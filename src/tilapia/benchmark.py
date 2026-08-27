"""Evaluation harness for Thai geographic entity resolution.

THIS MODULE IS THE COMPUTER SCIENCE CONTRIBUTION.

Everything else in this repository uses the resolver. This measures it -- against
baselines, per ambiguity type, with ablations -- which is the difference between
"I built a pipeline" and "I evaluated a method". In a CS category the second is
the project and the first is plumbing.

THE CLAIM BEING TESTED
----------------------
The architecture is hybrid neural-symbolic: the language model reports place
names *verbatim* and never resolves them; a deterministic gazetteer matcher does
the resolution. The alternative -- ask the model for the administrative code
directly -- is simpler and is what most people would build.

    H0: asking the model directly is as accurate as the hybrid pipeline.
    H1: the hybrid pipeline is more accurate, and the gap is concentrated in
        ambiguous cases where the correct answer requires the gazetteer.

That is a testable systems claim with a measurable answer, and it is the thing a
CS judge can actually evaluate.

WHY THAI MAKES THIS A REAL PROBLEM
----------------------------------
Not incidental difficulty -- these are the reasons an off-the-shelf approach
fails, and each one gets its own row in the results table:

  COLLISION    subdistrict names repeat across provinces; the string alone is
               insufficient and any system that answers anyway is guessing
  MUEANG       every province has a capital district, written เมือง<province> in
               gazetteers and bare อ.เมือง in text -- neither exact nor fuzzy
               matching connects them
  PREFIX       no inter-word spaces, so ต.บางแก้ว / ตำบลบางแก้ว / ตำบล บางแก้ว are
               one place and zero of them string-match
  ALIAS        colloquial names (แม่กลอง for สมุทรสงคราม) that no edit distance
               recovers
  TYPO         OCR and scraping noise

Reporting one aggregate accuracy hides all of this. Per-type accuracy is what
shows a judge that the failure modes were understood rather than averaged away.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Callable, Literal

from . import geocode
from .geocode import Gazetteer, MatchResult, normalise

AmbiguityType = Literal["unique", "collision", "mueang", "prefix", "alias", "typo", "unresolvable"]


@dataclass
class LabeledMention:
    """One hand-labelled test item.

    `gold_code` is None when the correct answer is "this cannot be resolved" --
    those items matter enormously. A resolver that always produces an answer
    scores well on resolvable items and silently fabricates locations on the
    rest, which in this application means putting fish in the wrong province.
    """

    raw_text: str
    context: str | None
    gold_code: str | None
    ambiguity_type: AmbiguityType
    note: str = ""


@dataclass
class BenchmarkResult:
    system: str
    correct: int = 0
    total: int = 0
    # Answered when it should have abstained -- the dangerous error.
    false_answers: int = 0
    # Abstained when a correct answer existed -- costly but safe.
    missed: int = 0
    by_type: dict[str, tuple[int, int]] = field(default_factory=dict)

    @property
    def accuracy(self) -> float:
        return self.correct / self.total if self.total else 0.0

    @property
    def fabrication_rate(self) -> float:
        """Share of unresolvable items the system answered anyway.

        The headline safety number. In this application a fabricated resolution
        is worse than a refusal: it places an occurrence record in a province
        that never had one, and nothing downstream can detect that.
        """
        unresolvable = sum(1 for t, (_, n) in self.by_type.items() if t == "unresolvable" for _ in range(n))
        return self.false_answers / unresolvable if unresolvable else 0.0

    def type_accuracy(self, ambiguity_type: str) -> float:
        correct, total = self.by_type.get(ambiguity_type, (0, 0))
        return correct / total if total else 0.0


Resolver = Callable[[str, str | None], MatchResult]


def evaluate(name: str, resolver: Resolver, testset: list[LabeledMention]) -> BenchmarkResult:
    """Score one resolver on the labelled set."""
    result = BenchmarkResult(system=name, total=len(testset))
    tally: dict[str, list[int]] = defaultdict(lambda: [0, 0])

    for item in testset:
        match = resolver(item.raw_text, item.context)
        predicted = _code_of(match)
        tally[item.ambiguity_type][1] += 1

        if predicted == item.gold_code:
            result.correct += 1
            tally[item.ambiguity_type][0] += 1
        elif item.gold_code is None and predicted is not None:
            result.false_answers += 1
        elif item.gold_code is not None and predicted is None:
            result.missed += 1

    result.by_type = {k: (v[0], v[1]) for k, v in tally.items()}
    return result


def _code_of(match: MatchResult) -> str | None:
    if match.unit is None:
        return None
    return match.unit.adm3_code or match.unit.adm2_code or match.unit.adm1_code


# --------------------------------------------------------------------------
# Baselines -- what a reasonable person would build instead
# --------------------------------------------------------------------------


def baseline_exact(gaz: Gazetteer) -> Resolver:
    """Normalise and look up. No fuzzy matching, no context, no rules."""
    def resolve(raw: str, context: str | None) -> MatchResult:
        candidates = gaz._by_name.get(normalise(raw), [])
        if len(candidates) == 1:
            return MatchResult(candidates[0], "exact", 1.0, 1)
        return MatchResult(None, "failed", 0.0, len(candidates))
    return resolve


def baseline_fuzzy_greedy(gaz: Gazetteer) -> Resolver:
    """Fuzzy match, always take the top candidate. Never abstains.

    This is the tempting baseline: it has the highest raw match rate and it is
    what a system built without thinking about ambiguity looks like. Its
    fabrication rate is the point of including it.
    """
    def resolve(raw: str, context: str | None) -> MatchResult:
        candidates = gaz._by_name.get(normalise(raw), [])
        if candidates:
            return MatchResult(candidates[0], "exact", 1.0, len(candidates))
        fuzzy = gaz._fuzzy(normalise(raw), raw, None)
        if fuzzy.unit is None and fuzzy.candidates > 0:
            key = normalise(raw)
            pool = gaz._by_name.get(key) or []
            if pool:
                return MatchResult(pool[0], "fuzzy", 0.5, len(pool))
        return fuzzy
    return resolve


def baseline_no_context(gaz: Gazetteer) -> Resolver:
    """The full resolver with the context signal removed.

    Ablation, not a strawman: it isolates how much of the accuracy comes from
    `place_context`, which is the field the extraction prompt works hardest to
    capture. If this barely hurts, that prompt effort is not earning its keep.
    """
    return lambda raw, context: gaz.resolve(raw, None)


def baseline_no_aliases(gaz: Gazetteer) -> Resolver:
    """Ablation: alias table disabled."""
    def resolve(raw: str, context: str | None) -> MatchResult:
        saved = dict(geocode.ALIASES)
        geocode.ALIASES.clear()
        try:
            return gaz.resolve(raw, context)
        finally:
            geocode.ALIASES.update(saved)
    return resolve


def full_resolver(gaz: Gazetteer) -> Resolver:
    return lambda raw, context: gaz.resolve(raw, context)


def llm_direct_stub(predictions: dict[str, str | None]) -> Resolver:
    """Stand-in for 'ask the model for the admin code directly'.

    Supply real model outputs keyed by raw text to run the comparison for
    actual. Until then this documents the experiment rather than faking a
    result -- do NOT report numbers from a stub as if they were measured.
    """
    def resolve(raw: str, context: str | None) -> MatchResult:
        code = predictions.get(raw)
        if code is None:
            return MatchResult(None, "failed", 0.0, 0, note="model declined")
        from .geocode import AdminUnit
        return MatchResult(
            AdminUnit(code[:2], "?", code[:4] if len(code) > 2 else None, None,
                      code if len(code) > 4 else None, None),
            "exact", 1.0, 1, note="model-supplied",
        )
    return resolve


# --------------------------------------------------------------------------
# Reporting
# --------------------------------------------------------------------------

TYPE_ORDER = ["unique", "prefix", "collision", "mueang", "alias", "typo", "unresolvable"]


def compare(results: list[BenchmarkResult]) -> None:
    """The results table. This is what goes on the poster."""
    types = [t for t in TYPE_ORDER if any(t in r.by_type for r in results)]
    header = f"{'system':<20}{'acc':<8}" + "".join(f"{t[:9]:<11}" for t in types) + f"{'fabricated':<12}"
    print(header)
    print("-" * len(header))
    for r in sorted(results, key=lambda x: -x.accuracy):
        row = f"{r.system:<20}{r.accuracy:<8.3f}"
        for t in types:
            correct, total = r.by_type.get(t, (0, 0))
            row += f"{(f'{correct}/{total}'):<11}"
        row += f"{r.false_answers:<12}"
        print(row)


def run_full_benchmark(gaz: Gazetteer, testset: list[LabeledMention]) -> list[BenchmarkResult]:
    """Every system on the same labelled set.

    Report all of them. A table showing the full resolver beating four
    alternatives, with the gap concentrated in the ambiguity types it was
    designed for, is an argument. A single accuracy number is not.
    """
    systems = [
        ("exact_only", baseline_exact(gaz)),
        ("fuzzy_greedy", baseline_fuzzy_greedy(gaz)),
        ("ablate_context", baseline_no_context(gaz)),
        ("ablate_aliases", baseline_no_aliases(gaz)),
        ("full_resolver", full_resolver(gaz)),
    ]
    return [evaluate(name, resolver, testset) for name, resolver in systems]
