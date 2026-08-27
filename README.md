# Blackchin tilapia spread in Thailand — occurrence mining

Reconstructing the invasion record of *Sarotherodon melanotheron* (ปลาหมอคางดำ)
in Thailand from Thai-language text, to get enough observations to fit and
validate a spread model.

## Why

The official record is ~19 provinces with confirmation dates. That is too few
observations to support a spread model — they are province-level, spatially
autocorrelated, and ordered in time, and no modelling technique rescues nineteen
points. The bottleneck is data, not method.

Thai news, government bulletins, and local fishing and farming groups contain
thousands of dated, place-named references to this species. This repository turns
that text into structured occurrence records, then proves the result is
trustworthy by independently recovering the official 19 from it — and measuring
how much *earlier* it would have flagged each province.

## Layout

```
prompts/extraction_th.md       the extraction prompt (versioned — it defines the corpus)
src/tilapia/schema.py          record schemas and the distinctions that matter
src/tilapia/extract.py         documents -> records via Claude (batch + single)
src/tilapia/geocode.py         Thai place names -> official admin units
src/tilapia/validate.py        recall, lead time, precision, excess
data/reference/                gazetteer + ground truth (you assemble these)
docs/pipeline.md               design rationale and known limitations
docs/compute.md                what hardware this needs (spoiler: a laptop)
tests/test_geocode.py          the Thai matching cases that actually break
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
from tilapia.extract import SourceDocument, submit_batch, await_batch, collect_batch
from tilapia.geocode import Gazetteer
from tilapia.validate import eligible_records, evaluate_recall, summarise

client = anthropic.Anthropic()

# 1. extract (batch: 50% cost, nothing here is latency-sensitive)
batch_id = submit_batch(client, documents)
await_batch(client, batch_id)
extractions, errors = collect_batch(client, batch_id)

# 2. resolve place names deterministically
gaz = Gazetteer.from_csv("data/reference/gazetteer.csv")

# 3. validate against the official record
print(summarise(evaluate_recall(eligible_records(records), truth)))
```

## Before you run anything

Two files in `data/reference/` are yours to assemble, and the project is inert
without them:

- **`gazetteer.csv`** — Thai administrative units with codes. Sources in
  `data/reference/README.md`. Keep the codes; they join everything downstream.
- **`official_detections.csv`** — the ground truth. Every result is measured
  against it, so every row needs a citation you can show a judge. Do not guess
  dates; record real precision rather than padding a year into a day.

## Status

Pipeline scaffolding, tested on synthetic gazetteer data. No corpus collected,
no ground truth entered, no results. The geocoder's ambiguity handling is real
and passing; everything else awaits data.
