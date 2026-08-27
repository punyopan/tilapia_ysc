"""Decide the provider question with the dev set instead of with opinions.

Generic benchmark scores will not answer "is this model good enough for my
task". This task has four specific ways a model can fail, and they are not
equally visible:

  1. SPECIES DISCRIMINATION. Does it hold the line between ปลาหมอคางดำ (target)
     and a bare ปลาหมอ (usually a different fish entirely)? This is the most
     delicate judgement in the prompt, it requires fine lexical discrimination
     in Thai specifically, and a weaker model flattens it by promoting
     everything to named_explicit. If a provider fails here, nothing else about
     it matters -- the corpus would be silently contaminated with the wrong
     species.

  2. GROUNDING. Does evidence_quote actually appear in the source? Measurable
     with zero hand-labelling, on any corpus, for free. Run this first.

  3. DATE BASIS. Does it distinguish a retrospective claim from a contemporary
     one? Getting this wrong breaks the lead-time result specifically, which is
     the headline of the project.

  4. SCHEMA COMPLIANCE. How often does it need a retry to produce valid output?
     Pure cost, but it is cost the price-per-token table does not show.

The honest comparison metric at the end is COST PER VALIDATED RECORD, not price
per million tokens. A provider that is four times cheaper and needs 1.3 attempts
per document while producing 20% fewer usable records is not four times cheaper.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from .extract import SourceDocument, verify_grounding
from .providers import ExtractionProvider
from .schema import DocumentExtraction, SpeciesCertainty


@dataclass
class ProviderRun:
    provider_name: str
    extractions: dict[str, DocumentExtraction]
    grounding_drops: int
    total_mentions: int
    stats: dict[str, float | int]

    @property
    def grounding_rate(self) -> float:
        total = self.total_mentions + self.grounding_drops
        return self.total_mentions / total if total else 0.0


def run_provider(
    provider: ExtractionProvider, docs: list[SourceDocument]
) -> ProviderRun:
    """Run one provider over the dev set, applying the grounding check."""
    extractions: dict[str, DocumentExtraction] = {}
    drops = 0
    mentions = 0

    for doc in docs:
        result = provider.extract(doc)
        if result is None:
            continue
        checked, dropped = verify_grounding(result, doc.text)
        extractions[doc.source_id] = checked
        drops += dropped
        mentions += len(checked.mentions)

    return ProviderRun(
        provider_name=provider.name,
        extractions=extractions,
        grounding_drops=drops,
        total_mentions=mentions,
        stats=provider.stats.summary(),
    )


def free_diagnostics(run: ProviderRun) -> dict[str, object]:
    """Everything measurable without hand-labelling a single document.

    Run this before spending an afternoon on labels. If a provider's grounding
    rate is poor, or it never emits `named_ambiguous`, you already have your
    answer and the labelling effort is better spent elsewhere.
    """
    certainty = Counter()
    claim = Counter()
    missing_context = 0

    for extraction in run.extractions.values():
        for mention in extraction.mentions:
            certainty[mention.species_certainty.value] += 1
            claim[mention.claim_type.value] += 1
            if mention.place_context is None:
                missing_context += 1

    explicit = certainty.get(SpeciesCertainty.NAMED_EXPLICIT.value, 0)
    ambiguous = certainty.get(SpeciesCertainty.NAMED_AMBIGUOUS.value, 0)

    return {
        "provider": run.provider_name,
        "grounding_rate": round(run.grounding_rate, 3),
        "mentions": run.total_mentions,
        "species_certainty": dict(certainty),
        # A model that never says "ambiguous" is not being careful, it is
        # collapsing the distinction. Near-zero here is a red flag, not a
        # clean result.
        "ambiguous_share": round(ambiguous / (explicit + ambiguous), 3)
        if (explicit + ambiguous)
        else None,
        "claim_types": dict(claim),
        "missing_place_context_share": round(missing_context / run.total_mentions, 3)
        if run.total_mentions
        else None,
        **run.stats,
    }


def disagreements(run_a: ProviderRun, run_b: ProviderRun) -> list[str]:
    """Documents where two providers disagree, as a hand-labelling queue.

    Where both providers agree, they are usually both right and labelling adds
    little. Where they disagree, one of them is wrong and the document is
    informative. Labelling the disagreements first gets you a usable comparison
    for a fraction of the reading -- and the disagreement set is itself a map of
    where this task is genuinely hard, which is worth a paragraph in the report.
    """
    flagged = []
    shared = set(run_a.extractions) & set(run_b.extractions)

    for source_id in sorted(shared):
        a = run_a.extractions[source_id]
        b = run_b.extractions[source_id]

        if len(a.mentions) != len(b.mentions):
            flagged.append(source_id)
            continue
        if a.document_is_relevant != b.document_is_relevant:
            flagged.append(source_id)
            continue

        key_a = sorted((m.raw_place_text, m.species_certainty.value) for m in a.mentions)
        key_b = sorted((m.raw_place_text, m.species_certainty.value) for m in b.mentions)
        if key_a != key_b:
            flagged.append(source_id)

    return flagged


def cost_per_record(
    run: ProviderRun, usd_in_per_m: float, usd_out_per_m: float
) -> dict[str, float]:
    """The comparison that actually matters.

    Uses the provider's own reported token usage, so retries are included -- that
    is the whole point. Pass the provider's current published rates; do not trust
    a hardcoded table for either vendor, both change them.
    """
    tokens_in = float(run.stats.get("input_tokens", 0) or 0)
    tokens_out = float(run.stats.get("output_tokens", 0) or 0)
    total = tokens_in / 1e6 * usd_in_per_m + tokens_out / 1e6 * usd_out_per_m

    return {
        "provider": run.provider_name,
        "usd_total": round(total, 4),
        "records": run.total_mentions,
        "usd_per_record": round(total / run.total_mentions, 6)
        if run.total_mentions
        else None,
        "grounding_rate": round(run.grounding_rate, 3),
    }


def compare(runs: list[ProviderRun]) -> None:
    """Print the free diagnostics side by side."""
    rows = [free_diagnostics(run) for run in runs]
    keys = ["provider", "grounding_rate", "mentions", "ambiguous_share",
            "schema_retry_rate", "hard_failures"]
    width = max(len(k) for k in keys) + 2

    for key in keys:
        line = f"{key:<{width}}"
        for row in rows:
            line += f"{str(row.get(key)):<28}"
        print(line)
