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

Rough arithmetic for a 5,000-document corpus, Thai news articles averaging
~3,000 input tokens each after the cached system prompt, ~800 output tokens each:

```
input     5,000 × 3,000  = 15M tokens
output    5,000 ×   800  =  4M tokens
```

At Claude Opus 5 list rates ($5/M input, $25/M output) that is ~$175 —
and both levers below apply on top of each other:

- **Batch API: 50% off.** Nothing about this pipeline is latency-sensitive, so
  there is no reason to pay interactive rates. `extract.submit_batch()` is the
  default path for this reason.
- **Prompt caching on the system prompt.** It is long and identical across every
  document; caching it removes most of the per-call input cost.

Realistically that lands somewhere near **$50–90 for a full corpus run**. Re-do
this arithmetic with your real corpus size and token counts before you start —
`client.messages.count_tokens` gives exact numbers, and Thai tokenises more
heavily than English so do not eyeball it from character counts.

Budget for **three or four full runs**, not one. You will change the prompt after
reading the first hand-labelled sample, and each prompt version is a different
corpus that has to be regenerated. That iteration is the project working
correctly, not overspending.

If cost binds harder than expected, the honest lever is model choice: a smaller
model on the same prompt costs a fraction. That is your call to make, not a
default to assume — and if you do switch, re-run the hand-labelled precision
sample on the new model rather than carrying the old accuracy number over. A
cheaper extraction that quietly loses the ambiguous-species distinction would
cost you more in validity than it saves in baht.

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
