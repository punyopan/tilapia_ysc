"""Validate the mined corpus against the official provincial detection record.

The official record -- the ~19 provinces with DOF confirmation dates -- is the
only ground truth available. It is small, so it cannot support a conventional
train/test split. It can support four things, and together they are enough to
establish that the pipeline works:

  1. RECALL          Does the pipeline independently recover the official 19?
  2. LEAD TIME       When it recovers a province, how early?
  3. PRECISION       Of what it produces, how much is right? (hand-labelled)
  4. EXCESS          What does it claim that the official record does not?

(2) is the result worth presenting. "This pipeline would have flagged N of the
19 provinces a median of M months before official confirmation" is a
demonstration of practical surveillance value, not an accuracy score -- and it is
exactly the claim an early-detection policy audience cares about.

(4) is the honest part. Provinces the pipeline claims but the official record
never confirmed are either false positives or undetected invasions, and nothing
in this dataset can distinguish them. Say so, list them, and treat them as
fieldwork targets rather than quietly deleting them.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from datetime import date

from .schema import ClaimType, DateBasis, GeocodedRecord, SpeciesCertainty

# Claim types that assert the fish is physically present somewhere.
OCCURRENCE_CLAIMS = {
    ClaimType.FIRST_DETECTION,
    ClaimType.PRESENCE,
    ClaimType.ABUNDANCE,
}


@dataclass(frozen=True)
class OfficialDetection:
    """One row of ground truth: a province and its official confirmation date."""

    adm1_code: str
    adm1_name_th: str
    detection_date: date
    source: str


@dataclass
class ProvinceOutcome:
    adm1_code: str
    adm1_name_th: str
    official_date: date
    earliest_mined: date | None
    lead_days: int | None
    supporting_records: int

    @property
    def recovered(self) -> bool:
        return self.earliest_mined is not None


def eligible_records(
    records: list[GeocodedRecord],
    *,
    min_confidence: float = 0.5,
    require_explicit_species: bool = False,
) -> list[GeocodedRecord]:
    """Filter to records that actually assert presence, at usable quality.

    Run the whole validation twice -- once with `require_explicit_species=False`
    and once with it True -- and report both. The gap between them measures how
    much the result depends on the ambiguous bare-ปลาหมอ mentions, which is the
    single most contestable judgement call in the extraction. If the headline
    number survives the strict setting, that objection is answered before it is
    raised.
    """
    allowed_species = {SpeciesCertainty.NAMED_EXPLICIT}
    if not require_explicit_species:
        allowed_species.add(SpeciesCertainty.NAMED_AMBIGUOUS)

    return [
        record
        for record in records
        if record.mention.claim_type in OCCURRENCE_CLAIMS
        and record.mention.species_certainty in allowed_species
        and record.mention.confidence >= min_confidence
        and record.adm1_code is not None
        and record.mention.event_date is not None
    ]


def drop_hindsight(records: list[GeocodedRecord]) -> list[GeocodedRecord]:
    """Remove records that only exist because someone looked back.

    THE LEAKAGE GUARD. A 2024 article reporting "the fish reached Phetchaburi in
    2018" produces a record dated 2018 -- but nobody could have read that article
    in 2018. Counting it as an early detection is retrospective knowledge
    smuggled into a prospective claim, and it would inflate lead time without
    limit.

    Two filters, both necessary:
      - drop `date_basis == RETROSPECTIVE` outright;
      - drop anything whose source was published after the event it describes by
        more than a reporting lag, since that is retrospective in substance
        whatever the model labelled it.

    Retrospective records are still useful -- they are the best evidence for when
    an invasion *actually* began, as opposed to when it was noticed. They belong
    in the spread model's outcome variable. They do not belong in a claim about
    early warning.
    """
    kept = []
    for record in records:
        if record.mention.date_basis == DateBasis.RETROSPECTIVE:
            continue
        event = record.mention.event_date
        published = record.publish_date
        if event and published and (published - event).days > 180:
            continue
        kept.append(record)
    return kept


def evaluate_recall(
    records: list[GeocodedRecord],
    truth: list[OfficialDetection],
    *,
    prospective_only: bool = True,
) -> list[ProvinceOutcome]:
    """Per-province recovery and lead time.

    With `prospective_only`, only records that could have been read at the time
    count -- this is the setting for any lead-time claim. Turn it off to measure
    total historical coverage instead, and never mix the two in one number.
    """
    pool = drop_hindsight(records) if prospective_only else records

    by_province: dict[str, list[GeocodedRecord]] = {}
    for record in pool:
        by_province.setdefault(record.adm1_code or "", []).append(record)

    outcomes = []
    for official in truth:
        province_records = by_province.get(official.adm1_code, [])
        dates = [r.mention.event_date for r in province_records if r.mention.event_date]
        earliest = min(dates) if dates else None
        outcomes.append(
            ProvinceOutcome(
                adm1_code=official.adm1_code,
                adm1_name_th=official.adm1_name_th,
                official_date=official.detection_date,
                earliest_mined=earliest,
                lead_days=(official.detection_date - earliest).days if earliest else None,
                supporting_records=len(province_records),
            )
        )
    return outcomes


def summarise(outcomes: list[ProvinceOutcome]) -> dict[str, object]:
    """Headline numbers. Report the median lead, not the mean.

    Lead-time distributions are skewed by one or two provinces with a very old
    forum post, and a mean lets that single record carry the result.
    """
    recovered = [o for o in outcomes if o.recovered]
    leads = [o.lead_days for o in recovered if o.lead_days is not None]
    early = [d for d in leads if d > 0]

    return {
        "provinces_in_truth": len(outcomes),
        "provinces_recovered": len(recovered),
        "recall": round(len(recovered) / len(outcomes), 3) if outcomes else 0.0,
        "median_lead_days": statistics.median(leads) if leads else None,
        "median_lead_months": round(statistics.median(leads) / 30.4, 1) if leads else None,
        "n_detected_before_official": len(early),
        "missed_provinces": [o.adm1_name_th for o in outcomes if not o.recovered],
    }


def excess_provinces(
    records: list[GeocodedRecord],
    truth: list[OfficialDetection],
    *,
    min_records: int = 3,
) -> dict[str, int]:
    """Provinces the corpus claims but the official record never confirmed.

    `min_records` guards against a single stray mention creating a phantom
    province. Report whatever survives, ranked by support -- these are candidate
    surveillance targets and candidate false positives, and which is which is an
    empirical question this dataset cannot settle. That is a finding, not a gap.
    """
    known = {t.adm1_code for t in truth}
    counts: dict[str, int] = {}
    for record in records:
        code = record.adm1_code
        if code and code not in known:
            counts[code] = counts.get(code, 0) + 1

    return {
        code: n
        for code, n in sorted(counts.items(), key=lambda kv: -kv[1])
        if n >= min_records
    }


def precision_sample(records: list[GeocodedRecord], n: int = 100, seed: int = 0):
    """Draw a random sample for hand-labelling.

    There is no way around this: to state a precision figure you have to read
    ~100 records against their sources and mark each right or wrong. It is a few
    hours of work and it is the single most defensible number in the project --
    every other metric depends on the corpus being roughly correct, and this is
    the only thing that establishes that it is.

    Label each as: correct / wrong species / wrong place / wrong date / not an
    occurrence. A per-category error breakdown tells you which part of the prompt
    to fix, where a single accuracy number tells you nothing.
    """
    import random

    rng = random.Random(seed)
    return rng.sample(records, min(n, len(records)))
