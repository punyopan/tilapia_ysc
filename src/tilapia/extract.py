"""Document -> structured occurrence records, via Claude.

Two paths:

  extract_document()  -- one document, synchronous. Use while iterating on the
                         prompt and while hand-checking output.
  submit_batch()      -- the whole corpus through the Batch API at 50% cost.
                         Use for every production run.

Corpus scale here is a few thousand documents, so the batch path is the one that
matters: it is the difference between a run that costs a few dollars and one that
costs a few tens of dollars, and nothing about this pipeline is latency
sensitive.
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

MODEL = "claude-opus-5"
PROMPT_PATH = Path(__file__).resolve().parents[2] / "prompts" / "extraction_th.md"


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
    client: anthropic.Anthropic, doc: SourceDocument
) -> DocumentExtraction:
    """Single-document extraction with Pydantic validation."""
    response = client.messages.parse(
        model=MODEL,
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
        thinking={"type": "adaptive"},
        messages=[{"role": "user", "content": _user_content(doc)}],
        output_format=DocumentExtraction,
    )
    return response.parsed_output


# --------------------------------------------------------------------------
# Batch path
# --------------------------------------------------------------------------


def submit_batch(client: anthropic.Anthropic, docs: list[SourceDocument]) -> str:
    """Submit a corpus for asynchronous extraction. Returns the batch id.

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

    requests = [
        Request(
            custom_id=doc.source_id,
            params=MessageCreateParamsNonStreaming(
                model=MODEL,
                max_tokens=16000,
                system=system,
                thinking={"type": "adaptive"},
                messages=[{"role": "user", "content": _user_content(doc)}],
                output_config={"format": {"type": "json_schema", "schema": schema}},
            ),
        )
        for doc in docs
    ]

    batch = client.messages.batches.create(requests=requests)
    return batch.id


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
