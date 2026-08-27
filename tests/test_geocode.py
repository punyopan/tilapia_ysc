"""Geocoder tests, built around the failure modes that actually occur.

The fixture below is SYNTHETIC -- a handful of plausible rows, not real gazetteer
data. Replace it with a sample of the real DOPA/HDX table once you have it; the
cases it exercises are the ones that matter either way.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tilapia.geocode import AdminUnit, Gazetteer, normalise  # noqa: E402

FIXTURE = [
    # Samut Songkhram
    AdminUnit("74", "สมุทรสงคราม", "7401", "เมืองสมุทรสงคราม", "740101", "แม่กลอง"),
    AdminUnit("74", "สมุทรสงคราม", "7401", "เมืองสมุทรสงคราม", "740102", "บางแก้ว"),
    AdminUnit("74", "สมุทรสงคราม", "7402", "บางคนที", "740201", "กระดังงา"),
    # Samut Sakhon
    AdminUnit("73", "สมุทรสาคร", "7301", "เมืองสมุทรสาคร", "730101", "มหาชัย"),
    AdminUnit("73", "สมุทรสาคร", "7301", "เมืองสมุทรสาคร", "730102", "ท่าฉลอม"),
    # Phatthalung -- has its own บางแก้ว, which is the whole point
    AdminUnit("93", "พัทลุง", "9308", "บางแก้ว", "930801", "ท่ามะเดื่อ"),
    # Bangkok
    AdminUnit("10", "กรุงเทพมหานคร", "1021", "บางขุนเทียน", "102101", "ท่าข้าม"),
]

GAZ = Gazetteer(FIXTURE)


def check(label, condition, detail=""):
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {label}{'  -- ' + detail if detail else ''}")
    return condition


results = []

# --- normalisation ---------------------------------------------------------
results.append(check(
    "prefix variants normalise identically",
    normalise("ต.บางแก้ว") == normalise("ตำบลบางแก้ว") == normalise("ตำบล บางแก้ว") == "บางแก้ว",
    normalise("ตำบล บางแก้ว"),
))

# --- unambiguous province --------------------------------------------------
r = GAZ.resolve("จ.สมุทรสงคราม")
results.append(check(
    "province with prefix resolves exactly",
    r.unit is not None and r.unit.adm1_code == "74" and r.method == "exact",
    f"method={r.method}",
))

# --- the collision case ----------------------------------------------------
r = GAZ.resolve("ต.บางแก้ว")
results.append(check(
    "colliding subdistrict name refuses to guess",
    r.unit is None and r.candidates > 1,
    r.note,
))

r = GAZ.resolve("ต.บางแก้ว", context="จ.สมุทรสงคราม")
results.append(check(
    "collision resolves with province context",
    r.unit is not None and r.unit.adm3_code == "740102" and r.method == "hierarchical",
    f"-> {r.unit.own_name if r.unit else None} in {r.unit.adm1_name if r.unit else None}",
))

# --- อำเภอเมือง ------------------------------------------------------------
r = GAZ.resolve("อ.เมือง")
results.append(check(
    "bare อ.เมือง refuses to guess",
    r.unit is None,
    r.note,
))

r = GAZ.resolve("อ.เมือง", context="สมุทรสาคร")
results.append(check(
    "อ.เมือง resolves against its province",
    r.unit is not None and r.unit.adm2_code == "7301",
    f"-> {r.unit.adm2_name if r.unit else None}",
))

# --- aliases ---------------------------------------------------------------
r = GAZ.resolve("แม่กลอง")
results.append(check(
    "colloquial name resolves via alias table",
    r.unit is not None and r.unit.adm1_code == "74",
    f"method={r.method} note={r.note}",
))

# --- Bangkok ---------------------------------------------------------------
r = GAZ.resolve("กทม.")
results.append(check(
    "Bangkok shorthand resolves",
    r.unit is not None and r.unit.adm1_code == "10",
    f"method={r.method}",
))

# --- fuzzy / typo ----------------------------------------------------------
r = GAZ.resolve("ต.บางคนที")
results.append(check(
    "district name resolves when it is unique",
    r.unit is not None and r.unit.adm2_code == "7402",
    f"method={r.method}",
))

# --- junk ------------------------------------------------------------------
r = GAZ.resolve("ประเทศไทย")
results.append(check(
    "unmatchable name fails cleanly rather than fuzzing to nonsense",
    r.unit is None and r.method == "failed",
    r.note,
))

print()
print(f"{sum(results)}/{len(results)} passed")
sys.exit(0 if all(results) else 1)
