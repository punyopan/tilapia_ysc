"""Benchmark harness, exercised on the synthetic gazetteer.

The labelled items here are SYNTHETIC and few. They demonstrate that the harness
measures the right things; they are not results. The real deliverable is a
hand-labelled set drawn from actual Thai text -- see docs/cs-track.md.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tilapia.benchmark import (  # noqa: E402
    LabeledMention, compare, evaluate, full_resolver, run_full_benchmark,
)
from tilapia.geocode import AdminUnit, Gazetteer  # noqa: E402

FIXTURE = [
    AdminUnit("74", "สมุทรสงคราม", "7401", "เมืองสมุทรสงคราม", "740101", "แม่กลอง"),
    AdminUnit("74", "สมุทรสงคราม", "7401", "เมืองสมุทรสงคราม", "740102", "บางแก้ว"),
    AdminUnit("74", "สมุทรสงคราม", "7402", "บางคนที", "740201", "กระดังงา"),
    AdminUnit("73", "สมุทรสาคร", "7301", "เมืองสมุทรสาคร", "730101", "มหาชัย"),
    AdminUnit("73", "สมุทรสาคร", "7301", "เมืองสมุทรสาคร", "730102", "ท่าฉลอม"),
    AdminUnit("93", "พัทลุง", "9308", "บางแก้ว", "930801", "ท่ามะเดื่อ"),
    AdminUnit("10", "กรุงเทพมหานคร", "1021", "บางขุนเทียน", "102101", "ท่าข้าม"),
]
GAZ = Gazetteer(FIXTURE)

TESTSET = [
    LabeledMention("จ.สมุทรสงคราม", None, "74", "unique"),
    LabeledMention("ตำบล กระดังงา", "จ.สมุทรสงคราม", "740201", "prefix"),
    LabeledMention("ต.ท่าฉลอม", None, "730102", "unique"),
    # Ambiguous without context; resolvable with it.
    LabeledMention("ต.บางแก้ว", "จ.สมุทรสงคราม", "740102", "collision"),
    # Same string, no context: the correct answer is "cannot resolve".
    LabeledMention("ต.บางแก้ว", None, None, "unresolvable",
                   "two provinces have one; answering is fabrication"),
    LabeledMention("อ.เมือง", "สมุทรสาคร", "7301", "mueang"),
    LabeledMention("อ.เมือง", None, None, "unresolvable", "77-way ambiguous"),
    LabeledMention("แม่กลอง", None, "74", "alias"),
    LabeledMention("มหาชัย", None, "73", "alias"),
    LabeledMention("กทม.", None, "10", "alias"),
]

results = []


def check(label, condition, detail=""):
    print(f"[{'PASS' if condition else 'FAIL'}] {label}{'  -- ' + detail if detail else ''}")
    return condition


rows = run_full_benchmark(GAZ, TESTSET)
print()
compare(rows)
print()

by_name = {r.system: r for r in rows}
full = by_name["full_resolver"]
exact = by_name["exact_only"]
greedy = by_name["fuzzy_greedy"]
no_ctx = by_name["ablate_context"]
no_alias = by_name["ablate_aliases"]

results.append(check(
    "full resolver beats exact-match-only",
    full.accuracy > exact.accuracy,
    f"{full.accuracy:.3f} vs {exact.accuracy:.3f}",
))
results.append(check(
    "the gain is concentrated in the ambiguity types it targets",
    full.type_accuracy("collision") >= exact.type_accuracy("collision")
    and full.type_accuracy("mueang") > exact.type_accuracy("mueang")
    and full.type_accuracy("alias") > exact.type_accuracy("alias"),
    f"collision {full.type_accuracy('collision'):.2f}/{exact.type_accuracy('collision'):.2f}  "
    f"mueang {full.type_accuracy('mueang'):.2f}/{exact.type_accuracy('mueang'):.2f}  "
    f"alias {full.type_accuracy('alias'):.2f}/{exact.type_accuracy('alias'):.2f}",
))
results.append(check(
    "greedy fuzzy fabricates answers where it should abstain",
    greedy.false_answers > full.false_answers,
    f"greedy fabricated {greedy.false_answers}, full resolver {full.false_answers}",
))
results.append(check(
    "full resolver abstains correctly on unresolvable items",
    full.type_accuracy("unresolvable") == 1.0,
    f"{full.by_type.get('unresolvable')}",
))
results.append(check(
    "ablating context measurably hurts -- the prompt field earns its keep",
    no_ctx.accuracy < full.accuracy,
    f"{no_ctx.accuracy:.3f} without context vs {full.accuracy:.3f} with",
))
results.append(check(
    "ablating the alias table measurably hurts",
    no_alias.type_accuracy("alias") < full.type_accuracy("alias"),
    f"alias accuracy {no_alias.type_accuracy('alias'):.2f} vs {full.type_accuracy('alias'):.2f}",
))

single = evaluate("spot", full_resolver(GAZ), [TESTSET[3]])
results.append(check(
    "per-item evaluation works on a single labelled mention",
    single.total == 1 and single.correct == 1,
))

print()
print(f"{sum(results)}/{len(results)} passed")
sys.exit(0 if all(results) else 1)
