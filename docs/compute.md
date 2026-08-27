# What compute this actually needs

Short version: a laptop, plus an API bill. No HPC allocation, no GPU.

This is worth writing down because the instinct to reach for a supercomputer is
strong and, here, wrong — and because a judge who asks "what did you run this
on?" should get a specific answer.

## Per component

| Component | Real requirement |
|---|---|
| Text extraction | Zero local compute. The model runs on someone else's hardware; you are issuing HTTP requests. Bounded by API cost and rate limits, not FLOPs. |
| Geocoding | String matching over ~7,000 gazetteer rows. Seconds. |
| Spread graph | Thailand has 77 provinces, ~930 districts, ~7,300 subdistricts. A graph of 7,300 nodes is small — diffusion, fitting, and leave-one-out validation all run in seconds to minutes on a laptop. |
| Surveillance allocation | An optimisation over the same small graph. Minutes. |
| Species classifier *(if kept)* | Fine-tuning MobileNet on a few thousand images: one free Colab T4 session, well under an hour. |
| Pond segmentation from Sentinel-2 *(if added)* | The only component that could want a real GPU, and even then it is a single-GPU U-Net on a modest tile set — a Colab session, not a cluster. |

Nothing here parallelises across nodes, because nothing here is large. A
supercomputer allocation would sit idle.

There is a presentation argument too: running a 7,000-node graph problem on
national HPC infrastructure signals that you have not sized your own problem.
The stronger claim is the opposite one — *this runs on a laptop, which is why a
provincial fisheries office could actually run it.* That framing turns a
limitation into a deployment story.

## The cost that is real: API tokens

This is the budget line that matters, so estimate it before committing.

Run `extract.estimate_cost()` before paying for anything — it measures real
input tokens with `count_tokens` on a sample of your own documents. Thai
tokenises more heavily than English, so do not estimate from character counts.

The pipeline's defaults are set for a student budget. Five levers, and they
multiply:

**1. Screen before the API sees anything (free).** `prefilter.py` drops documents
that cannot contain a located record — wrong species, or no place reference at
all. This is free and it multiplies with every lever below: halving the corpus
halves the bill under any model. Read 50 rejected documents once
(`screen_recall_check`) to confirm it is not discarding real records.

**2. Iterate on a dev set, not the corpus.** Prompt work needs ~150 documents,
not 5,000. Run the full corpus once in the middle and once at the end. This is
the largest single saving and it is purely a workflow choice.

**3. Batch API: 50% off.** Nothing here is latency-sensitive. `submit_batch()`
is the default path for this reason.

**4. Cache the system prompt.** Long, and identical across every call.

**5. Low effort, and the bulk model.** This is mechanical reading against a
strict schema, not a reasoning problem. High effort spends output tokens — the
expensive side, 5× input — deliberating over a task the schema has already
constrained. `BULK_MODEL` defaults to Haiku 4.5 for the same reason: structured
extraction against a strict schema is among the most model-robust tasks there
is, and the prompt and schema are doing the real work.

That last one is a measurement, not an assumption. Run your 150-document dev set
through both `BULK_MODEL` and `ADJUDICATION_MODEL`, compare against your
hand-labels, and keep the cheap one only if it holds up. The specific thing to
check is whether it still separates `named_explicit` from `named_ambiguous` on
bare ปลาหมอ — that distinction is the most delicate judgement in the prompt and
the first thing a weaker model would flatten. A cheaper extraction that silently
loses it costs more in validity than it saves in baht.

### What that actually comes to

For ~4,000 scraped documents reducing to ~1,500 after screening, ~3,000 input
tokens each, ~400 output tokens at low effort:

| | |
|---|---|
| Dev-set iteration (150 docs × ~8 prompt versions, synchronous) | ~$6 |
| Reference pass on the dev set with Opus 5, to validate the bulk model | ~$4 |
| Two full corpus runs on Haiku 4.5, batched | ~$8 |
| **Total** | **~$18** |

Running the *entire* corpus on Opus 5 instead, still screened and batched at low
effort, is roughly $19 per run — so even the expensive version lands near $45,
not the hundreds it would cost with none of the levers applied.

Before paying at all, check what you already have: YSC is run by NECTEC and
provides resources to finalists, and Anthropic runs credit programmes for
students and researchers. Both are worth an email before you spend anything.

## When an allocation *would* help

One case: if you cannot use a hosted API at all — cost, or a rule about where
data goes — and you self-host an open Thai-capable model instead. That needs one
GPU with enough memory for the model, which is a very different ask from an HPC
allocation, and it costs you the structured-output guarantees this pipeline
relies on.

If you have access to NSTDA/ThaiSC resources anyway, the part worth having is
not the FLOPs. It is the affiliation: access to people who know the DOF data
landscape, and a plausible route to the aquaculture statistics and buyback
records that this project would benefit from far more than from compute.

## Using a different provider

The pipeline is provider-agnostic (`providers.py`). Everything carrying
scientific weight — the schema, the prompt, the geocoder, the validation design
— is independent of who serves the model; only the call differs.

Two things to weigh before switching, neither of which is about benchmark
scores:

**Schema enforcement differs, and it costs real money.** The Anthropic path
constrains generation against the JSON schema, so valid output is the normal
case. An OpenAI-compatible JSON mode guarantees *valid JSON*, not JSON matching
your schema — wrong enum values and missing fields happen at some rate, so
`DeepSeekProvider` retries on validation failure and counts how often. A
provider 4× cheaper per token that needs 1.3 attempts per document is not 4×
cheaper, and if the retries cluster on the ambiguous-species documents it is
worse in a way the price table cannot show you.

**Thai is the actual question.** This task needs fine lexical discrimination in
Thai specifically — holding ปลาหมอคางดำ apart from a bare ปลาหมอ — plus
Buddhist-Era date handling. General capability scores do not tell you whether a
model does that. Your dev set does.

### Deciding it

`bakeoff.py` runs the comparison. Do the free half first:

```python
from tilapia.bakeoff import run_provider, compare, disagreements, cost_per_record

runs = [run_provider(p, dev_docs) for p in (provider_a, provider_b)]
compare(runs)                      # no hand labels needed
queue = disagreements(*runs)       # label these first
```

`compare()` needs no labelled data and can already disqualify a provider. Watch
two numbers:

- **Grounding rate** — the share of records whose evidence quote is verbatim in
  the source. Low means fabrication, and no price makes that acceptable.
- **`ambiguous_share`** — the share of records marked `named_ambiguous`. A model
  reporting near-zero is not being decisive, it is collapsing the distinction
  that keeps the wrong fish out of your corpus. Near-zero is a red flag, not a
  clean result.

Then hand-label the disagreements rather than a random sample. Where both
providers agree they are usually both right; where they differ, one is wrong and
the document is informative. That gets a usable comparison for a fraction of the
reading, and the disagreement set is itself a map of where this task is hard —
worth a paragraph in the report.

Finish with `cost_per_record()`, which uses each provider's own reported token
usage so retries are counted. Cost per validated record is the honest
comparison; price per million tokens is not.

### Keep the number in perspective

After screening, batching, low effort and dev-set discipline, the whole project
is around $18. A 4× cheaper provider saves roughly $13 — real, but no longer the
dominant cost of anything. Spend the effort where it pays: an afternoon of
provider bake-off is worth it only if you were going to hand-label the dev set
anyway, which you were.

One genuine non-cost argument for an open-weight model: you can state exactly
which weights produced your corpus, and a reader could reproduce it without a
commercial API. That is a legitimate reproducibility claim and worth a sentence
in the writeup if you go that way. It is also the one scenario where an HPC
allocation earns its place — see above.
