# "Isn't this just collecting online posts and drawing a map?"

A fair question, and worth being able to answer in one sentence at a poster
board. If the project stopped at *scraped Thai news → extracted mentions →
coloured map*, the answer would be yes: that is data journalism. Competent, but
not science, and a judge would be right to ask "so what?"

Here is what makes the difference.

## The extraction is the instrument, not the result

Building a telescope is not astronomy. But you cannot do the astronomy without
one, and nobody had built this particular telescope: there was no
subdistrict-resolution occurrence record for this species in Thailand. The
pipeline exists because the question needs more than 19 observations, not
because mining text is interesting in itself.

The paper is not "I built a text-mining pipeline." It is "here is what the
resulting record shows, and here is the hypothesis it rules in or out."

## Four things that separate this from reporting

**1. A hypothesis that came from somewhere else.** The claim that human
transport drives this invasion is not read off the map. It is derived from
independent evidence — published population genetics reporting multiple
introductions and regionally distinct populations with limited mixing.
Genetically separate populations were not connected by swimming fish. The text
corpus is then used to *test* a prediction that evidence implies, not to
generate a story after the fact.

**2. A comparison that could come out the other way.** `spread.py` fits two
competing models to the same data — waterway connectivity versus
aquaculture-mediated human transport — plus nulls including distance-only and
aquaculture-area-only. If the waterway model predicts as well as the hybrid,
the hypothesis is wrong. That outcome is possible, and reporting it would be a
legitimate result. A map cannot be wrong; a ranked prediction can.

**3. Out-of-sample prediction, not fit.** `experiment.py` withholds the later
part of the invasion sequence, fits on the earlier part, predicts which region
falls next, and scores the rank of the region that actually did. In-sample fit
would prove nothing — the hybrid model has more parameters and always fits
better. Prediction is not free that way: a parameter fitting noise makes the
next prediction worse.

**4. The instrument itself gets a measured accuracy.** The pipeline is validated
by independently recovering the documented provincial detections and reporting
how far in advance it would have flagged each. "Recovered N of 19, median M
months early, P% precision on a hand-labelled sample" is a measurement with a
number attached, not a claim about how nice the map looks.

## The strongest version: go and look

The project's `excess_provinces()` output lists places the corpus claims but the
official record never confirmed. The model produces a ranked list of subdistricts
with no recorded detection.

Visit some of them.

"My model ranked these 20 subdistricts; I visited 5 with no official record; I
found the species in 3" is a **prospective validated prediction**. That is not
reporting under any definition, and it is about as strong as a school project
gets. Finding nothing is also a result, and a much better one than not having
looked.

Commit the ranking in writing *before* the fieldwork. A prediction recorded in
advance and then checked is a different kind of evidence from one explained
afterwards, and judges know the difference.

## The honest caveat, which you should raise first

Run `can_this_experiment_work()` before believing any of this. At province-level
resolution the design is weakly powered: roughly 20 nodes and 10 invasion events
is not much to separate two correlated network layers with. The synthetic check
plants a known signal and measures how often the comparison finds it.

If that number is low, say so. "I established that province-level data cannot
answer this question, and here is the resolution at which it can" is a genuine
methodological finding, arrived at before spending a season on fieldwork rather
than after. It is a better result than a confident answer the design could not
have supported.

That check is also the complete answer to "how do you know your model isn't just
fitting noise?" — you tested it against a case where you knew the truth.

---

## Measured power, on synthetic data (2026-08)

Ran `can_this_experiment_work()` on synthetic networks with deliberately
discordant layers, planting a known human-transport signal. Six candidate models,
three of which contain the human layer — so **chance is 0.5**, not zero.

Individual cells were run at 10–15 replicates. At that size the estimates were
badly unstable: three near-identical runs at 24 nodes returned layer recovery of
**0.583, 0.700, and 0.933**. Any one of those quoted alone would have been
misleading. So the cells are pooled:

**Pooled across 6 cells, 66 replicates: layer recovery 0.682, 95% CI
[0.562, 0.782].** The interval excludes 0.5, so the design does identify the
generating mechanism above chance — modestly, but detectably.

By resolution band:

| nodes | layer recovery | 95% CI |
|---|---|---|
| 24 | 0.636 (14/22) | [0.43, 0.80] |
| 50–60 | 0.727 (16/22) | [0.52, 0.87] |
| 90–120 | 0.682 (15/22) | [0.47, 0.84] |

All three overlap heavily. **Spatial resolution has no detectable effect on
identifiability** in this simulation.

Two process notes worth carrying into the writeup. First, the instability at
n≈12 is itself the argument for the confidence intervals: without them, the
single 0.933 run would have looked like a clean success and the single 0.583 run
like a failed design. Second, pooling was decided *because* the cells disagreed,
not to reach a nicer number — the pooled estimate is lower than the best
individual cell, not higher.

What *does* work, from the same test suite: the fitted coefficient recovers the
right layer (β_human 2.84 vs β_water 0.51), and the reverse case behaves
correctly (plant a water signal, the waterway model wins). So the estimator is
sound; the **model-selection step** is what lacks power.

### What this implies for the project

Two conclusions, one negative and one actionable.

**Negative:** identification is real but weak — roughly 68% against a 50%
baseline — and pushing to finer spatial resolution does not improve it. A
real-data claim of the form "the hybrid model wins, therefore human transport"
must be reported with this power figure beside it. At 68% recovery, a single
model comparison landing on the hybrid is suggestive, not conclusive, and
saying so is the difference between a defensible result and an overclaim.

**Actionable:** the discriminating information lives entirely in region pairs
where the two layers disagree. Where the delta's water network and its trade
network coincide, both hypotheses predict the same thing no matter how many
nodes you add. So the lever is not resolution — it is **discordance**. Selecting
or oversampling regions connected by water but not commerce, and vice versa,
should raise power at any node count. `discordant_pairs()` counts them; the
accompanying experiment tests whether recovery actually tracks that count.

Run the power check with far more replicates before finalising — it is slow but
free, and an overnight run turns these intervals into something you can defend.

### Does discordance drive power? (25 replicates per cell)

Held the network at 60 nodes and varied how different the two layers are, from
identical (`alpha=0`) to fully distinct (`alpha=1`):

| alpha | corr(W_water, W_human) | layer recovery | 95% CI | lift over chance |
|---|---|---|---|---|
| 0.0 | 0.999 | 0.72 | [0.52, 0.86] | +0.22 |
| 0.35 | 0.818 | 0.80 | [0.61, 0.91] | +0.30 |
| 0.70 | 0.303 | 0.80 | [0.61, 0.91] | +0.30 |
| 1.00 | −0.041 | 0.84 | [0.65, 0.94] | +0.34 |

**Direction supports the hypothesis; the evidence does not yet settle it.**
Recovery rises monotonically as the layers separate, which is what the
discordance argument predicts. But every interval overlaps every other, so at
n=25 per cell this is a suggestive trend, not a demonstrated one. Reporting it
as established would be exactly the overclaim this document exists to avoid.

Two caveats on the table itself, both worth stating before a judge finds them:

- **`alpha=0` is degenerate.** When the layers are the same graph, "recovered
  the human layer" has no meaning — the water and human models are
  interchangeable by construction. The 0.72 there is measuring "a network model
  won", not "the right layer won". It is a floor, not a result.
- **The pair count is the wrong summary statistic.** `discordant_pairs()`
  returned 215 pairs for every network with `alpha > 0`, from correlation 0.82
  down to −0.04. It detects that discordance exists, not how much. Use
  `layer_confounding()` — the matrix correlation — as the headline
  identifiability number, and the pair list to inspect *which* regions carry the
  information.

### What to run before trusting any of this

The cells above are 10–25 replicates. That is enough to see a direction and not
enough to defend one. A decisive version is a single overnight job:

```python
from tilapia.experiment import can_this_experiment_work
power = can_this_experiment_work(network, truth_spec, theta, seeds, n_replicates=200)
```

At 200 replicates the intervals narrow to roughly ±0.07, which would separate
0.72 from 0.84. It costs nothing but wall-clock, and it converts the trend above
into either a finding or a retraction — both of which are publishable in a
school report, and only one of which is available if you skip it.

### The design conclusion, stated conservatively

Measure `layer_confounding()` on the real Thai network **first**. If the canal
network and the aquaculture-trade network turn out to be highly correlated —
which the geography of the Chao Phraya delta makes likely — then the model
comparison is weakly identified no matter how much text you mine or how fine
your spatial resolution, and the honest move is to restrict the analysis to the
subset of provinces where the layers diverge, and say why.

That is a real methodological decision, made from a measurement, before
collecting data. It is also the thing that separates this project from a map.
