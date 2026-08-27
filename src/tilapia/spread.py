"""The two-layer spread model. This is the part that makes the project science.

The extraction pipeline is instrumentation -- it produces observations. This
module states a hypothesis about those observations that could turn out to be
false, and the accompanying `experiment.py` tests it.

THE MODEL
---------
Each region is a node, invaded or not. In each time step, an uninvaded node i
faces a hazard of becoming invaded that depends on which of its neighbours are
already invaded, weighted by how strongly they are connected:

    pressure_i(t) = beta_water * SUM_(j invaded) W_water[i,j]
                  + beta_human * SUM_(j invaded) W_human[i,j]
                  + beta_local * suitability_i
                  + beta_0

    P(i invaded at t) = 1 - exp(-exp(pressure_i(t)))

Two layers, two coefficients. `W_water` encodes hydrological connectivity;
`W_human` encodes aquaculture-mediated movement between regions. The whole
project reduces to a question about those two numbers:

    H0 (diffusion):        beta_human = 0. Water explains the spread.
    H1 (human transport):  beta_human > 0 and carries predictive weight that
                           beta_water cannot.

That is falsifiable. If the waterway-only model predicts the observed invasion
sequence as well as the hybrid does, the hypothesis is wrong and the correct
result is to say so.

WHY THE COMPARISON IS NOT AUTOMATIC
-----------------------------------
The hybrid model has one more parameter than the waterway model, so it will fit
the observed sequence better no matter what. In-sample fit therefore proves
nothing, which is why `experiment.py` scores every model by out-of-sample
prediction of the next region invaded and reports AIC alongside.

The deeper problem is that in Thailand the two layers are correlated: the
Chao Phraya delta is simultaneously the water network and the aquaculture core.
Where both layers say the same thing, the data cannot tell them apart.
`discordant_pairs()` finds the region pairs where they disagree -- connected by
water but not by trade, or vice versa. Those pairs carry the inferential weight,
and the honest version of this project reports how many of them exist before
claiming anything.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy.optimize import minimize


@dataclass
class SpreadNetwork:
    """Regions plus the two connectivity layers.

    Both weight matrices are row-normalised at construction so that
    `beta_water` and `beta_human` are on a comparable scale -- without that,
    whichever layer happens to carry larger raw numbers dominates for reasons
    that have nothing to do with biology.
    """

    node_ids: list[str]
    w_water: np.ndarray
    w_human: np.ndarray
    suitability: np.ndarray | None = None

    def __post_init__(self) -> None:
        n = len(self.node_ids)
        for name, matrix in (("w_water", self.w_water), ("w_human", self.w_human)):
            if matrix.shape != (n, n):
                raise ValueError(f"{name} must be {n}x{n}, got {matrix.shape}")
        self.w_water = _row_normalise(self.w_water)
        self.w_human = _row_normalise(self.w_human)
        if self.suitability is None:
            self.suitability = np.zeros(n)
        else:
            std = self.suitability.std()
            self.suitability = (
                (self.suitability - self.suitability.mean()) / std
                if std > 0
                else np.zeros(n)
            )

    @property
    def n(self) -> int:
        return len(self.node_ids)

    def index(self, node_id: str) -> int:
        return self.node_ids.index(node_id)


def _row_normalise(matrix: np.ndarray) -> np.ndarray:
    matrix = np.asarray(matrix, dtype=float).copy()
    np.fill_diagonal(matrix, 0.0)
    totals = matrix.sum(axis=1, keepdims=True)
    return np.divide(matrix, totals, out=np.zeros_like(matrix), where=totals > 0)


@dataclass(frozen=True)
class ModelSpec:
    """Which layers a model is allowed to use.

    The nulls matter as much as the hypothesis. `aquaculture_only` in
    particular is the one that keeps this honest: if simply ranking regions by
    farming intensity predicts the invasion sequence as well as the network
    models do, then the networks are decorative and the real finding is "big
    aquaculture regions get invaded first".
    """

    name: str
    use_water: bool = False
    use_human: bool = False
    use_local: bool = False

    @property
    def n_params(self) -> int:
        return 1 + sum((self.use_water, self.use_human, self.use_local))


MODELS = [
    ModelSpec("waterway_only", use_water=True),
    ModelSpec("human_only", use_human=True),
    ModelSpec("hybrid", use_water=True, use_human=True),
    ModelSpec("hybrid_plus_local", use_water=True, use_human=True, use_local=True),
    ModelSpec("aquaculture_only", use_local=True),   # no network at all
    ModelSpec("intercept_only"),                     # everything invaded at random
]


@dataclass
class FittedModel:
    spec: ModelSpec
    params: dict[str, float]
    log_likelihood: float
    n_observations: int
    converged: bool = True
    _network: SpreadNetwork | None = field(default=None, repr=False)

    @property
    def aic(self) -> float:
        return 2 * self.spec.n_params - 2 * self.log_likelihood

    @property
    def bic(self) -> float:
        return self.spec.n_params * np.log(max(self.n_observations, 1)) - 2 * self.log_likelihood


def _pressure(
    spec: ModelSpec,
    network: SpreadNetwork,
    theta: np.ndarray,
    invaded: np.ndarray,
) -> np.ndarray:
    """Linear predictor for every node given who is currently invaded."""
    cursor = 0
    pressure = np.full(network.n, theta[cursor])
    cursor += 1

    if spec.use_water:
        pressure = pressure + theta[cursor] * (network.w_water @ invaded)
        cursor += 1
    if spec.use_human:
        pressure = pressure + theta[cursor] * (network.w_human @ invaded)
        cursor += 1
    if spec.use_local:
        pressure = pressure + theta[cursor] * network.suitability

    return pressure


def hazard(
    spec: ModelSpec, network: SpreadNetwork, theta: np.ndarray, invaded: np.ndarray
) -> np.ndarray:
    """Per-step invasion probability. Complementary log-log link."""
    p = _pressure(spec, network, theta, invaded)
    return 1.0 - np.exp(-np.exp(np.clip(p, -30, 30)))


def _neg_log_likelihood(
    theta: np.ndarray,
    spec: ModelSpec,
    network: SpreadNetwork,
    sequence: list[tuple[int, list[int]]],
) -> float:
    """Discrete-time survival likelihood over the observed invasion sequence.

    At each step, nodes newly invaded contribute log(p) and nodes still
    uninvaded contribute log(1-p). Already-invaded nodes are removed from the
    risk set -- this species is not being eradicated anywhere, so invasion is
    treated as absorbing.
    """
    invaded = np.zeros(network.n)
    total = 0.0

    for _, newly in sequence:
        at_risk = invaded == 0
        if not at_risk.any():
            break

        p = np.clip(hazard(spec, network, theta, invaded), 1e-12, 1 - 1e-12)
        newly_mask = np.zeros(network.n, dtype=bool)
        newly_mask[newly] = True

        total += np.log(p[at_risk & newly_mask]).sum()
        total += np.log1p(-p[at_risk & ~newly_mask]).sum()

        invaded = invaded.copy()
        invaded[newly] = 1.0

    return -total


def fit(
    spec: ModelSpec,
    network: SpreadNetwork,
    sequence: list[tuple[int, list[int]]],
) -> FittedModel:
    """Maximum-likelihood fit of one model to one invasion sequence.

    `sequence` is [(time, [node indices invaded at that time]), ...] in order.
    Multiple simultaneous invasions in one step are fine and common -- province
    confirmations cluster.
    """
    x0 = np.zeros(spec.n_params)
    x0[0] = -3.0  # low baseline hazard; most regions are not invaded most years

    result = minimize(
        _neg_log_likelihood,
        x0,
        args=(spec, network, sequence),
        method="Nelder-Mead",
        options={"maxiter": 4000, "xatol": 1e-6, "fatol": 1e-6},
    )

    names = ["intercept"]
    if spec.use_water:
        names.append("beta_water")
    if spec.use_human:
        names.append("beta_human")
    if spec.use_local:
        names.append("beta_local")

    n_obs = sum(len(newly) for _, newly in sequence)
    return FittedModel(
        spec=spec,
        params=dict(zip(names, result.x)),
        log_likelihood=-result.fun,
        n_observations=n_obs,
        converged=bool(result.success),
        _network=network,
    )


def rank_next(
    fitted: FittedModel, network: SpreadNetwork, invaded: np.ndarray
) -> list[int]:
    """Rank the uninvaded nodes by predicted hazard, most likely first.

    This is the model's actual prediction, and the thing `experiment.py` scores.
    A map of where the fish is would be reporting; a ranked list of where it
    goes next, committed before checking, is a testable claim.
    """
    theta = np.array(list(fitted.params.values()))
    p = hazard(fitted.spec, network, theta, invaded)
    p = np.where(invaded > 0, -np.inf, p)
    return [int(i) for i in np.argsort(-p) if invaded[i] == 0]


def discordant_pairs(
    network: SpreadNetwork, min_gap: float = 0.3
) -> list[tuple[str, str, float, float]]:
    """Region pairs where the two layers disagree most.

    Returns (node_a, node_b, water_weight, human_weight) for pairs that are
    well connected on one layer and poorly on the other.

    These pairs are where the hypothesis is actually testable. Everywhere the
    delta's water network and its trade network coincide, both models predict
    the same thing and the data cannot separate them. Report how many
    discordant pairs exist BEFORE reporting a model comparison -- if there are
    very few, the comparison is weakly identified no matter how good the
    accuracy numbers look, and saying so first is what distinguishes a result
    from a coincidence.
    """
    pairs = []
    for i in range(network.n):
        for j in range(i + 1, network.n):
            water = max(network.w_water[i, j], network.w_water[j, i])
            human = max(network.w_human[i, j], network.w_human[j, i])
            if abs(water - human) >= min_gap:
                pairs.append((network.node_ids[i], network.node_ids[j], water, human))

    return sorted(pairs, key=lambda p: -abs(p[2] - p[3]))
