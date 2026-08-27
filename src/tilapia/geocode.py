"""Resolve verbatim Thai place names to official administrative units.

This is deliberately deterministic. The language model reports names; this module
decides what they refer to. Keeping resolution out of the model means every
assignment is reproducible, inspectable, and correctable by editing a table
rather than re-running an extraction.

The four problems this has to solve, in order of how much damage they do:

1. **Name collision.** Subdistrict names repeat across the country -- there are
   many separate ตำบลบางแก้ว, ตำบลบางกระเจ้า, ตำบลท่าทราย. A bare subdistrict name
   is usually NOT resolvable on its own, and pretending otherwise silently
   scatters records across the wrong provinces.

2. **อำเภอเมือง.** Every one of the 77 provinces has a "Mueang" district -- its
   capital. `อ.เมือง` with no province context is 77-way ambiguous. It is also
   extremely common in news text. Handled explicitly below.

3. **Prefix and spacing variation.** Thai is written without spaces between
   words, so `ต.บางแก้ว`, `ตำบลบางแก้ว`, and `ตำบล บางแก้ว` are the same place and
   none of them string-match each other.

4. **Colloquial names.** Places are routinely called something other than their
   administrative name (the town of แม่กลอง for สมุทรสงคราม). No amount of fuzzy
   matching finds these; they need an alias table.

Gazetteer source: the official DOPA subdistrict code list, or the Thailand
administrative boundaries on HDX. See data/reference/README.md. Whichever you
use, keep the ADM codes -- they are the join key to every boundary shapefile you
will need later.
"""

from __future__ import annotations

import csv
import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from rapidfuzz import fuzz, process

# Administrative prefixes, longest first so that "ตำบล" is stripped before "ต".
_PREFIXES = [
    "จังหวัด", "อำเภอ", "กิ่งอำเภอ", "ตำบล", "แขวง", "เขต",
    "จ.", "อ.", "ต.", "มหานคร",
]

# Bangkok goes by many names and is its own province.
_BANGKOK = {"กรุงเทพมหานคร", "กรุงเทพฯ", "กรุงเทพ", "กทม.", "กทม", "บางกอก"}

# Colloquial and historical names that fuzzy matching cannot recover.
# Seeded, not complete -- extend it as the corpus surfaces new ones, and keep
# the additions in version control so the corpus stays reproducible.
ALIASES: dict[str, str] = {
    "แม่กลอง": "สมุทรสงคราม",   # the town/river commonly stands in for the province
    "มหาชัย": "สมุทรสาคร",       # likewise
    "ปากน้ำ": "สมุทรปราการ",
}

_THAI_DIGITS = str.maketrans("๐๑๒๓๔๕๖๗๘๙", "0123456789")


def normalise(name: str) -> str:
    """Canonical form for matching: no prefix, no spaces, no decorations.

    Thai tone marks and vowels are preserved -- they are phonemic and dropping
    them merges genuinely different names.
    """
    text = unicodedata.normalize("NFC", name).strip()
    text = text.translate(_THAI_DIGITS)
    text = text.replace("​", "")          # zero-width space, common in scrapes
    text = re.sub(r"[\(\)\[\]\"'`]", "", text)

    for prefix in _PREFIXES:
        if text.startswith(prefix):
            text = text[len(prefix):]
            break

    text = re.sub(r"\s+", "", text)
    return text


@dataclass(frozen=True)
class AdminUnit:
    adm1_code: str
    adm1_name: str
    adm2_code: str | None
    adm2_name: str | None
    adm3_code: str | None
    adm3_name: str | None

    @property
    def level(self) -> str:
        if self.adm3_code:
            return "tambon"
        if self.adm2_code:
            return "amphoe"
        return "changwat"

    @property
    def own_name(self) -> str:
        return self.adm3_name or self.adm2_name or self.adm1_name


@dataclass
class MatchResult:
    unit: AdminUnit | None
    method: str
    score: float
    candidates: int
    note: str = ""


class Gazetteer:
    """Thai administrative units, indexed by normalised name at each level.

    Expects a CSV with columns:
        adm1_code, adm1_name_th, adm2_code, adm2_name_th, adm3_code, adm3_name_th
    one row per subdistrict. Province and district rows are derived, not stored.
    """

    def __init__(self, units: list[AdminUnit]) -> None:
        self.units = units
        self._by_name: dict[str, list[AdminUnit]] = defaultdict(list)
        self._provinces: dict[str, AdminUnit] = {}

        seen_provinces: set[str] = set()
        seen_districts: set[str] = set()

        for unit in units:
            self._by_name[normalise(unit.own_name)].append(unit)

            if unit.adm1_code not in seen_provinces:
                seen_provinces.add(unit.adm1_code)
                province = AdminUnit(
                    unit.adm1_code, unit.adm1_name, None, None, None, None
                )
                self._by_name[normalise(unit.adm1_name)].append(province)
                self._provinces[normalise(unit.adm1_name)] = province

            if unit.adm2_code and unit.adm2_code not in seen_districts:
                seen_districts.add(unit.adm2_code)
                self._by_name[normalise(unit.adm2_name or "")].append(
                    AdminUnit(
                        unit.adm1_code, unit.adm1_name,
                        unit.adm2_code, unit.adm2_name,
                        None, None,
                    )
                )

        self._all_names = list(self._by_name.keys())

    @classmethod
    def from_csv(cls, path: Path) -> "Gazetteer":
        units = []
        with open(path, encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                units.append(
                    AdminUnit(
                        adm1_code=row["adm1_code"],
                        adm1_name=row["adm1_name_th"],
                        adm2_code=row.get("adm2_code") or None,
                        adm2_name=row.get("adm2_name_th") or None,
                        adm3_code=row.get("adm3_code") or None,
                        adm3_name=row.get("adm3_name_th") or None,
                    )
                )
        return cls(units)

    # ----------------------------------------------------------------
    # Resolution
    # ----------------------------------------------------------------

    def resolve(self, raw_name: str, context: str | None = None) -> MatchResult:
        """Resolve a verbatim place name, optionally narrowed by a context name.

        `context` is whatever other place the passage mentioned -- usually the
        containing province. It is what makes an ambiguous subdistrict usable.
        """
        key = normalise(raw_name)

        if key in _BANGKOK or raw_name.strip() in _BANGKOK:
            bangkok = self._provinces.get(normalise("กรุงเทพมหานคร"))
            if bangkok:
                return MatchResult(bangkok, "exact", 1.0, 1)

        if key in ALIASES:
            aliased = normalise(ALIASES[key])
            if aliased in self._provinces:
                return MatchResult(
                    self._provinces[aliased], "alias", 0.95, 1,
                    note=f"colloquial name for {ALIASES[key]}",
                )

        # "เมือง" is the capital district of every province: never resolvable
        # alone. Note that gazetteers spell these เมือง<province>
        # (เมืองสมุทรสาคร), while news text almost always writes a bare อ.เมือง,
        # so neither exact nor fuzzy matching connects the two -- it needs the
        # province context and an explicit rule.
        if key == "เมือง":
            if not context:
                return MatchResult(
                    None, "failed", 0.0, 77,
                    note="อำเภอเมือง requires a province context (77-way ambiguous)",
                )
            return self._resolve_mueang(context)

        candidates = self._by_name.get(key, [])

        if len(candidates) == 1:
            return MatchResult(candidates[0], "exact", 1.0, 1)

        if len(candidates) > 1:
            narrowed = self._narrow(candidates, context)
            if len(narrowed) == 1:
                return MatchResult(narrowed[0], "hierarchical", 0.9, len(candidates))
            return MatchResult(
                None, "failed", 0.0, len(candidates),
                note=f"'{raw_name}' matches {len(candidates)} units; "
                     f"context {context!r} narrowed to {len(narrowed)}",
            )

        return self._fuzzy(key, raw_name, context)

    def _resolve_mueang(self, context: str) -> MatchResult:
        """Resolve a bare อ.เมือง against its containing province."""
        ctx = normalise(context)
        if ctx in ALIASES:
            ctx = normalise(ALIASES[ctx])

        province = self._provinces.get(ctx)
        if province is None:
            return MatchResult(
                None, "failed", 0.0, 77,
                note=f"อ.เมือง given context {context!r}, which is not a province",
            )

        wanted = {"เมือง", normalise("เมือง" + province.adm1_name)}
        for unit in self.units:
            if unit.adm1_code == province.adm1_code and normalise(unit.adm2_name or "") in wanted:
                return MatchResult(
                    AdminUnit(
                        unit.adm1_code, unit.adm1_name,
                        unit.adm2_code, unit.adm2_name,
                        None, None,
                    ),
                    "hierarchical", 0.9, 77,
                    note="bare อ.เมือง resolved via province context",
                )

        return MatchResult(
            None, "failed", 0.0, 77,
            note=f"no capital district found in {province.adm1_name}",
        )

    def _narrow(self, candidates: list[AdminUnit], context: str | None) -> list[AdminUnit]:
        """Keep only candidates consistent with the context name."""
        if not context:
            return candidates

        ctx = normalise(context)
        if ctx in ALIASES:
            ctx = normalise(ALIASES[ctx])

        narrowed = [
            unit for unit in candidates
            if ctx in (normalise(unit.adm1_name), normalise(unit.adm2_name or ""))
        ]
        return narrowed or candidates

    def _fuzzy(self, key: str, raw_name: str, context: str | None) -> MatchResult:
        """Last resort: typo and OCR tolerance.

        The 88 threshold is a starting point, not a finding. Tune it against a
        hand-labelled sample and report the value you used -- a fuzzy matcher
        with an unjustified threshold is a fair thing for a judge to attack.
        """
        if not key:
            return MatchResult(None, "failed", 0.0, 0, note="empty after normalisation")

        hits = process.extract(key, self._all_names, scorer=fuzz.ratio, limit=5)
        good = [(name, score) for name, score, _ in hits if score >= 88]
        if not good:
            return MatchResult(
                None, "failed", 0.0, 0,
                note=f"no gazetteer entry within threshold of '{raw_name}'",
            )

        best_name, best_score = good[0]
        candidates = self._by_name[best_name]
        narrowed = self._narrow(candidates, context)

        if len(narrowed) == 1:
            method = "fuzzy" if len(candidates) == 1 else "hierarchical"
            return MatchResult(narrowed[0], method, best_score / 100, len(candidates))

        return MatchResult(
            None, "failed", 0.0, len(candidates),
            note=f"fuzzy match '{best_name}' still {len(narrowed)}-way ambiguous",
        )


def resolution_report(results: list[MatchResult]) -> dict[str, int | float]:
    """Summary stats for the geocoding step.

    Put these in the report. The number that matters is `unresolved_rate`: if it
    is high and *correlated with province*, the resulting map is biased, not just
    incomplete -- provinces whose names collide more will look less invaded.
    """
    total = len(results)
    if total == 0:
        return {"total": 0}

    by_method: dict[str, int] = defaultdict(int)
    for result in results:
        by_method[result.method] += 1

    unresolved = by_method["failed"]
    return {
        "total": total,
        "resolved": total - unresolved,
        "unresolved": unresolved,
        "unresolved_rate": round(unresolved / total, 4),
        **{f"method_{k}": v for k, v in sorted(by_method.items())},
    }
