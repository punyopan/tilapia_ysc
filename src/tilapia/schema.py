"""Record schemas for the occurrence-extraction pipeline.

Design rules that the rest of the pipeline depends on:

1. The language model NEVER produces coordinates or admin codes. It reports the
   place name *verbatim as written* (`raw_place_text`); a deterministic gazetteer
   matcher resolves that to an admin unit later. Models hallucinate coordinates
   confidently and there is no way to audit the result.

2. Every record carries `evidence_quote`, a span copied verbatim from the source.
   If the quote is not literally present in the source text, the record is
   dropped by `extract.verify_grounding()`. This is the cheapest hallucination
   check available and it doubles as an audit trail for judges.

3. `event_date` is when the fish was reportedly seen, which is NOT the article's
   publication date. A 2024 article saying "it has been here since 2015" is a
   2015 event reported in 2024. Conflating the two destroys the lead-time
   analysis in validate.py -- see `date_basis`.

4. `claim_type` separates "a fish is in this water" from "officials met to
   discuss the fish". Most text mentioning the species is not an occurrence
   record, and treating it as one is the main way this pipeline could inflate
   its own apparent coverage.
"""

from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class ClaimType(str, Enum):
    """What the passage actually asserts. Only the first four are occurrences."""

    FIRST_DETECTION = "first_detection"      # explicitly framed as newly found here
    PRESENCE = "presence"                    # present, no novelty claim
    ABUNDANCE = "abundance"                  # quantified: catch weight, density, "ทั้งบ่อ"
    ABSENCE = "absence"                      # explicitly looked for, not found -- rare and precious
    CONTROL_ACTION = "control_action"        # netting drive, buyback, predator release
    IMPACT = "impact"                        # farm loss, ecological damage claim
    POLICY = "policy"                        # meetings, budgets, regulations
    OPINION = "opinion"                      # speculation about origin/blame
    UNCLEAR = "unclear"


class DatePrecision(str, Enum):
    DAY = "day"
    MONTH = "month"
    YEAR = "year"
    UNKNOWN = "unknown"


class DateBasis(str, Enum):
    """How `event_date` was arrived at. Governs leakage filtering in validation."""

    EXPLICIT = "explicit"            # the text states the date of the sighting
    RELATIVE = "relative"            # "last month", "two years ago" -- resolved against publish_date
    PUBLICATION = "publication"      # no date given; fell back to publish_date
    RETROSPECTIVE = "retrospective"  # text recalls an event well before publication


class AdminLevel(str, Enum):
    TAMBON = "tambon"        # subdistrict (also แขวง in Bangkok)
    AMPHOE = "amphoe"        # district (also เขต in Bangkok)
    CHANGWAT = "changwat"    # province
    WATERBODY = "waterbody"  # a named canal/river/lagoon, resolved separately
    UNKNOWN = "unknown"


class SpeciesCertainty(str, Enum):
    """Thai common names overlap badly.

    ปลาหมอคางดำ  = blackchin tilapia (Sarotherodon melanotheron)  -- the target
    ปลาหมอ        = climbing perch (Anabas) in most contexts      -- NOT the target
    ปลาหมอเทศ     = Mozambique tilapia                            -- NOT the target
    ปลานิล        = Nile tilapia                                  -- NOT the target

    A bare ปลาหมอ in a coastal-aquaculture context is genuinely ambiguous. The
    model must not resolve that ambiguity silently; it flags it and the record
    is handled at a lower confidence tier.
    """

    NAMED_EXPLICIT = "named_explicit"    # full name ปลาหมอคางดำ or the binomial
    NAMED_AMBIGUOUS = "named_ambiguous"  # bare ปลาหมอ / "เอเลี่ยนสปีชีส์" in context
    DESCRIBED_ONLY = "described_only"    # described by traits, not named
    UNCERTAIN = "uncertain"


class ExtractedMention(BaseModel):
    """One claim about the species at one place, as extracted from one document.

    A single document routinely yields several of these (an article naming five
    affected provinces produces five records). They are deduplicated downstream,
    not here.
    """

    claim_type: ClaimType
    species_certainty: SpeciesCertainty

    raw_place_text: str = Field(
        description="Place name copied verbatim from the source, including any "
        "administrative prefix (ต./อ./จ./เขต/แขวง). Never normalised, never "
        "translated, never resolved to a code."
    )
    place_context: str | None = Field(
        default=None,
        description="Any *other* place name in the same passage that narrows the "
        "first one, e.g. the province containing a named subdistrict. This is "
        "what makes hierarchical disambiguation possible.",
    )
    admin_level_guess: AdminLevel

    event_date: date | None
    date_precision: DatePrecision
    date_basis: DateBasis

    evidence_quote: str = Field(
        description="Verbatim span from the source supporting this record. Must "
        "appear character-for-character in the source text."
    )
    quantity_text: str | None = Field(
        default=None,
        description="Verbatim quantity if the passage gives one ('300 กิโลกรัม', "
        "'ร้อยละ 80 ของบ่อ'). Parsed downstream, never here.",
    )

    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str = Field(description="One sentence: why this reading, and what is uncertain.")


class DocumentExtraction(BaseModel):
    """The model's full response for one source document."""

    mentions: list[ExtractedMention]
    document_is_relevant: bool = Field(
        description="False if the document does not concern this species at all. "
        "Keyword search returns plenty of these; recording them keeps an honest "
        "denominator for the precision estimate."
    )


class GeocodedRecord(BaseModel):
    """An ExtractedMention after gazetteer resolution. The analysis unit."""

    mention: ExtractedMention

    source_id: str
    source_url: str | None
    source_type: Literal["news", "government", "social", "forum", "academic", "other"]
    publish_date: date | None

    # Resolved administrative identity. adm2/adm3 may be None when the text only
    # names a province -- that is a legitimate record, not a failure.
    adm1_code: str | None  # province
    adm2_code: str | None  # district
    adm3_code: str | None  # subdistrict
    adm1_name_th: str | None
    match_method: Literal["exact", "normalised", "fuzzy", "hierarchical", "alias", "failed"]
    match_score: float = Field(ge=0.0, le=1.0)
    match_candidates: int = Field(
        description="How many gazetteer entries matched. >1 means the name is "
        "ambiguous and was resolved by context (or left unresolved)."
    )
