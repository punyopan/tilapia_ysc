"""Allocation policy tests.

The important one is `test: model gain over the trivial heuristic is small` --
it asserts the deflating result rather than the flattering one. A test suite
that only confirms what you hoped is not evidence.
"""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tilapia.allocate import (  # noqa: E402
    Site, compare_policies, containability, detection_probability,
    expected_value, policy_expected_value, policy_highest_risk, sensitivity,
)

BUDGET = 20.0


def make_sites(seed: int, n: int = 200) -> list[Site]:
    rng = np.random.default_rng(seed)
    p = np.clip(rng.beta(1.4, 4.0, n), 0.001, 0.999)
    assets = rng.lognormal(3.0, 1.0, n)
    cost = 1.0 + rng.random(n) * 0.6
    return [Site(f"T{i}", float(p[i]), float(assets[i]), float(cost[i])) for i in range(n)]


results = []


def check(label, condition, detail=""):
    print(f"[{'PASS' if condition else 'FAIL'}] {label}{'  -- ' + detail if detail else ''}")
    return condition


# --- component behaviour ---------------------------------------------------
results.append(check(
    "containability falls as invasion probability rises",
    containability(0.05) > containability(0.5) > containability(0.95),
    f"{containability(0.05):.3f} > {containability(0.5):.3f} > {containability(0.95):.3f}",
))
results.append(check(
    "detection improves with effort but never reaches certainty",
    detection_probability(1) < detection_probability(3) < 1.0,
    f"{detection_probability(1):.2f} -> {detection_probability(3):.2f}",
))

# --- the interior optimum: value peaks in the middle, not at the top -------
probe = [Site("x", p, 100.0) for p in (0.02, 0.15, 0.35, 0.6, 0.9, 0.99)]
values = [expected_value(s) for s in probe]
peak = int(np.argmax(values))
results.append(check(
    "expected value peaks at moderate risk, not maximum risk",
    0 < peak < len(probe) - 1,
    f"peak at p={probe[peak].p_invaded} (values {[round(v,1) for v in values]})",
))

# --- the two policies genuinely disagree -----------------------------------
sites = make_sites(3)
hr = set(policy_highest_risk(sites, BUDGET))
ev = set(policy_expected_value(sites, BUDGET))
results.append(check(
    "the two policies send you to different places",
    len(hr & ev) == 0,
    f"{len(hr & ev)} of {len(hr)} sites in common",
))

# --- direction is robust to the unmeasured assumption ----------------------
sens = sensitivity(sites, BUDGET, (2.0, 4.0, 6.0, 10.0))
results.append(check(
    "expected-value policy wins at every containability assumption tested",
    all(r["winner"] == "expected_value" for r in sens),
    f"gains {[r['ev_gain_over_highest_risk'] for r in sens]}",
))

# --- but the MAGNITUDE is not robust, and the suite says so ---------------
gains = [float(r["ev_gain_over_highest_risk"]) for r in sens]
results.append(check(
    "magnitude of the gain is NOT stable -- report the direction only",
    max(gains) / min(gains) > 3,
    f"{min(gains)}x to {max(gains)}x across plausible assumptions",
))

# --- the deflating result, asserted on purpose ----------------------------
ratios = []
for seed in range(8):
    rows = {r["policy"]: r for r in compare_policies(make_sites(seed), BUDGET)}
    ratios.append(
        float(rows["expected_value"]["expected_averted"])
        / float(rows["largest_assets"]["expected_averted"])
    )
mean_gain = float(np.mean(ratios))
results.append(check(
    "model beats the trivial assets-only heuristic by only a few percent",
    1.0 < mean_gain < 1.25,
    f"mean {mean_gain:.3f}x over 8 trials -- most of the benefit is in "
    f"abandoning highest-risk, not in the model",
))

print()
print(f"{sum(results)}/{len(results)} passed")
sys.exit(0 if all(results) else 1)
