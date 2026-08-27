# Kangdam — where removing blackchin tilapia actually lasts

**กำจัดตรงไหนถึงจะอยู่ถาวร**

A computational model of spread and reinvasion in *Sarotherodon melanotheron*
(ปลาหมอคางดำ), built on Thai-language literature mining, to distinguish sites
where removal is permanent from sites where it is recurring maintenance.

> **YSC: Computer Science → CSBI (Computational Biology and Bioinformatics).**
> Literature mining generates the dataset; the spread and reinvasion model is
> the contribution. See `docs/cs-subcategory.md` for why CSBI over CSAI or CSSD.

## The question

Removal is the goal, but national eradication is not achievable: an open,
tidally connected canal network, a euryhaline species, a mouthbrooder with high
juvenile survival.

So the computational-biology question is **where is removal permanent?**

Clearing a site strongly connected to dense invaded areas yields only temporary
reduction — neighbouring populations refill it. Clearing a weakly connected site
can be permanent. The governing quantity is **reinvasion pressure**: computable
from a fitted spread model, unreadable from a map of current occupancy.

Measured on simulated networks, that window **closes past ~60% saturation** —
beyond it every site refills and no targeting recovers durability.

## The data problem, and literature mining

Fitting the model needs more than the ~19 province-level detections on record.
So a schema-constrained language model extracts dated, place-named occurrence
records from Thai news, government bulletins, and community posts — the standard
bioinformatics practice of mining literature to build a biological dataset.

Two design rules make the output trustworthy:

- every record carries a source quote **verified character-for-character**, as a
  hallucination control
- the model reports place names **verbatim and never resolves them**; a
  deterministic matcher assigns subdistrict codes

Thai makes that second step genuinely hard:

| | why standard methods fail |
|---|---|
| no inter-word spacing | `ต.บางแก้ว` / `ตำบลบางแก้ว` / `ตำบล บางแก้ว` are one place, none string-match |
| name collision | many provinces have a `ต.บางแก้ว`; the string alone cannot resolve it |
| `อ.เมือง` | gazetteers write `เมือง<province>`, text writes bare `อ.เมือง` |
| colloquial aliases | `แม่กลอง` for สมุทรสงคราม; no edit distance recovers it |

`benchmark.py` measures the resolver against five systems per ambiguity type,
including a **fabrication rate** on items whose correct answer is *"cannot be
resolved"* — a system that always answers scores well on resolvable items and
invents locations for the rest.

```
Thai text ──▶ occurrence records ──▶ spread + reinvasion model ──▶ where removal lasts
              (mined, grounded,       (two-layer network,           + when the window
               deterministically       out-of-sample validated)      closes
               geocoded)
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
src/tilapia/benchmark.py       resolver evaluation: baselines, ablations, fabrication
src/tilapia/distill.py         teacher -> student training data (only if CSAI)
src/tilapia/sdm.py             habitat model from GBIF: spatial CV, bias, novelty
src/tilapia/validate.py        recall, lead time, precision, excess
src/tilapia/spread.py          the two-layer model: water vs human transport
src/tilapia/experiment.py      out-of-sample test + power check
src/tilapia/allocate.py        risk map -> survey plan under a fixed budget
src/tilapia/removal.py         where clearing fish stays cleared vs refills
data/reference/                gazetteer + ground truth (you assemble these)
docs/cs-subcategory.md         which CS subcategory, and why (read first)
docs/csai-track.md             what a real CSAI project would have to be
docs/existing-data.md          training ML on data that already exists
docs/cs-track.md               evaluation plan for the resolver component
docs/abstract.md               title and abstract, proposal + results versions
docs/how-this-helps.md         what it changes in the real world, measured
docs/removal.md                "isn't the real problem getting rid of them?"
docs/why-this-is-science.md    the "isn't this just a map?" answer, with measured power
docs/pipeline.md               design rationale and known limitations
docs/compute.md                what hardware this needs (spoiler: a laptop)
tests/                         8 suites — run them before trusting anything
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

**Gate on the resolver result: a hand-labelled test set of ~400 real Thai place
mentions** — protocol and ambiguity taxonomy in `docs/cs-track.md`.

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
python tests/test_benchmark.py   #  7/7
python tests/test_distill.py     #  8/8
python tests/test_sdm.py         # 10/10
python tests/test_geocode.py     # 10/10
python tests/test_bakeoff.py     #  7/7
python tests/test_allocate.py    #  7/7
python tests/test_removal.py     #  6/6
python tests/test_experiment.py  #  7/7   (slow — many model fits)
```
