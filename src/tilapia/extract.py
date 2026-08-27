"""Document -> structured occurrence records, via Claude.

Two paths:

  extract_document()  -- one document, synchronous. Use while iterating on the
                         prompt and while hand-checking output.
  submit_batch()      -- the whole corpus through the Batch API at 50% cost.
                         Use for every production run.

COST
----
This runs on a student budget, so the defaults are chosen for cost and the
levers are explicit. In rough order of how much they save:

1. Screen first (`prefilter.py`). Free, and it multiplies with everything below.
2. Iterate the prompt on a DEV SET, not the corpus. Prompt work needs ~150
   documents, not 5,000. Full corpus runs happen once or twice, at the end.
3. Batch API: 50% off. Nothing here is latency-sensitive, so this is free money.
4. Cache the system prompt. It is long and identical across every call.
5. Low effort. This is mechanical reading against a tight schema, not a
   reasoning problem -- high effort spends output tokens (the expensive side)
   on deliberation this task does not need.
6. Model choice. BULK_MODEL below. Structured extraction against a strict schema
   is one of the most model-robust tasks there is; the schema and the prompt do
   most of the work. Validate any choice on the dev set rather than assuming.

`estimate_cost()` prices a run before you pay for it. Use it.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import anthropic
from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
from anthropic.types.messages.batch_create_params import Request

from .schema import DocumentExtraction

PROMPT_PATH = Path(__file__).resolve().parents[2] / "prompts" / "extraction_th.md"

# The model that reads the corpus. Every document goes through this one, so it
# sets the bill. Start here, and only move up if the dev-set precision says you
# must -- that is a measurement, not a guess.
BULK_MODEL = "claude-haiku-4-5"

# The model used to settle disagreements: the dev-set reference pass you compare
# BULK_MODEL against, and any records flagged as hard. A few hundred calls, not
# a few thousand, so its higher rate barely registers in the total.
ADJUDICATION_MODEL = "claude-opus-5"

# USD per million tokens, standard (non-batch) rates.
PRICING = {
    "claude-opus-5": (5.00, 25.00),
    "claude-sonnet-5": (2.00, 10.00),
    "claude-haiku-4-5": (1.00, 5.00),
}


def _tuning(model: str) -> dict:
    """Per-model request parameters.

    These are not interchangeable. Effort and adaptive thinking exist on the
    current Opus/Sonnet models; Haiku 4.5 predates both and rejects `effort`, so
    it simply runs without either. Sending the wrong pair is a 400, and it is an
    easy mistake to make when swapping models to save money.
    """
    if model in ("claude-opus-5", "claude-sonnet-5"):
        return {
            "thinking": {"type": "adaptive"},
            # Mechanical extraction against a strict schema. Low effort keeps
            # output tokens -- the expensive side -- down without touching the
            # part of the task that needs care, which lives in the prompt.
            "output_config": {"effort": "low"},
        }
    return {}


@dataclass(frozen=True)
class SourceDocument:
    """One document to extract from."""

    source_id: str
    text: str
    source_type: str
    publish_date: date | None
    url: str | None = None


def load_system_prompt() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")


def prompt_version() -> str:
    """Short hash of the prompt, stored with every output batch.

    Records extracted under different prompt versions are not comparable; this
    is what lets you prove which version produced which corpus.
    """
    return hashlib.sha256(load_system_prompt().encode("utf-8")).hexdigest()[:12]


def _user_content(doc: SourceDocument) -> str:
    published = doc.publish_date.isoformat() if doc.publish_date else "unknown"
    return (
        f"<document>\n"
        f"<source_type>{doc.source_type}</source_type>\n"
        f"<publish_date>{published}</publish_date>\n"
        f"<text>\n{doc.text}\n</text>\n"
        f"</document>\n\n"
        f"Extract every occurrence record from this document."
    )


def extract_document(
    client: anthropic.Anthropic,
    doc: SourceDocument,
    model: str = BULK_MODEL,
) -> DocumentExtraction:
    """Single-document extraction with Pydantic validation.

    The dev-set and hand-checking path. `messages.parse` manages `output_config`
    itself to attach the schema, so only the thinking setting is passed through
    here -- effort is set on the batch path, which is where the token volume
    actually is.
    """
    tuning = _tuning(model)
    response = client.messages.parse(
        model=model,
        max_tokens=16000,
        system=[
            {
                "type": "text",
                "text": load_system_prompt(),
                # The prompt is long and identical across every document, so it
                # is worth caching. Keep it as the only cached block: the
                # document text after it varies every call.
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": _user_content(doc)}],
        output_format=DocumentExtraction,
        **({"thinking": tuning["thinking"]} if "thinking" in tuning else {}),
    )
    return response.parsed_output


# --------------------------------------------------------------------------
# Batch path
# --------------------------------------------------------------------------


def submit_batch(
    client: anthropic.Anthropic,
    docs: list[SourceDocument],
    model: str = BULK_MODEL,
) -> str:
    """Submit a corpus for asynchronous extraction. Returns the batch id.

    Half price versus the synchronous path, and this pipeline has no latency
    requirement whatsoever, so there is no reason to run a corpus any other way.

    `custom_id` carries the source_id so results can be rejoined -- batch results
    come back in arbitrary order and must never be matched by position.
    """
    schema = DocumentExtraction.model_json_schema()
    system = [
        {
            "type": "text",
            "text": load_system_prompt(),
            "cache_control": {"type": "ephemeral"},
        }
    ]

    tuning = _tuning(model)
    output_config = {"format": {"type": "json_schema", "schema": schema}}
    if "output_config" in tuning:
        output_config.update(tuning["output_config"])

    params = {"thinking": tuning["thinking"]} if "thinking" in tuning else {}

    requests = [
        Request(
            custom_id=doc.source_id,
            params=MessageCreateParamsNonStreaming(
                model=model,
                max_tokens=16000,
                system=system,
                messages=[{"role": "user", "content": _user_content(doc)}],
                output_config=output_config,
                **params,
            ),
        )
        for doc in docs
    ]

    batch = client.messages.batches.create(requests=requests)
    return batch.id


def estimate_cost(
    client: anthropic.Anthropic,
    docs: list[SourceDocument],
    model: str = BULK_MODEL,
    *,
    batch: bool = True,
    output_tokens_per_doc: int = 400,
    sample: int = 25,
) -> dict[str, float]:
    """Price a run before paying for it.

    Input tokens are measured, not guessed -- `count_tokens` on a sample of real
    documents, scaled up. Thai tokenises more heavily than English, so estimating
    from character counts will mislead you.

    Output is the estimate you control least. 400 tokens/document suits a
    document yielding a couple of records; raise it if your sources are long
    listicles naming a dozen provinces each.
    """
    if not docs:
        return {"documents": 0, "usd_total": 0.0}

    system = load_system_prompt()
    probe = docs[: min(sample, len(docs))]

    counted = 0
    for doc in probe:
        result = client.messages.count_tokens(
            model=model,
            system=system,
            messages=[{"role": "user", "content": _user_content(doc)}],
        )
        counted += result.input_tokens
    mean_input = counted / len(probe)

    in_rate, out_rate = PRICING.get(model, PRICING["claude-opus-5"])
    discount = 0.5 if batch else 1.0

    input_usd = len(docs) * mean_input / 1e6 * in_rate * discount
    output_usd = len(docs) * output_tokens_per_doc / 1e6 * out_rate * discount

    return {
        "documents": len(docs),
        "model": model,
        "mean_input_tokens": round(mean_input),
        "usd_input": round(input_usd, 2),
        "usd_output": round(output_usd, 2),
        "usd_total": round(input_usd + output_usd, 2),
        "note": "excludes prompt-caching savings on the system prompt, so this "
                "is an upper bound",
    }


def await_batch(
    client: anthropic.Anthropic, batch_id: str, poll_seconds: int = 60
) -> None:
    """Block until the batch ends. Most finish inside an hour; the cap is 24h."""
    while True:
        batch = client.messages.batches.retrieve(batch_id)
        if batch.processing_status == "ended":
            counts = batch.request_counts
            print(f"ended: {counts.succeeded} ok, {counts.errored} errored")
            return
        print(f"{batch.processing_status}: {batch.request_counts.processing} in flight")
        time.sleep(poll_seconds)


def collect_batch(
    client: anthropic.Anthropic, batch_id: str
) -> tuple[dict[str, DocumentExtraction], dict[str, str]]:
    """Pull batch results. Returns (extractions by source_id, errors by source_id)."""
    extractions: dict[str, DocumentExtraction] = {}
    errors: dict[str, str] = {}

    for result in client.messages.batches.results(batch_id):
        source_id = result.custom_id
        if result.result.type != "succeeded":
            errors[source_id] = result.result.type
            continue
        message = result.result.message
        text = next((b.text for b in message.content if b.type == "text"), None)
        if text is None:
            errors[source_id] = "no_text_block"
            continue
        try:
            extractions[source_id] = DocumentExtraction.model_validate(json.loads(text))
        except Exception as exc:  # malformed output is data, not a crash
            errors[source_id] = f"parse_failed: {exc}"

    return extractions, errors


# --------------------------------------------------------------------------
# Grounding check
# --------------------------------------------------------------------------


def verify_grounding(
    extraction: DocumentExtraction, source_text: str
) -> tuple[DocumentExtraction, int]:
    """Drop mentions whose evidence_quote is not verbatim in the source.

    Returns the filtered extraction and the number dropped. Report that number:
    a rising drop rate is the earliest signal that a prompt edit has degraded
    the pipeline, and judges will ask how hallucination was controlled.

    Whitespace is normalised before comparison because scraped HTML mangles it;
    nothing else is. In particular Thai text is compared as-is -- do not strip
    tone marks here, since that would let a genuinely wrong quote pass.
    """
    normalised_source = " ".join(source_text.split())

    kept = []
    dropped = 0
    for mention in extraction.mentions:
        quote = " ".join(mention.evidence_quote.split())
        if quote and quote in normalised_source:
            kept.append(mention)
        else:
            dropped += 1

    return (
        DocumentExtraction(
            mentions=kept, document_is_relevant=extraction.document_is_relevant
        ),
        dropped,
    )
