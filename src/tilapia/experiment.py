"""The test. This is where a map becomes a claim that could be wrong.

Three things live here, and the order matters:

  1. can_this_experiment_work()  -- run BEFORE touching real data
  2. rolling_validation()        -- the actual out-of-sample test
  3. compare()                   -- the result table

Step 1 is the one people skip. Before asking "which model does reality match",
establish that this method can tell the models apart *at all* at the sample size
you have. Simulate an invasion from a known layer, hand the harness the result,
and see whether it recovers the layer you used. If it cannot recover a signal
you planted yourself, then any answer it gives on real data is noise, and you
have learned that for the price of a few seconds of compute rather than a
season of fieldwork.

Reporting that check is also the strongest possible answer to "how do you know
your model isn't just fitting noise?" -- you tested it against a case where you
knew the truth.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .spread import (
    MODELS,
    FittedModel,
    ModelSpec,
    SpreadNetwork,
    fit,
    hazard,
    rank_next,
)


@dataclass
class ValidationResult:
    model_name: str
    reciprocal_ranks: list[float]
    ranks: list[int]
    n_candidates: list[int]

    @property
    def mrr(self) -> float:
        """Mean reciprocal rank of the region that was actually invaded next."""
        return float(np.mean(self.reciprocal_ranks)) if self.reciprocal_ranks else 0.0

    def top_k(self, k: int) -> float:
        if not self.ranks:
            return 0.0
        return float(np.mean([r <= k for r in self.ranks]))

    @property
    def skill_over_random(self) -> float:
        """MRR relative to guessing uniformly among the uninvaded regions.

        Report this, not raw MRR. With few candidates left, even a useless
        model scores a respectable-looking MRR -- late in the sequence there
        are only a handful of uninvaded provinces and picking at random gets
        you close. A value near 1.0 means no skill regardless of how good the
        raw number looks.
        """
        if not self.reciprocal_ranks:
            return 0.0
        expected = [
            float(np.mean([1.0 / r for r in range(1, n + 1)])) if n else 0.0
            for n in self.n_candidates
        ]
        baseline = float(np.mean(expected))
        return self.mrr / baseline if baseline > 0 else 0.0


def rolling_validation(
    spec: ModelSpec,
    network: SpreadNetwork,
    sequence: list[tuple[int, list[int]]],
    min_train_steps: int = 3,
) -> ValidationResult:
    """Fit on the past, predict the next region, walk forward. Repeat.

    This is the honest comparison. Every model here has a different number of
    parameters, so in-sample likelihood is not evidence -- a richer model always
    fits better. Out-of-sample prediction is not free that way: an extra
    parameter that is fitting noise makes the next prediction worse, not better.

    `min_train_steps` holds back the first few steps because a model fitted to
    two invasions predicts nothing meaningful. With a sequence as short as this
    one, that leaves few test points -- which is a real limitation to state
    plainly, not to hide behind an average.
    """
    reciprocal_ranks: list[float] = []
    ranks: list[int] = []
    n_candidates: list[int] = []

    for split in range(min_train_steps, len(sequence)):
        train = sequence[:split]
        truth = sequence[split][1]

        invaded = np.zeros(network.n)
        for _, newly in train:
            invaded[newly] = 1.0

        if invaded.sum() == 0 or (invaded == 0).sum() == 0:
            continue

        fitted = fit(spec, network, train)
        ranking = rank_next(fitted, network, invaded)
        if not ranking:
            continue

        # Best rank achieved among the regions actually invaded next.
        positions = [ranking.index(node) + 1 for node in truth if node in ranking]
        if not positions:
            continue

        best = min(positions)
        ranks.append(best)
        reciprocal_ranks.append(1.0 / best)
        n_candidates.append(len(ranking))

    return ValidationResult(spec.name, reciprocal_ranks, ranks, n_candidates)


def compare(
    network: SpreadNetwork,
    sequence: list[tuple[int, list[int]]],
    specs: list[ModelSpec] | None = None,
    min_train_steps: int = 3,
) -> list[dict[str, object]]:
    """Run every model against the same sequence. This table is the result."""
    specs = specs or MODELS
    rows = []

    for spec in specs:
        fitted = fit(spec, network, sequence)
        validation = rolling_validation(spec, network, sequence, min_train_steps)
        rows.append({
            "model": spec.name,
            "n_params": spec.n_params,
            "aic": round(fitted.aic, 2),
            "mrr": round(validation.mrr, 3),
            "top3": round(validation.top_k(3), 3),
            "skill": round(validation.skill_over_random, 2),
            "n_test": len(validation.ranks),
            "params": {k: round(v, 3) for k, v in fitted.params.items()},
        })

    return sorted(rows, key=lambda r: -float(r["mrr"]))


def print_comparison(rows: list[dict[str, object]]) -> None:
    header = f"{'model':<20}{'params':<8}{'AIC':<10}{'MRR':<8}{'top-3':<8}{'skill':<8}{'n':<5}"
    print(header)
    print("-" * len(header))
    for row in rows:
        print(
            f"{row['model']:<20}{row['n_params']:<8}{row['aic']:<10}"
            f"{row['mrr']:<8}{row['top3']:<8}{row['skill']:<8}{row['n_test']:<5}"
        )


# --------------------------------------------------------------------------
# Run this before the real data
# --------------------------------------------------------------------------


def simulate(
    spec: ModelSpec,
    network: SpreadNetwork,
    theta: np.ndarray,
    seeds: list[int],
    n_steps: int,
    rng: np.random.Generator,
) -> list[tuple[int, list[int]]]:
    """Generate an invasion sequence from a known model."""
    invaded = np.zeros(network.n)
    invaded[seeds] = 1.0
    sequence: list[tuple[int, list[int]]] = [(0, list(seeds))]

    for t in range(1, n_steps + 1):
        p = hazard(spec, network, theta, invaded)
        draws = rng.random(network.n)
        newly = [i for i in range(network.n) if invaded[i] == 0 and draws[i] < p[i]]
        if newly:
            sequence.append((t, newly))
            invaded[newly] = 1.0
        if invaded.all():
            break

    return sequence


def can_this_experiment_work(
    network: SpreadNetwork,
    truth_spec: ModelSpec,
    truth_theta: np.ndarray,
    seeds: list[int],
    n_steps: int = 15,
    n_replicates: int = 30,
    seed: int = 0,
) -> dict[str, object]:
    """Power check: plant a signal, see whether the harness finds it.

    Simulates invasions driven by `truth_spec`, then asks the full model
    comparison which layer it thinks was responsible. Returns how often the
    generating layer was correctly identified.

    Interpreting the number:

      >0.8   the design can detect this effect at this sample size. Proceed.
      0.5-0.8 weak. Report it, and treat a real-data result as suggestive.
      <0.5   the design cannot tell the layers apart. A real-data answer would
             be meaningless. Fix it -- more nodes (subdistricts rather than
             provinces), more discordant pairs, or a longer sequence -- before
             collecting anything.

    A low number here is not a failed project. It is a finding about study
    design, arrived at before wasting a season on it, and it belongs in the
    report either way.
    """
    rng = np.random.default_rng(seed)
    exact = 0
    layer = 0
    attempted = 0
    winners: dict[str, int] = {}
    by_spec = {spec.name: spec for spec in MODELS}

    def uses_generating_layer(name: str) -> bool:
        spec = by_spec.get(name)
        if spec is None:
            return False
        return (
            (truth_spec.use_human and spec.use_human)
            or (truth_spec.use_water and spec.use_water)
        )

    for _ in range(n_replicates):
        sequence = simulate(truth_spec, network, truth_theta, seeds, n_steps, rng)
        if len(sequence) < 5:
            continue

        attempted += 1
        rows = compare(network, sequence, min_train_steps=2)
        winner = str(rows[0]["model"])
        winners[winner] = winners.get(winner, 0) + 1
        if winner == truth_spec.name:
            exact += 1
        if uses_generating_layer(winner):
            layer += 1

    # What a coin-flip would score. Without this the recovery rates read far
    # better than they are: if half the candidate models contain the human
    # layer, picking at random already "recovers" it 50% of the time.
    n_with_layer = sum(1 for s in MODELS if uses_generating_layer(s.name))
    chance = n_with_layer / len(MODELS)

    return {
        "generating_model": truth_spec.name,
        "replicates": attempted,
        # Exact model selection. Usually pessimistic: picking `hybrid` when the
        # truth is `human_only` counts as a miss here, even though it got the
        # mechanism right and merely kept a coefficient near zero.
        "exact_recovery_rate": round(exact / attempted, 3) if attempted else 0.0,
        # The scientifically meaningful one: did the winning model include the
        # layer that actually generated the data? This is the question the
        # project asks -- "did people move the fish" -- not "which of six
        # parameterisations is minimal".
        "layer_recovery_rate": round(layer / attempted, 3) if attempted else 0.0,
        "layer_recovery_ci95": wilson_interval(layer, attempted),
        "chance_baseline": round(chance, 3),
        # The only number that means anything on its own. <=0 is no evidence
        # the design can identify the mechanism at all.
        "lift_over_chance": round((layer / attempted) - chance, 3) if attempted else 0.0,
        "winner_counts": dict(sorted(winners.items(), key=lambda kv: -kv[1])),
    }


def wilson_interval(successes: int, trials: int, z: float = 1.96) -> tuple[float, float]:
    """95% CI for a proportion.

    Included because power checks are slow, so the temptation is to run 10 or 12
    replicates and read the result as if it were precise. At n=12 a rate of 0.58
    has a CI roughly [0.32, 0.81] -- wide enough to contain both "no signal" and
    "strong signal". Report the interval, and do not compare two rates whose
    intervals overlap.
    """
    if trials == 0:
        return (0.0, 0.0)
    p = successes / trials
    denom = 1 + z**2 / trials
    centre = (p + z**2 / (2 * trials)) / denom
    margin = z * np.sqrt(p * (1 - p) / trials + z**2 / (4 * trials**2)) / denom
    return (round(max(0.0, centre - margin), 3), round(min(1.0, centre + margin), 3))


def resolution_scan(
    build_network,
    truth_spec: ModelSpec,
    truth_theta: np.ndarray,
    sizes: tuple[int, ...] = (24, 60, 120),
    n_replicates: int = 12,
    n_steps: int = 18,
) -> list[dict[str, object]]:
    """How much does spatial resolution buy?

    `build_network` is a callable taking a node count and returning a
    SpreadNetwork. Runs the power check at each size.

    This answers a design question the project has to settle before collecting
    anything: work at province level (~77 nodes, but only ~19 invasion events)
    or push the extraction to subdistrict level (thousands of nodes, many more
    events but noisier labels). Guessing is expensive; simulating is free.
    """
    rows = []
    for size in sizes:
        network = build_network(size)
        seeds = [0]
        power = can_this_experiment_work(
            network, truth_spec, truth_theta, seeds,
            n_steps=n_steps, n_replicates=n_replicates,
        )
        rows.append({
            "n_nodes": size,
            "exact": power["exact_recovery_rate"],
            "layer": power["layer_recovery_rate"],
            "replicates": power["replicates"],
        })
    return rows
