"""Where removal actually sticks, and where it is a treadmill.

Removal is what everyone wants, and the project should say so plainly. The
honest position is not "eradication is off the table so we do surveillance
instead" -- it is that *removal splits into two different problems with
different answers*:

  ESTABLISHED CORE       Clearing a site inside a densely invaded, well-connected
                         network buys you a temporary drop in density. Neighbours
                         refill it. The benefit lasts as long as the effort does,
                         and stops when the budget does. This is suppression, and
                         it is worth doing for damage reduction -- but calling it
                         eradication is wrong.

  NEW / ISOLATED SITE    Clearing a site with weak connection to invaded
                         neighbours can be permanent. This is real local
                         eradication, and it is achieved routinely.

The difference between them is not effort or technique. It is **reinvasion
pressure**, which is exactly the quantity the fitted spread model computes. So
the network model is not an alternative to removal work -- it is the thing that
says where removal work is durable.

That reframes the whole project:

    not "where is the fish"  -> a map
    not "where will it go"   -> a forecast
    but "where does clearing it stay cleared" -> a removal plan

WHY NATIONAL ERADICATION IS NOT THE TARGET
------------------------------------------
State this once, with reasons, and move on. An open, tidally connected canal
network spanning many provinces; a euryhaline species tolerating fresh through
hypersaline water; a mouthbrooder, so juvenile survival is high; already
established across many provinces. Documented eradications of established fish
happen in *closed* systems -- a single pond, a quarry, an isolated lake -- or
very early after arrival. The realistic national goal is containment plus
permanent clearance of new incursions, and that is what the policy has already
shifted to.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .spread import FittedModel, SpreadNetwork, hazard


@dataclass
class RemovalCandidate:
    site_id: str
    node_index: int
    assets_at_risk: float
    removal_cost: float       # effort-units to clear: scales with area and density
    success_probability: float = 0.7   # chance a clearance attempt actually works


def reinvasion_hazard(
    fitted: FittedModel,
    network: SpreadNetwork,
    node_index: int,
    invaded: np.ndarray,
) -> float:
    """Per-period probability that a cleared site is re-invaded by its neighbours.

    Uses the fitted spread model with the target marked clear. This is the
    number that decides whether removal is permanent or a treadmill, and it is
    only available because the spread model exists -- you cannot read it off a
    map of where the fish currently is.
    """
    state = invaded.copy()
    state[node_index] = 0.0
    theta = np.array(list(fitted.params.values()))
    return float(hazard(fitted.spec, network, theta, state)[node_index])


def expected_periods_clear(reinvasion_h: float, horizon: float = 20.0) -> float:
    """How long a cleared site stays clear, in time periods.

    Geometric waiting time, capped at a planning horizon -- an unbounded 1/h
    would let a site with near-zero hazard dominate every ranking on the
    strength of a modelled century of protection nobody can promise. The cap is
    a judgement; state it, and show the ranking is stable across a couple of
    values.
    """
    if reinvasion_h <= 0:
        return horizon
    return float(min(1.0 / reinvasion_h, horizon))


def durable_benefit(
    candidate: RemovalCandidate,
    fitted: FittedModel,
    network: SpreadNetwork,
    invaded: np.ndarray,
    horizon: float = 20.0,
) -> float:
    """Expected protected asset-periods from clearing this site once.

        P(clearance succeeds) x assets protected x periods it stays clear

    The third term is what distinguishes this from a naive "remove where the
    fish is densest" policy, and it is the entire argument of this module.
    """
    h = reinvasion_hazard(fitted, network, candidate.node_index, invaded)
    return (
        candidate.success_probability
        * candidate.assets_at_risk
        * expected_periods_clear(h, horizon)
    )


def rank_removal_sites(
    candidates: list[RemovalCandidate],
    fitted: FittedModel,
    network: SpreadNetwork,
    invaded: np.ndarray,
    horizon: float = 20.0,
) -> list[dict[str, object]]:
    """Rank by durable benefit per unit of removal effort."""
    rows = []
    for candidate in candidates:
        h = reinvasion_hazard(fitted, network, candidate.node_index, invaded)
        benefit = durable_benefit(candidate, fitted, network, invaded, horizon)
        rows.append({
            "site_id": candidate.site_id,
            "reinvasion_hazard": round(h, 4),
            "periods_clear": round(expected_periods_clear(h, horizon), 2),
            "durable_benefit": round(benefit, 1),
            "cost": round(candidate.removal_cost, 2),
            "benefit_per_cost": round(benefit / max(candidate.removal_cost, 1e-9), 2),
        })
    return sorted(rows, key=lambda r: -float(r["benefit_per_cost"]))


def treadmill_share(rows: list[dict[str, object]], threshold: float = 2.0) -> float:
    """Fraction of candidate sites that refill within `threshold` periods.

    Report this number. If most of the invaded range refills within a season,
    then the honest message to a fisheries office is that clearance campaigns
    there are recurring maintenance, not eradication, and should be budgeted and
    described as such. That is not a discouraging finding -- it is the
    difference between a programme that renews its funding and one that is
    declared a failure when the fish come back.
    """
    if not rows:
        return 0.0
    refill = sum(1 for r in rows if float(r["periods_clear"]) <= threshold)
    return round(refill / len(rows), 3)


def compare_removal_policies(
    candidates: list[RemovalCandidate],
    fitted: FittedModel,
    network: SpreadNetwork,
    invaded: np.ndarray,
    budget: float,
    horizon: float = 20.0,
) -> list[dict[str, object]]:
    """Durable benefit under three ways of spending the same removal budget.

    `worst_affected` is the realistic default policy: go where the problem is
    most visible and most complained about. It is politically natural and it is
    the one this module predicts will underperform, because visibility
    correlates with the density that makes refilling fast.
    """
    index = {c.site_id: c for c in candidates}
    ranked = rank_removal_sites(candidates, fitted, network, invaded, horizon)
    by_id = {r["site_id"]: r for r in ranked}

    def spend(order: list[str]) -> tuple[list[str], float]:
        chosen, spent, total = [], 0.0, 0.0
        for site_id in order:
            cost = index[site_id].removal_cost
            if spent + cost <= budget:
                chosen.append(site_id)
                spent += cost
                total += float(by_id[site_id]["durable_benefit"])
        return chosen, total

    policies = {
        # Where it is worst: highest reinvasion pressure = densest, most visible.
        "worst_affected": sorted(
            index, key=lambda s: -float(by_id[s]["reinvasion_hazard"])
        ),
        "largest_assets": sorted(index, key=lambda s: -index[s].assets_at_risk),
        "durable_first": [str(r["site_id"]) for r in ranked],
    }

    rows = []
    for name, order in policies.items():
        chosen, total = spend(order)
        rows.append({
            "policy": name,
            "sites_cleared": len(chosen),
            "durable_benefit": round(total, 1),
            "mean_periods_clear": round(
                float(np.mean([float(by_id[s]["periods_clear"]) for s in chosen])), 2
            ) if chosen else None,
        })

    baseline = next(r for r in rows if r["policy"] == "worst_affected")["durable_benefit"]
    for row in rows:
        row["vs_worst_affected"] = (
            round(float(row["durable_benefit"]) / baseline, 2) if baseline else None
        )

    return sorted(rows, key=lambda r: -float(r["durable_benefit"]))
