"""Removal targeting: is clearing a site permanent, or maintenance?

The finding this suite pins down: there is a WINDOW. Early in an invasion,
cleared sites stay clear and any sensible policy works. Late, everything refills
and no targeting helps. Targeted removal earns its keep in between.
"""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tilapia.experiment import simulate  # noqa: E402
from tilapia.removal import (  # noqa: E402
    RemovalCandidate, compare_removal_policies, expected_periods_clear,
    rank_removal_sites, reinvasion_hazard, treadmill_share,
)
from tilapia.spread import ModelSpec, SpreadNetwork, fit  # noqa: E402

N = 40
HORIZON = 20.0


def build():
    rng = np.random.default_rng(11)
    w = np.zeros((N, N))
    for i in range(N - 1):
        w[i, i + 1] = w[i + 1, i] = 1.0
    h = np.zeros((N, N))
    for hub in (0, 13, 26):
        for j in range(N):
            if abs(j - hub) > 3:
                h[hub, j] = h[j, hub] = 1.0
    net = SpreadNetwork(
        [f"S{i:02d}" for i in range(N)],
        w + rng.random((N, N)) * 0.02,
        h + rng.random((N, N)) * 0.02,
        rng.normal(size=N),
    )
    spec = ModelSpec("hybrid", use_water=True, use_human=True)
    seq = simulate(spec, net, np.array([-4.0, 2.0, 2.5]), [0], 14, np.random.default_rng(5))
    return net, spec, seq, fit(spec, net, seq), rng.lognormal(3.0, 0.8, N)


net, spec, seq, fitted, assets = build()
results = []


def check(label, condition, detail=""):
    print(f"[{'PASS' if condition else 'FAIL'}] {label}{'  -- ' + detail if detail else ''}")
    return condition


def state_at(stop):
    inv = np.zeros(N)
    for _, newly in seq[:stop]:
        inv[newly] = 1.0
    return inv


def candidates(inv):
    return [
        RemovalCandidate(f"S{i:02d}", i, float(assets[i]), 1.0 + (i % 3) * 0.2)
        for i in range(N) if inv[i] > 0
    ]


# --- components ------------------------------------------------------------
results.append(check(
    "a site with invaded neighbours refills faster than an isolated one",
    expected_periods_clear(0.8, HORIZON) < expected_periods_clear(0.05, HORIZON),
    f"{expected_periods_clear(0.8, HORIZON):.2f} vs {expected_periods_clear(0.05, HORIZON):.2f} periods",
))

# --- the window ------------------------------------------------------------
early = state_at(4)
late = state_at(len(seq))
rows_early = rank_removal_sites(candidates(early), fitted, net, early, HORIZON)
rows_late = rank_removal_sites(candidates(late), fitted, net, late, HORIZON)

results.append(check(
    "early invasion: cleared sites stay clear",
    treadmill_share(rows_early) == 0.0,
    f"treadmill share {treadmill_share(rows_early)} at {int(early.sum())}/{N} invaded",
))
results.append(check(
    "saturated network: every cleared site refills quickly",
    treadmill_share(rows_late) > 0.9,
    f"treadmill share {treadmill_share(rows_late)} at {int(late.sum())}/{N} invaded",
))
results.append(check(
    "durability collapses as the network saturates",
    max(float(r["periods_clear"]) for r in rows_late)
    < max(float(r["periods_clear"]) for r in rows_early),
    f"best stays-clear {max(float(r['periods_clear']) for r in rows_late):.1f} "
    f"vs {max(float(r['periods_clear']) for r in rows_early):.1f} periods",
))

# --- targeting value is non-monotonic -------------------------------------
gains = []
for stop in range(2, len(seq) + 1):
    inv = state_at(stop)
    k = int(inv.sum())
    if k < 3 or k >= N:
        continue
    pol = {r["policy"]: r for r in
           compare_removal_policies(candidates(inv), fitted, net, inv, 8.0, HORIZON)}
    gains.append((k, float(pol["durable_first"]["vs_worst_affected"])))

mid = max(gains, key=lambda g: g[1])
results.append(check(
    "targeting matters most mid-invasion, not at either extreme",
    gains[0][1] < mid[1] > gains[-1][1],
    f"gain {gains[0][1]}x at {gains[0][0]} invaded, peak {mid[1]}x at {mid[0]}, "
    f"{gains[-1][1]}x at {gains[-1][0]}",
))

# --- and again, the model adds little over a simple heuristic -------------
inv = state_at(len(seq) - 3)
pol = {r["policy"]: r for r in
       compare_removal_policies(candidates(inv), fitted, net, inv, 8.0, HORIZON)}
ratio = float(pol["durable_first"]["durable_benefit"]) / float(pol["largest_assets"]["durable_benefit"])
results.append(check(
    "durable ranking beats assets-only by only a small margin (recorded, not hidden)",
    1.0 <= ratio < 1.4,
    f"{ratio:.3f}x -- most of the gain is in avoiding the worst-affected default",
))

print()
print(f"{sum(results)}/{len(results)} passed")
sys.exit(0 if all(results) else 1)
