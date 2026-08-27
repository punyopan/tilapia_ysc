# Kangdam — Thai geographic entity resolution for invasive species reporting

**ต.บางแก้ว อยู่จังหวัดไหน**

A hybrid neural-symbolic system for extracting and geolocating spatial event
records from Thai-language text, evaluated on blackchin tilapia
(*Sarotherodon melanotheron*, ปลาหมอคางดำ) spread reporting.

> **YSC: Computer Science → CSBI (Computational Biology and Bioinformatics).**
> Literature mining generates the data; the spread and reinvasion model is the
> contribution. See `docs/cs-subcategory.md` for why CSBI over CSAI or CSSD, and
> `docs/cs-track.md` for the evaluation plan.

## The problem

Extracting geolocated records from low-resource-language text is poorly solved,
and Thai is specifically hard:

| | why standard methods fail |
|---|---|
| no inter-word spacing | `ต.บางแก้ว` / `ตำบลบางแก้ว` / `ตำบล บางแก้ว` are one place, and none string-match |
| name collision | many provinces have a `ต.บางแก้ว`; the string alone cannot resolve it |
| `อ.เมือง` | gazetteers write `เมือง<province>`, text writes a bare `อ.เมือง` — neither exact nor fuzzy matching connects them |
| colloquial aliases | `แม่กลอง` for สมุทรสงคราม; no edit distance recovers it |

## The claim being tested

The architecture is hybrid: **the language model reports place names verbatim
and never resolves them**; a deterministic gazetteer matcher does resolution.
The obvious alternative is to ask the model for the administrative code
directly.

> **H0** — asking the model directly is as accurate as the hybrid pipeline.
> **H1** — the hybrid is more accurate, and the gap concentrates in ambiguous cases.

Measured by `benchmark.py` against five systems, per ambiguity type, with a
**fabrication rate** on items whose correct answer is *"cannot be resolved"* — a
system that always answers scores well on resolvable items and invents locations
for the rest.

## Extrinsic evaluation

Outputs feed a two-layer spread model for the species, whose official record
covers only ~19 provinces. This measures how geolocation error propagates into
downstream scientific inference — connecting NLP accuracy to applied conclusions,
which most extraction work cannot do.

```
Thai text ──▶ LLM reports names ──▶ deterministic resolver ──▶ spread model
              (schema + grounding)   (hierarchy, aliases)      (extrinsic eval)
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
src/tilapia/benchmark.py       EVALUATION HARNESS — the CS contribution
src/tilapia/validate.py        recall, lead time, precision, excess
src/tilapia/spread.py          the two-layer model: water vs human transport
src/tilapia/experiment.py      out-of-sample test + power check
src/tilapia/allocate.py        risk map -> survey plan under a fixed budget
src/tilapia/removal.py         where clearing fish stays cleared vs refills
data/reference/                gazetteer + ground truth (you assemble these)
docs/cs-subcategory.md         which CS subcategory, and why (read first)
docs/cs-track.md               evaluation plan for the resolver component
docs/abstract.md               title and abstract, proposal + results versions
docs/how-this-helps.md         what it changes in the real world, measured
docs/removal.md                "isn't the real problem getting rid of them?"
docs/why-this-is-science.md    the "isn't this just a map?" answer, with measured power
docs/pipeline.md               design rationale and known limitations
docs/compute.md                what hardware this needs (spoiler: a laptop)
tests/                         6 suites — run them before trusting anything
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

**The one thing that gates the CS result: a hand-labelled test set of ~400 real
Thai place mentions.** Without it there is no measured contribution, only an
assertion. Labelling protocol and ambiguity taxonomy are in `docs/cs-track.md`.

Two files in `data/reference/` are also yours to assemble:

- **`gazetteer.csv`** — Thai administrative units with codes. Sources in
  `data/reference/README.md`. Keep the codes; they join everything downstream.
- **`official_detections.csv`** — the ground truth. Every result is measured
  against it, so every row needs a citation you can show a judge. Do not guess
  dates; record real precision rather than padding a year into a day.

## Status

Method built and tested end to end on synthetic data. **No corpus collected, no
ground truth entered, no real results.** What is verified so far:

- Thai place-name resolution, including subdistrict collision and bare อ.เมือง
- the benchmark harness: full resolver beats exact-match and greedy-fuzzy
  baselines on synthetic labels, with the gap in the targeted ambiguity types,
  and ablating context or aliases measurably hurts
- the spread model recovers a planted signal, in both directions
- identifiability measured at 0.682 [0.562, 0.782] against a 0.5 baseline —
  real but weak, and *not* improved by finer spatial resolution
- removal durability collapses past ~60% network saturation

Two findings recorded against interest, both asserted in the tests: the
allocation gain multiple is an artifact of an unmeasured parameter (4x-107x),
and the full model beats a trivial assets-only heuristic by only ~1.06x. Nearly
all the value is in not defaulting to the worst-affected areas.

```
python tests/test_benchmark.py   #  7/7   <- the CS contribution
python tests/test_geocode.py     # 10/10
python tests/test_bakeoff.py     #  7/7
python tests/test_allocate.py    #  7/7
python tests/test_removal.py     #  6/6
python tests/test_experiment.py  #  7/7   (slow — many model fits)
```
