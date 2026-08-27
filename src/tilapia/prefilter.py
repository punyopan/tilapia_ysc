"""Free screening, before anything reaches the API.

Keyword search returns a lot of documents that cannot possibly contain an
occurrence record: the species is not mentioned, or no place is. Sending those to
a model costs money to be told what a regex already knows.

This is the cheapest cost lever in the pipeline and it is worth applying first,
because it multiplies with every other lever -- halving the corpus halves the
bill under any model, any effort level, any batch discount.

The rule for a screen like this: it may only drop documents that are *certainly*
useless. A screen that discards borderline cases to save money is quietly
choosing recall loss, and you will not see it happen. Measure it (see
`screen_recall_check`) rather than assuming.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Explicit names for the target species.
TARGET_NAMES = [
    "ปลาหมอคางดำ",
    "ปลาหมอสีคางดำ",
    "หมอคางดำ",
    "Sarotherodon",
    "melanotheron",
    "blackchin",
]

# Weaker signals: these only count when a target name is absent but the document
# is clearly about an alien aquatic species problem. Kept separate so you can
# measure what the loose tier costs and contributes.
WEAK_SIGNALS = [
    "เอเลี่ยนสปีชีส์",
    "เอเลียนสปีชีส์",
    "ชนิดพันธุ์ต่างถิ่น",
    "ปลาต่างถิ่น",
    "เอเลี่ยนฟิช",
]

# A document with no place reference at all cannot produce a located record.
PLACE_MARKERS = [
    "จังหวัด", "จ.", "อำเภอ", "อ.", "ตำบล", "ต.", "เขต", "แขวง",
    "คลอง", "แม่น้ำ", "ทะเลสาบ", "บึง", "ลำ",
]

_TARGET_RE = re.compile("|".join(map(re.escape, TARGET_NAMES)), re.IGNORECASE)
_WEAK_RE = re.compile("|".join(map(re.escape, WEAK_SIGNALS)))
_PLACE_RE = re.compile("|".join(map(re.escape, PLACE_MARKERS)))


@dataclass(frozen=True)
class ScreenResult:
    keep: bool
    tier: str      # "explicit" | "weak" | "rejected"
    reason: str


def screen(text: str) -> ScreenResult:
    """Decide whether a document is worth an API call.

    Two keep-tiers, deliberately. Run the explicit tier first and get results;
    add the weak tier later and measure how many extra records it buys per baht.
    Often the answer is "very few", and then you have a defensible reason to
    exclude it rather than a guess.
    """
    has_place = bool(_PLACE_RE.search(text))

    if _TARGET_RE.search(text):
        if not has_place:
            return ScreenResult(False, "rejected", "species named, no place reference")
        return ScreenResult(True, "explicit", "species named explicitly")

    if _WEAK_RE.search(text):
        if not has_place:
            return ScreenResult(False, "rejected", "weak signal, no place reference")
        return ScreenResult(True, "weak", "alien-species language, species not named")

    return ScreenResult(False, "rejected", "no species reference")


def apply_screen(documents: dict[str, str], tiers: tuple[str, ...] = ("explicit",)):
    """Split a corpus into kept and rejected by tier.

    Default is the explicit tier only -- the cheap, high-precision run. Pass
    ``("explicit", "weak")`` when you want coverage over cost.
    """
    kept, rejected = {}, {}
    for doc_id, text in documents.items():
        result = screen(text)
        if result.keep and result.tier in tiers:
            kept[doc_id] = text
        else:
            rejected[doc_id] = result
    return kept, rejected


def screen_recall_check(rejected: dict[str, ScreenResult], sample_size: int = 50, seed: int = 0):
    """Draw rejected documents to read by hand.

    Do this once. If the screen is throwing away real records you need to know
    before you build a corpus on top of it, and the only way to find out is to
    read some of what it discarded. Fifty documents is an hour, and it converts
    "the filter probably works" into a number you can put in the report.
    """
    import random

    rng = random.Random(seed)
    items = list(rejected.items())
    return rng.sample(items, min(sample_size, len(items)))
