"""Distillation dataset construction, on synthetic teacher output."""

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tilapia.distill import (  # noqa: E402
    build_linking_dataset, build_ner_dataset, learning_curve_splits, to_char_bio, write_jsonl,
)
from tilapia.extract import SourceDocument  # noqa: E402
from tilapia.geocode import AdminUnit, Gazetteer  # noqa: E402
from tilapia.schema import (  # noqa: E402
    AdminLevel, ClaimType, DateBasis, DatePrecision,
    DocumentExtraction, ExtractedMention, SpeciesCertainty,
)

TEXT = "ชาวประมง ต.บางแก้ว จ.สมุทรสงคราม พบปลาหมอคางดำ จำนวนมากในคลอง"
GAZ = Gazetteer([
    AdminUnit("74", "สมุทรสงคราม", "7401", "เมืองสมุทรสงคราม", "740102", "บางแก้ว"),
    AdminUnit("93", "พัทลุง", "9308", "บางแก้ว", "930801", "ท่ามะเดื่อ"),
])

def mention(raw, ctx):
    return ExtractedMention(
        claim_type=ClaimType.PRESENCE, species_certainty=SpeciesCertainty.NAMED_EXPLICIT,
        raw_place_text=raw, place_context=ctx, admin_level_guess=AdminLevel.TAMBON,
        event_date=date(2024, 1, 1), date_precision=DatePrecision.DAY,
        date_basis=DateBasis.PUBLICATION, evidence_quote="พบปลาหมอคางดำ",
        confidence=0.9, reasoning="stub",
    )

DOCS = {"d1": SourceDocument("d1", TEXT, "news", date(2024, 5, 1))}
EXTR = {"d1": DocumentExtraction(
    mentions=[mention("ต.บางแก้ว", "จ.สมุทรสงคราม")], document_is_relevant=True)}

results = []
def check(label, cond, detail=""):
    print(f"[{'PASS' if cond else 'FAIL'}] {label}{'  -- ' + detail if detail else ''}")
    return cond

tags = to_char_bio(TEXT, ["ต.บางแก้ว"])
start = TEXT.find("ต.บางแก้ว")
results.append(check(
    "character BIO tagging aligns to the verbatim span",
    tags[start] == "B-PLACE" and tags[start+1] == "I-PLACE" and tags[0] == "O",
    f"tagged {tags.count('B-PLACE')} span(s), {len(tags)} chars",
))
results.append(check(
    "a mention absent from the text is skipped, not fuzzily aligned",
    to_char_bio(TEXT, ["ต.ไม่มีอยู่จริง"]).count("B-PLACE") == 0,
))

ner = build_ner_dataset(DOCS, EXTR)
results.append(check(
    "NER examples carry silver provenance",
    len(ner) == 1 and ner[0].label_quality == "silver" and len(ner[0].labels) == len(TEXT),
    f"{len(ner)} example(s)",
))

link = build_linking_dataset(EXTR, GAZ)
results.append(check(
    "linking example enumerates the colliding candidates",
    len(link) == 1 and len(link[0].candidate_codes) == 2,
    f"candidates={link[0].candidate_codes}",
))
results.append(check(
    "gold index points at the context-consistent candidate",
    link[0].gold_index is not None and link[0].candidate_codes[link[0].gold_index] == "740102",
    f"gold_index={link[0].gold_index}",
))
results.append(check(
    "each candidate gets a feature vector of equal length",
    len({len(f) for f in link[0].features}) == 1 and len(link[0].features) == 2,
    f"{len(link[0].features[0])} features per candidate",
))

curve = learning_curve_splits(list(range(3000)), sizes=(250, 500, 1000, 2000, 4000))
results.append(check(
    "learning-curve subsets are nested and drop sizes beyond the pool",
    list(curve) == [250, 500, 1000, 2000] and curve[500][:250] == curve[250],
    f"sizes={list(curve)}",
))

out = Path("/tmp/claude-0/-home-user-tilapia-ysc/31da810b-33f6-590f-8fb9-0072cea3c7b3/scratchpad/ner.jsonl")
results.append(check("jsonl export writes UTF-8 Thai", write_jsonl(ner, out) == 1
                     and "บางแก้ว" in out.read_text(encoding="utf-8")))

print()
print(f"{sum(results)}/{len(results)} passed")
sys.exit(0 if all(results) else 1)
