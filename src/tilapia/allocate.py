"""Turning a risk map into a survey plan. This is the part that touches the problem.

Nothing in this repository removes a fish. The invasion is established and
national eradication is not achievable; that is the premise, not a failure of
the project. What is achievable is finding *new* incursions while they are still
small enough to remove locally, and the binding constraint on that is not
knowledge, it is survey days. A provincial office has a handful of staff and a
coastline.

So the deliverable is not "here is where the fish is". It is "given N survey
days, here is where to spend them, and here is how much more damage that averts
than the obvious policy."

THE ASYMMETRY THAT MAKES THIS WORTH DOING
-----------------------------------------
Local eradication is genuinely possible when a population is confined to a few
ponds or a short canal segment -- drain, net, treat. Once it is spread across a
connected canal network it is not. The value of detection therefore does not
decline smoothly with delay; it falls off a cliff. Moving detection earlier in a
few places is worth more than marginally improving a map everywhere.

WHY THE OBVIOUS POLICY IS WRONG
-------------------------------
The obvious policy is "survey the highest-risk sites". It is wrong for a reason
that is easy to state and easy to miss:

    A site almost certain to be invaded is almost certainly past the point where
    finding it helps.

High invasion probability is a proxy for "the fish arrived a while ago", and
containability declines with time since arrival. Surveying a site at p=0.95
mostly buys you confirmation of something you already believed, about a
population you can no longer remove. Surveying at p=0.02 mostly buys you
nothing. The value is in the middle, weighted by what is downstream.

`compare_policies()` measures that gap. If it is small for the real Thai
network, say so -- that is a finding too, and it means the existing policy is
already near-optimal, which is worth telling a fisheries office.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class Site:
    """One candidate survey location, usually a subdistrict.

    `assets_at_risk` should be something defensible and public -- aquaculture
    area, or number of registered farms. Do not invent a composite index; a
    judge will ask how it was weighted and "I chose the weights" is a weak
    answer. One measured quantity, stated plainly, is stronger.
    """

    site_id: str
    p_invaded: float          # from spread.rank_next / the fitted hazard model
    assets_at_risk: float     # e.g. hectares of aquaculture in the subdistrict
    survey_cost: float = 1.0  # survey-days; travel makes remote sites cost more


def containability(p_invaded: float, sharpness: float = 6.0) -> float:
    """Probability that an incursion is still small enough to remove locally.

    Modelled as declining in `p_invaded`, which stands in for time since
    arrival: the longer a population has been present, the more likely both that
    someone would have noticed (raising p) and that it has spread beyond
    containment (lowering c).

    This is the assumption doing the most work in the whole module, so state it
    explicitly in the report and show the result under at least two values of
    `sharpness`. If the ranking is stable across them, the conclusion does not
    depend on the exact shape. If it flips, the honest finding is that the
    allocation is sensitive to an unmeasured parameter -- which is worth knowing
    before anyone drives anywhere.

    A better version replaces this with something measured: time between first
    community report and official confirmation, per province, which the
    extraction pipeline can supply.
    """
    return float(np.exp(-sharpness * p_invaded))


def detection_probability(effort: float, per_visit: float = 0.6) -> float:
    """Chance of finding the species given it is present.

    Surveys miss things -- especially a small founding population in a large
    canal system. `per_visit` well below 1 is realistic and it matters: it is
    why spreading effort thinly can be worse than concentrating it.
    """
    return float(1.0 - (1.0 - per_visit) ** effort)


def expected_value(
    site: Site, effort: float = 1.0, sharpness: float = 6.0, per_visit: float = 0.6
) -> float:
    """Expected damage averted by surveying this site.

        P(invaded) x P(detect | invaded) x P(still removable) x assets at risk

    Every term is necessary. Drop containability and you get the naive policy
    that chases certainty. Drop detection probability and you assume surveys
    never miss. Drop assets and you protect empty water.
    """
    return (
        site.p_invaded
        * detection_probability(effort, per_visit)
        * containability(site.p_invaded, sharpness)
        * site.assets_at_risk
    )


# --------------------------------------------------------------------------
# Policies
# --------------------------------------------------------------------------


def policy_highest_risk(sites: list[Site], budget: float) -> list[str]:
    """The obvious policy: survey wherever invasion is most likely."""
    return _take_within_budget(sorted(sites, key=lambda s: -s.p_invaded), budget)


def policy_largest_assets(sites: list[Site], budget: float) -> list[str]:
    """Protect the biggest farming areas, ignoring risk. A common real default."""
    return _take_within_budget(sorted(sites, key=lambda s: -s.assets_at_risk), budget)


def policy_expected_value(
    sites: list[Site], budget: float, sharpness: float = 6.0, per_visit: float = 0.6
) -> list[str]:
    """Maximise averted damage per survey-day.

    Ranks by expected value divided by cost -- the greedy solution to a
    fractional knapsack, which is optimal here and, more importantly, is
    explainable to the person who has to sign off on it. A method a fisheries
    officer cannot follow is not a method they will use.
    """
    ranked = sorted(
        sites,
        key=lambda s: -expected_value(s, 1.0, sharpness, per_visit) / max(s.survey_cost, 1e-9),
    )
    return _take_within_budget(ranked, budget)


def _take_within_budget(ranked: list[Site], budget: float) -> list[str]:
    chosen, spent = [], 0.0
    for site in ranked:
        if spent + site.survey_cost <= budget:
            chosen.append(site.site_id)
            spent += site.survey_cost
    return chosen


# --------------------------------------------------------------------------
# Comparison
# --------------------------------------------------------------------------


def evaluate_policy(
    sites: list[Site], chosen: list[str], sharpness: float = 6.0, per_visit: float = 0.6
) -> float:
    """Total expected damage averted by a chosen set of sites."""
    index = {s.site_id: s for s in sites}
    return sum(expected_value(index[sid], 1.0, sharpness, per_visit) for sid in chosen)


def compare_policies(
    sites: list[Site], budget: float, sharpness: float = 6.0, per_visit: float = 0.6
) -> list[dict[str, object]]:
    """Run every policy on the same sites and budget.

    The output is the project's actual policy claim, and it is falsifiable in the
    same way the spread model is: if the expected-value policy does not beat
    highest-risk on the real network, then the sophistication bought nothing and
    the existing approach was already right.
    """
    policies = {
        "highest_risk": policy_highest_risk(sites, budget),
        "largest_assets": policy_largest_assets(sites, budget),
        "expected_value": policy_expected_value(sites, budget, sharpness, per_visit),
    }

    baseline = evaluate_policy(sites, policies["highest_risk"], sharpness, per_visit)
    rows = []
    for name, chosen in policies.items():
        value = evaluate_policy(sites, chosen, sharpness, per_visit)
        rows.append({
            "policy": name,
            "n_sites": len(chosen),
            "expected_averted": round(value, 1),
            "vs_highest_risk": round(value / baseline, 2) if baseline > 0 else None,
            "median_p_invaded": round(
                float(np.median([s.p_invaded for s in sites if s.site_id in chosen])), 3
            ) if chosen else None,
        })

    return sorted(rows, key=lambda r: -float(r["expected_averted"]))


def sensitivity(
    sites: list[Site], budget: float, sharpness_values: tuple[float, ...] = (3.0, 6.0, 10.0)
) -> list[dict[str, object]]:
    """Does the conclusion survive the assumption it rests on?

    `containability` is the least-measured part of this model. Run the
    comparison across plausible values and report the range. A conclusion that
    holds across all of them is worth stating; one that flips is worth stating
    even more clearly, as a limitation.
    """
    rows = []
    for sharpness in sharpness_values:
        comparison = compare_policies(sites, budget, sharpness)
        ev = next(r for r in comparison if r["policy"] == "expected_value")
        rows.append({
            "sharpness": sharpness,
            "ev_gain_over_highest_risk": ev["vs_highest_risk"],
            "winner": comparison[0]["policy"],
        })
    return rows
