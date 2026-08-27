"""Bake-off logic, exercised with stub providers (no API calls, no keys)."""

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tilapia.bakeoff import compare, cost_per_record, disagreements, free_diagnostics, run_provider  # noqa: E402
from tilapia.extract import SourceDocument  # noqa: E402
from tilapia.providers import ProviderStats  # noqa: E402
from tilapia.schema import (  # noqa: E402
    AdminLevel, ClaimType, DateBasis, DatePrecision,
    DocumentExtraction, ExtractedMention, SpeciesCertainty,
)

TEXT = "ชาวประมง ต.บางแก้ว จ.สมุทรสงคราม พบปลาหมอคางดำ จำนวนมากในคลอง เมื่อปี 2565"
DOCS = [SourceDocument("doc1", TEXT, "news", date(2024, 5, 1))]


def mention(quote, certainty):
    return ExtractedMention(
        claim_type=ClaimType.PRESENCE,
        species_certainty=certainty,
        raw_place_text="ต.บางแก้ว",
        place_context="จ.สมุทรสงคราม",
        admin_level_guess=AdminLevel.TAMBON,
        event_date=date(2022, 1, 1),
        date_precision=DatePrecision.YEAR,
        date_basis=DateBasis.RETROSPECTIVE,
        evidence_quote=quote,
        confidence=0.8,
        reasoning="stub",
    )


class StubProvider:
    """Emits a fixed extraction. `quote` decides whether grounding passes."""

    def __init__(self, name, quote, certainty, retries=0):
        self.name = name
        self._quote = quote
        self._certainty = certainty
        self.stats = ProviderStats(
            calls=1, schema_retries=retries,
            input_tokens=3000, output_tokens=400,
        )

    def extract(self, doc):
        return DocumentExtraction(
            mentions=[mention(self._quote, self._certainty)],
            document_is_relevant=True,
        )


results = []


def check(label, condition, detail=""):
    print(f"[{'PASS' if condition else 'FAIL'}] {label}{'  -- ' + detail if detail else ''}")
    return condition


# Grounded quote (verbatim substring) vs hallucinated quote.
grounded = run_provider(StubProvider("good", "พบปลาหมอคางดำ จำนวนมากในคลอง", SpeciesCertainty.NAMED_EXPLICIT), DOCS)
hallucinated = run_provider(StubProvider("bad", "พบปลาหมอคางดำ ที่จังหวัดภูเก็ต", SpeciesCertainty.NAMED_EXPLICIT, retries=1), DOCS)

results.append(check(
    "grounded quote survives the verbatim check",
    grounded.grounding_rate == 1.0 and grounded.total_mentions == 1,
    f"rate={grounded.grounding_rate}",
))
results.append(check(
    "fabricated quote is dropped, grounding rate falls to 0",
    hallucinated.grounding_rate == 0.0 and hallucinated.grounding_drops == 1,
    f"rate={hallucinated.grounding_rate} drops={hallucinated.grounding_drops}",
))

diag = free_diagnostics(grounded)
results.append(check(
    "free diagnostics need no hand labels",
    diag["grounding_rate"] == 1.0 and diag["mentions"] == 1,
    f"ambiguous_share={diag['ambiguous_share']}",
))

results.append(check(
    "retry rate is surfaced from provider stats",
    hallucinated.stats["schema_retry_rate"] == 1.0,
    f"retry_rate={hallucinated.stats['schema_retry_rate']}",
))

# Two providers that disagree on species certainty for the same document.
explicit = run_provider(StubProvider("A", "พบปลาหมอคางดำ จำนวนมากในคลอง", SpeciesCertainty.NAMED_EXPLICIT), DOCS)
ambiguous = run_provider(StubProvider("B", "พบปลาหมอคางดำ จำนวนมากในคลอง", SpeciesCertainty.NAMED_AMBIGUOUS), DOCS)

results.append(check(
    "species-certainty disagreement is queued for hand-labelling",
    disagreements(explicit, ambiguous) == ["doc1"],
    str(disagreements(explicit, ambiguous)),
))
results.append(check(
    "agreement produces an empty labelling queue",
    disagreements(explicit, explicit) == [],
))

cheap = cost_per_record(grounded, 0.27, 1.10)
dear = cost_per_record(grounded, 5.00, 25.00)
results.append(check(
    "cost per record tracks the rate card",
    cheap["usd_per_record"] < dear["usd_per_record"],
    f"cheap={cheap['usd_per_record']} vs dear={dear['usd_per_record']}",
))

print()
compare([explicit, ambiguous])
print()
print(f"{sum(results)}/{len(results)} passed")
sys.exit(0 if all(results) else 1)
