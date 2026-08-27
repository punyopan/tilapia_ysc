"""Species distribution modelling from existing occurrence data.

The point of this module: you can train a real model on data that already
exists, with no hand-labelling at all. GBIF and iNaturalist hold occurrence
records for *Sarotherodon melanotheron* across its native West African range and
several invaded ranges; environmental rasters are free downloads.

THE ML QUESTION WORTH ASKING
----------------------------
Fitting a habitat model to Thai occurrences and reporting high accuracy is not
interesting -- it is nearly guaranteed and it proves little. The interesting
version is transfer:

    Train on the species' NATIVE range (and other invaded ranges).
    Predict Thailand. Validate against the Thai occurrence record, which the
    model never saw.

That is a geographically held-out test set, which is far harder and far more
honest than a random split. It is simultaneously a machine-learning question
(does a model transfer across a distribution shift?) and an ecological one
(is the realised niche conserved, or has the invasive population shifted into
conditions absent from the native range?). Either answer is a result.

THE THREE MISTAKES THAT INVALIDATE THIS KIND OF MODEL
-----------------------------------------------------
Every one of them inflates reported accuracy, and all three are common.

1. RANDOM CROSS-VALIDATION. Occurrence points are spatially autocorrelated:
   nearby points share environments. A random split puts near-duplicate points
   in train and test, so the model is scored on data it effectively memorised.
   `spatial_block_split()` exists for this, and `demonstrate_cv_inflation()`
   measures how large the illusion is.

2. UNCORRECTED SAMPLING BIAS. Presence-only records cluster where people look --
   near cities, roads, universities, and popular fishing spots. A model trained
   against uniformly random background learns *where surveyors go*, not where
   the fish lives. `target_group_background()` applies the standard correction.

3. EXTRAPOLATION WITHOUT SAYING SO. Transferring to a new region means
   predicting at environmental values the training data never covered.
   Predictions there are extrapolation, not inference. `novelty_mask()` flags
   which cells those are so they can be excluded or reported separately.

A judge who knows this literature will ask about all three. Handling them is
what separates the project from a tutorial.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class OccurrenceSet:
    """Presence points with environmental covariates attached.

    `region` labels the biogeographic range (e.g. "native_west_africa",
    "invaded_thailand"), and is what makes the cross-range experiment possible.
    """

    lon: np.ndarray
    lat: np.ndarray
    features: np.ndarray          # (n_points, n_covariates)
    region: np.ndarray            # (n_points,) region label per point
    feature_names: list[str]

    def __post_init__(self) -> None:
        n = len(self.lon)
        if not (len(self.lat) == len(self.region) == self.features.shape[0] == n):
            raise ValueError("lon, lat, region and features must have equal length")

    def subset(self, mask: np.ndarray) -> "OccurrenceSet":
        return OccurrenceSet(
            self.lon[mask], self.lat[mask], self.features[mask],
            self.region[mask], self.feature_names,
        )


def spatial_block_split(
    lon: np.ndarray,
    lat: np.ndarray,
    n_folds: int = 5,
    block_degrees: float = 1.0,
    seed: int = 0,
) -> np.ndarray:
    """Assign points to CV folds by spatial block, not at random.

    Points are grouped into square blocks of `block_degrees`, and whole blocks
    are assigned to folds. Neighbouring points therefore land in the same fold,
    so the model is never scored on a point that sits beside one it trained on.

    Choose `block_degrees` larger than the range over which your covariates are
    correlated. Too small and the leak persists; too large and folds become
    unbalanced. Report the value you used -- it is a real analysis choice, and a
    reviewer cannot judge the result without it.
    """
    block_x = np.floor(np.asarray(lon) / block_degrees).astype(int)
    block_y = np.floor(np.asarray(lat) / block_degrees).astype(int)

    blocks = list({(int(x), int(y)) for x, y in zip(block_x, block_y)})
    rng = np.random.default_rng(seed)
    rng.shuffle(blocks)
    block_fold = {block: i % n_folds for i, block in enumerate(blocks)}

    return np.array([block_fold[(int(x), int(y))] for x, y in zip(block_x, block_y)])


def target_group_background(
    presence_lon: np.ndarray,
    presence_lat: np.ndarray,
    target_group_lon: np.ndarray,
    target_group_lat: np.ndarray,
    n_background: int = 10000,
    seed: int = 0,
) -> tuple[np.ndarray, np.ndarray]:
    """Draw background points from where surveyors actually sampled.

    The standard correction for presence-only sampling bias. Instead of
    uniformly random background, sample from the recorded locations of a
    *target group* -- other species collected by the same kind of observer with
    the same kind of effort. For a brackish-water fish, the target group is
    other fish records in the same databases.

    The logic: background points then carry the same spatial bias as the
    presences, so the model can no longer separate the two using "somewhere a
    person went" and must use environment instead.

    Skipping this is the single most common reason a species distribution model
    reports high accuracy while having learned road networks.
    """
    rng = np.random.default_rng(seed)
    n_available = len(target_group_lon)
    if n_available == 0:
        raise ValueError("target group is empty -- cannot correct for bias without it")

    idx = rng.choice(n_available, size=min(n_background, n_available), replace=False)
    return np.asarray(target_group_lon)[idx], np.asarray(target_group_lat)[idx]


def novelty_mask(
    train_features: np.ndarray, predict_features: np.ndarray, tolerance: float = 0.0
) -> np.ndarray:
    """Flag prediction points outside the training data's environmental range.

    Returns True where at least one covariate falls beyond the training
    min/max (a simple univariate MESS-style check). Those cells are
    extrapolation: the model has no evidence there and its output is an
    artefact of whatever the learner does off the end of its data.

    Report the fraction flagged. For a native-to-invaded transfer it is often
    substantial, and stating it honestly is stronger than a map that quietly
    extrapolates across half of Thailand.
    """
    lo = train_features.min(axis=0) - tolerance
    hi = train_features.max(axis=0) + tolerance
    return ((predict_features < lo) | (predict_features > hi)).any(axis=1)


def cross_range_split(
    data: OccurrenceSet, test_region: str
) -> tuple[OccurrenceSet, OccurrenceSet]:
    """Train on every other region, test on `test_region`.

    The headline experiment. A model that transfers from the native range to
    Thailand has learned something about the species; one that only works
    within a region has learned that region.
    """
    test_mask = data.region == test_region
    if not test_mask.any():
        raise ValueError(f"no points in region {test_region!r}")
    return data.subset(~test_mask), data.subset(test_mask)


# --------------------------------------------------------------------------


def _auc(scores: np.ndarray, labels: np.ndarray) -> float:
    """AUC by rank, no sklearn dependency."""
    order = np.argsort(scores)
    ranks = np.empty(len(scores), dtype=float)
    ranks[order] = np.arange(1, len(scores) + 1)

    n_pos = float(labels.sum())
    n_neg = float(len(labels) - n_pos)
    if n_pos == 0 or n_neg == 0:
        return float("nan")
    return float((ranks[labels == 1].sum() - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg))


def demonstrate_cv_inflation(
    lon: np.ndarray,
    lat: np.ndarray,
    features: np.ndarray,
    labels: np.ndarray,
    fit_predict,
    n_folds: int = 5,
    block_degrees: float = 1.0,
    seed: int = 0,
) -> dict[str, float]:
    """Score the same model under random CV and under spatial-block CV.

    `fit_predict(X_train, y_train, X_test) -> scores` keeps this independent of
    which learner you use.

    The gap between the two numbers is a result in its own right, and a good one
    to lead with: it shows that the accuracy figure most projects report is an
    artefact of the validation scheme rather than a property of the model. If
    random CV gives 0.95 and blocked CV gives 0.78, the honest headline is 0.78
    and the 0.95 is the finding about method.
    """
    rng = np.random.default_rng(seed)

    random_folds = rng.integers(0, n_folds, size=len(labels))
    spatial_folds = spatial_block_split(lon, lat, n_folds, block_degrees, seed)

    results = {}
    for name, folds in (("random_cv_auc", random_folds), ("spatial_cv_auc", spatial_folds)):
        aucs = []
        for fold in range(n_folds):
            train, test = folds != fold, folds == fold
            if test.sum() == 0 or len(np.unique(labels[test])) < 2:
                continue
            if len(np.unique(labels[train])) < 2:
                continue
            scores = fit_predict(features[train], labels[train], features[test])
            aucs.append(_auc(np.asarray(scores), labels[test]))
        results[name] = float(np.nanmean(aucs)) if aucs else float("nan")

    results["inflation"] = results["random_cv_auc"] - results["spatial_cv_auc"]
    return results
