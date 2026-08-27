"""Species-distribution modelling utilities, on synthetic spatial data.

The headline test measures how much random cross-validation inflates accuracy
when occurrence points are spatially autocorrelated. That inflation is the
single most common way a habitat model reports a number it has not earned.
"""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tilapia.sdm import (  # noqa: E402
    OccurrenceSet, cross_range_split, demonstrate_cv_inflation, novelty_mask,
    spatial_block_split, target_group_background,
)


def make_spatial_data(n=900, seed=3):
    """Presence driven by a smooth environmental field plus spatially
    correlated residual structure -- i.e. real ecological data."""
    rng = np.random.default_rng(seed)
    lon = rng.uniform(95, 106, n)
    lat = rng.uniform(5, 20, n)

    # Smooth environmental surface (what genuinely drives suitability).
    env1 = np.sin(lon / 1.5) + np.cos(lat / 1.5)
    env2 = (lon - 100) / 5 + rng.normal(0, 0.15, n)

    # Spatially correlated residual: local patches favourable for reasons the
    # covariates do not capture. This is what random CV lets a model memorise.
    patch = np.sin(lon * 3.0) * np.cos(lat * 3.0)

    logit = 2.0 * env1 + 0.8 * env2 + 2.5 * patch
    prob = 1 / (1 + np.exp(-logit))
    labels = (rng.random(n) < prob).astype(int)

    features = np.column_stack([env1, env2])
    return lon, lat, features, labels


def knn_fit_predict(k=5):
    """Nearest-neighbour scorer: flexible enough to memorise local structure,
    which is exactly the behaviour random CV fails to penalise."""
    def fit_predict(X_train, y_train, X_test):
        scores = []
        for row in X_test:
            d = np.sqrt(((X_train - row) ** 2).sum(axis=1))
            nearest = np.argsort(d)[:k]
            scores.append(y_train[nearest].mean())
        return np.array(scores)
    return fit_predict


results = []


def check(label, cond, detail=""):
    print(f"[{'PASS' if cond else 'FAIL'}] {label}{'  -- ' + detail if detail else ''}")
    return cond


lon, lat, features, labels = make_spatial_data()

# --- spatial blocking -------------------------------------------------------
folds = spatial_block_split(lon, lat, n_folds=5, block_degrees=2.0)
results.append(check(
    "spatial blocking assigns every point to a fold",
    len(folds) == len(lon) and set(np.unique(folds)) <= set(range(5)),
    f"{len(np.unique(folds))} folds used",
))
same_block = (np.floor(lon / 2.0).astype(int) == np.floor(lon[0] / 2.0).astype(int)) & \
             (np.floor(lat / 2.0).astype(int) == np.floor(lat[0] / 2.0).astype(int))
results.append(check(
    "neighbouring points share a fold (that is the whole point)",
    len(np.unique(folds[same_block])) == 1,
    f"{same_block.sum()} points in the same block, all in fold {folds[same_block][0]}",
))

# --- THE HEADLINE: WHEN does random CV inflate accuracy? -------------------
# Not always. The effect depends on whether the model can exploit spatial
# proximity, which is a property of the feature set, not of the data alone.
configs = {
    "env only": features,
    "env + coordinates": np.column_stack([features, lon, lat]),
    "coordinates only": np.column_stack([lon, lat]),
}
print()
print(f"{'feature set':<24}{'random':<10}{'spatial':<10}{'inflation'}")
print("-" * 54)
inflation = {}
for name, X in configs.items():
    cv = demonstrate_cv_inflation(lon, lat, X, labels, knn_fit_predict(),
                                  n_folds=5, block_degrees=2.0)
    inflation[name] = cv
    print(f"{name:<24}{cv['random_cv_auc']:<10.3f}"
          f"{cv['spatial_cv_auc']:<10.3f}{cv['inflation']:+.3f}")
print()

results.append(check(
    "environment-only features: random CV is roughly honest",
    abs(inflation["env only"]["inflation"]) < 0.02,
    f"inflation {inflation['env only']['inflation']:+.3f} -- generalisable covariates transfer",
))
results.append(check(
    "adding coordinates makes random CV substantially optimistic",
    inflation["env + coordinates"]["inflation"] > 0.03,
    f"inflation {inflation['env + coordinates']['inflation']:+.3f}",
))
results.append(check(
    "the WORST model looks BEST under random CV -- the trap, quantified",
    inflation["coordinates only"]["random_cv_auc"] > inflation["env only"]["random_cv_auc"]
    and inflation["coordinates only"]["spatial_cv_auc"] < inflation["env only"]["spatial_cv_auc"],
    f"coords-only scores {inflation['coordinates only']['random_cv_auc']:.3f} random "
    f"but {inflation['coordinates only']['spatial_cv_auc']:.3f} spatial",
))

# --- bias-corrected background ---------------------------------------------
rng = np.random.default_rng(0)
tg_lon = np.concatenate([rng.normal(100.5, 0.3, 400), rng.normal(98.9, 0.3, 300)])
tg_lat = np.concatenate([rng.normal(13.7, 0.3, 400), rng.normal(18.8, 0.3, 300)])
bg_lon, bg_lat = target_group_background(lon, lat, tg_lon, tg_lat, n_background=200)
results.append(check(
    "background is drawn from surveyed locations, not uniformly",
    len(bg_lon) == 200 and bg_lon.std() < np.asarray(lon).std(),
    f"background sd {bg_lon.std():.2f} vs uniform-presence sd {np.asarray(lon).std():.2f}",
))
try:
    target_group_background(lon, lat, np.array([]), np.array([]))
    results.append(check("empty target group raises rather than silently degrading", False))
except ValueError:
    results.append(check("empty target group raises rather than silently degrading", True))

# --- extrapolation flagging -------------------------------------------------
train_f = features[:400]
novel = novelty_mask(train_f, features[400:])
results.append(check(
    "novelty mask flags points outside the training envelope",
    novel.dtype == bool and len(novel) == len(features) - 400,
    f"{novel.mean():.1%} of prediction points are extrapolation",
))
far = np.array([[99.0, 99.0]])
results.append(check(
    "an obviously out-of-range point is flagged",
    bool(novelty_mask(train_f, far)[0]),
))

# --- cross-range transfer split --------------------------------------------
region = np.where(lat > 12, "invaded_thailand", "native_west_africa")
data = OccurrenceSet(lon, lat, features, region, ["env1", "env2"])
train, test = cross_range_split(data, "invaded_thailand")
results.append(check(
    "cross-range split holds out an entire region",
    set(np.unique(test.region)) == {"invaded_thailand"}
    and "invaded_thailand" not in set(np.unique(train.region)),
    f"train n={len(train.lon)}, held-out n={len(test.lon)}",
))

print()
print(f"{sum(results)}/{len(results)} passed")
sys.exit(0 if all(results) else 1)
