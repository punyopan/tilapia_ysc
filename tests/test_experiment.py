"""Does the experiment work at all?

Builds a synthetic country where the water network and the trade network are
deliberately different, simulates an invasion driven by ONE of them, and checks
that the model comparison points at the right one.

If this fails, nothing downstream means anything -- so it runs before any real
data does.
"""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tilapia.experiment import (  # noqa: E402
    can_this_experiment_work, compare, print_comparison, rolling_validation, simulate,
)
from tilapia.spread import MODELS, ModelSpec, SpreadNetwork, discordant_pairs, fit  # noqa: E402

N = 24


def build_network(seed: int = 7) -> SpreadNetwork:
    """Water = a river chain. Trade = long-range hubs. Deliberately discordant.

    This is the structure the real project needs to find in Thailand: places
    connected by canal but not by commerce, and places connected by commerce
    across a watershed boundary. Without such pairs the two hypotheses make the
    same predictions and no amount of data separates them.
    """
    rng = np.random.default_rng(seed)
    ids = [f"R{i:02d}" for i in range(N)]

    # Water: neighbours along a chain, plus a little noise.
    w_water = np.zeros((N, N))
    for i in range(N - 1):
        w_water[i, i + 1] = w_water[i + 1, i] = 1.0
    w_water += rng.random((N, N)) * 0.02

    # Trade: three hubs wired to distant nodes, ignoring the chain.
    w_human = np.zeros((N, N))
    hubs = [0, 8, 16]
    for hub in hubs:
        for node in range(N):
            if abs(node - hub) > 3:                 # deliberately NOT neighbours
                w_human[hub, node] = w_human[node, hub] = 1.0
    w_human += rng.random((N, N)) * 0.02

    suitability = rng.normal(size=N)
    return SpreadNetwork(ids, w_water, w_human, suitability)


results = []


def check(label, condition, detail=""):
    print(f"[{'PASS' if condition else 'FAIL'}] {label}{'  -- ' + detail if detail else ''}")
    return condition


net = build_network()

# --- the layers must actually differ ---------------------------------------
pairs = discordant_pairs(net, min_gap=0.05)
results.append(check(
    "synthetic network has discordant pairs to learn from",
    len(pairs) > 20,
    f"{len(pairs)} pairs where water and trade disagree",
))

# --- recover a planted human-transport signal ------------------------------
truth = ModelSpec("human_only", use_human=True)
theta_true = np.array([-4.0, 3.5])          # low baseline, strong trade effect
rng = np.random.default_rng(1)
sequence = simulate(truth, net, theta_true, seeds=[0], n_steps=18, rng=rng)

results.append(check(
    "simulated invasion produced a usable sequence",
    len(sequence) >= 6,
    f"{len(sequence)} time steps, {sum(len(s[1]) for s in sequence)} regions invaded",
))

rows = compare(net, sequence, min_train_steps=2)
print()
print_comparison(rows)
print()

human_row = next(r for r in rows if r["model"] == "human_only")
water_row = next(r for r in rows if r["model"] == "waterway_only")
results.append(check(
    "human-driven invasion: human model beats waterway model",
    human_row["mrr"] > water_row["mrr"],
    f"MRR {human_row['mrr']} vs {water_row['mrr']}",
))

# --- the fitted coefficient should point the right way ---------------------
hybrid = fit(ModelSpec("hybrid", use_water=True, use_human=True), net, sequence)
results.append(check(
    "hybrid fit puts the weight on the true layer",
    hybrid.params["beta_human"] > hybrid.params["beta_water"],
    f"beta_human={hybrid.params['beta_human']:.2f} "
    f"beta_water={hybrid.params['beta_water']:.2f}",
))

# --- the reverse case: plant a water signal instead ------------------------
truth_w = ModelSpec("waterway_only", use_water=True)
seq_w = simulate(truth_w, net, np.array([-4.0, 3.5]), [0], 18, np.random.default_rng(2))
rows_w = compare(net, seq_w, min_train_steps=2)
h_w = next(r for r in rows_w if r["model"] == "human_only")
w_w = next(r for r in rows_w if r["model"] == "waterway_only")
results.append(check(
    "water-driven invasion: waterway model wins (harness is not biased)",
    w_w["mrr"] > h_w["mrr"],
    f"MRR water={w_w['mrr']} vs human={h_w['mrr']}",
))

# --- power check -----------------------------------------------------------
power = can_this_experiment_work(net, truth, theta_true, seeds=[0], n_replicates=15)
print()
print("power check:", power)
results.append(check(
    "design recovers the generating layer more often than chance",
    power["recovery_rate"] > 1.0 / len(MODELS),
    f"recovery_rate={power['recovery_rate']} over {power['replicates']} replicates",
))

print()
print(f"{sum(results)}/{len(results)} passed")
sys.exit(0 if all(results) else 1)
