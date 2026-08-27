# Kangdam — where removing blackchin tilapia actually lasts

**กำจัดตรงไหนถึงจะอยู่ถาวร**

Distinguishing places where clearing *Sarotherodon melanotheron* (ปลาหมอคางดำ)
is permanent from places where it is recurring maintenance — by mining
Thai-language text for occurrence records, then fitting a two-layer spread model
to them.

## Why

Removal is the goal. National eradication is not achievable: an open, tidally
connected canal network across many provinces, a euryhaline species, a
mouthbrooder with high juvenile survival. Documented eradications of established
fish happen in closed systems, or very shortly after arrival.

But removal is **two problems, not one**. Clearing a site inside a dense,
well-connected invaded network buys a temporary density drop — neighbours refill
it. Clearing a weakly connected site can be permanent. The quantity separating
them is *reinvasion pressure*, which a spread model computes and a map of current
occupancy cannot.

Fitting that model needs more than the ~19 province-level detections on record —
too few, spatially autocorrelated, and time-ordered. So the pipeline mines Thai
news, government bulletins, and community posts for dated, place-named
occurrences, and proves the result trustworthy by independently recovering the
official 19 and measuring how much *earlier* it would have flagged each.

```
Thai text ──▶ occurrence records ──▶ two-layer spread model ──▶ where removal lasts
              (validated vs the 19)    (water vs human transport)   + survey priority
```

## Layout

```
prompts/extraction_th.md       the extraction prompt (versioned — it defines the corpus)
src/tilapia/schema.py          record schemas and the distinctions that matter
src/tilapia/prefilter.py       free keyword screen — runs before any API call
src/tilapia/extract.py         documents -> records via Claude (batch + single)
src/tilapia/providers.py       provider-agnostic extraction (Anthropic, DeepSeek)
src/tilapia/bakeoff.py         compare providers on the dev set, mostly for free
src/tilapia/geocode.py         Thai place names -> official admin units
src/tilapia/validate.py        recall, lead time, precision, excess
src/tilapia/spread.py          the two-layer model: water vs human transport
src/tilapia/experiment.py      out-of-sample test + power check
src/tilapia/allocate.py        risk map -> survey plan under a fixed budget
src/tilapia/removal.py         where clearing fish stays cleared vs refills
data/reference/                gazetteer + ground truth (you assemble these)
docs/abstract.md               title and abstract, proposal + results versions
docs/how-this-helps.md         what it changes in the real world, measured
docs/removal.md                "isn't the real problem getting rid of them?"
docs/why-this-is-science.md    the "isn't this just a map?" answer, with measured power
docs/pipeline.md               design rationale and known limitations
docs/compute.md                what hardware this needs (spoiler: a laptop)
tests/                         5 suites — run them before trusting anything
```

## Setup

```bash
pip install -e .
export ANTHROPIC_API_KEY=...        # or: ant auth login
python tests/test_geocode.py        # 10/10 expected
```

## Use

```python
import anthropic
from tilapia.prefilter import apply_screen
from tilapia.extract import estimate_cost, submit_batch, await_batch, collect_batch
from tilapia.geocode import Gazetteer
from tilapia.validate import eligible_records, evaluate_recall, summarise

client = anthropic.Anthropic()

# 0. screen for free, then price the run before paying for it
kept, rejected = apply_screen(raw_documents)
print(estimate_cost(client, documents))

# 1. extract (batch: 50% cost, nothing here is latency-sensitive)
batch_id = submit_batch(client, documents)
await_batch(client, batch_id)
extractions, errors = collect_batch(client, batch_id)

# 2. resolve place names deterministically
gaz = Gazetteer.from_csv("data/reference/gazetteer.csv")

# 3. validate against the official record
print(summarise(evaluate_recall(eligible_records(records), truth)))
```

Costs about **$18 end to end** — see `docs/compute.md` for the breakdown and the
levers. Iterate the prompt on a ~150-document dev set; run the full corpus twice,
not eight times.

## Before you run anything

Two files in `data/reference/` are yours to assemble, and the project is inert
without them:

- **`gazetteer.csv`** — Thai administrative units with codes. Sources in
  `data/reference/README.md`. Keep the codes; they join everything downstream.
- **`official_detections.csv`** — the ground truth. Every result is measured
  against it, so every row needs a citation you can show a judge. Do not guess
  dates; record real precision rather than padding a year into a day.

## Status

Method built and tested end to end on synthetic data. **No corpus collected, no
ground truth entered, no real results.** What is verified so far:

- Thai place-name resolution, including subdistrict collision and bare อ.เมือง
- the spread model recovers a planted signal, in both directions
- identifiability measured at 0.682 [0.562, 0.782] against a 0.5 baseline —
  real but weak, and *not* improved by finer spatial resolution
- removal durability collapses past ~60% network saturation

Two findings recorded against interest, both asserted in the tests: the
allocation gain multiple is an artifact of an unmeasured parameter (4x-107x),
and the full model beats a trivial assets-only heuristic by only ~1.06x. Nearly
all the value is in not defaulting to the worst-affected areas.

```
python tests/test_geocode.py     # 10/10
python tests/test_bakeoff.py     #  7/7
python tests/test_allocate.py    #  7/7
python tests/test_removal.py     #  6/6
python tests/test_experiment.py  #  7/7   (slow — many model fits)
```
