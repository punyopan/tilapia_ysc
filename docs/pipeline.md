# Extraction pipeline — design notes

The problem this solves: the official record of the blackchin tilapia invasion is
~19 provinces with confirmation dates. That is too few observations to fit or
validate a spread model on, and they are province-level, spatially
autocorrelated, and ordered in time. No modelling technique rescues nineteen
points. The way out is not a better model — it is more observations.

Thai-language news, government bulletins, and local fishing and farming groups
contain thousands of dated, place-named references to this species. This pipeline
turns that text into structured occurrence records, and then proves the result is
trustworthy by recovering the official 19 from it independently.

```
documents ──▶ extract.py ──▶ verify_grounding ──▶ geocode.py ──▶ validate.py
   raw          Claude          quote check        gazetteer      vs official 19
                                                                        │
                                                              recall · lead time
                                                              precision · excess
```

## Four design decisions worth defending

**1. The model reports; it does not resolve.**
Claude emits place names verbatim (`ต.บางแก้ว`) and never coordinates or admin
codes. A deterministic gazetteer matcher does the resolution. Models produce
plausible coordinates for places that do not exist, and there is no way to audit
that after the fact. Splitting the two steps means every location assignment is
reproducible and fixable by editing a table rather than re-running extraction.

**2. Every record carries a verbatim quote, and unverified records are dropped.**
`verify_grounding()` checks that `evidence_quote` appears character-for-character
in the source and discards the record if not. This is the cheapest available
hallucination check, it doubles as an audit trail, and the *drop rate* is a
live quality signal — a rise after a prompt edit means the edit degraded the
pipeline.

**3. Claim type is separated from occurrence.**
Most text mentioning this fish is not evidence the fish is anywhere: it is
ministry meetings, budget announcements, opinion columns about who is to blame.
`ClaimType` separates these, and only `first_detection` / `presence` /
`abundance` feed the spread model. Collapsing them would inflate the corpus with
policy noise and make coverage look far better than it is.

**4. Event date is separated from publication date, with a basis flag.**
A 2024 article saying "it has been here since 2015" is a 2015 event reported in
2024. `DateBasis` records how the date was arrived at. This distinction is what
makes the lead-time analysis honest — see below.

## Thai-specific problems the geocoder has to survive

These are not incidental; they are most of the engineering.

- **Name collision.** Subdistrict names repeat across the country. A bare
  `ต.บางแก้ว` is genuinely ambiguous and the resolver refuses to guess — it
  returns a failure with the candidate count rather than silently picking one.
  Records are rescued by `place_context`, the other place name in the same
  passage, which is why the extraction prompt works hard to capture it.
- **`อำเภอเมือง`.** Every province has a capital district. Gazetteers spell these
  `เมือง<province>`; news text writes a bare `อ.เมือง`. Neither exact nor fuzzy
  matching connects the two, so it gets an explicit rule and a province context.
- **No inter-word spaces.** `ต.บางแก้ว`, `ตำบลบางแก้ว`, and `ตำบล บางแก้ว` are one
  place and zero of them string-match. Handled by prefix stripping in
  `normalise()`.
- **Colloquial names.** `แม่กลอง` for Samut Songkhram, `มหาชัย` for Samut Sakhon.
  Fuzzy matching cannot recover these — they need the alias table, which grows as
  the corpus surfaces new ones.
- **Buddhist Era dates.** พ.ศ. 2567 = CE 2024. Handled in the prompt.

Tone marks and vowels are deliberately *preserved* through normalisation. They
are phonemic; stripping them would merge genuinely different place names.

## Validation — and the trap inside it

Ground truth is the official 19. Four measurements:

| | What it answers |
|---|---|
| **Recall** | Does the pipeline independently recover the official provinces? |
| **Lead time** | When it does, how much earlier than official confirmation? |
| **Precision** | Of what it produces, how much is right? (hand-labelled, n≈100) |
| **Excess** | What does it claim that the official record never confirmed? |

**Lead time is the result worth presenting.** "This pipeline would have flagged N
of the 19 provinces a median of M months before official confirmation" is a
demonstration of surveillance value, not an accuracy score — and it speaks
directly to a policy audience whose stated priority is early detection.

**The trap: retrospective leakage.** That claim is only meaningful for records
someone could actually have read at the time. A 2024 article recalling a 2018
arrival produces a record dated 2018, and counting it as an early detection
smuggles hindsight into a prospective claim — it would inflate lead time without
limit. `drop_hindsight()` removes these two ways: by the `RETROSPECTIVE` basis
flag, and by publication lag, since a record can be retrospective in substance
whatever the model labelled it.

Retrospective records are not garbage — they are the *best* evidence for when an
invasion actually began, as opposed to when it was noticed, and they belong in
the spread model's outcome variable. They simply cannot appear in an early-warning
claim. Keeping both uses straight is the point of the flag.

**Excess provinces are a finding, not a failure.** Places the corpus claims but
the official record never confirmed are either false positives or undetected
invasions, and this dataset cannot tell which. List them, rank them by support,
and treat them as fieldwork targets. That is a more interesting result than
deleting them and reporting cleaner numbers.

## Run the whole validation twice

Once with `require_explicit_species=True`, once without. The gap measures how
much the headline depends on ambiguous bare-`ปลาหมอ` mentions — the most
contestable judgement call in the extraction. If the result survives the strict
setting, that objection is answered before anyone raises it.

## What this pipeline cannot do

State these before a judge does:

- **It measures attention as much as fish.** Provinces with more journalists and
  more political salience generate more text per fish. The corpus supports "was
  reported present by date D"; it does not support "has more fish than province
  B".
- **Detection dates are not arrival dates** — in the ground truth as much as in
  the corpus. Confirmation speed changed as national attention grew, so some
  apparent spread is surveillance intensity. This is a limitation of the outcome
  variable itself and needs a per-year effort covariate downstream.
- **Precision rests on ~100 hand-labelled records.** There is no way around
  reading them yourself. It is a few hours and it is the most defensible number
  in the project — every other metric assumes the corpus is roughly correct, and
  this is the only thing that establishes that it is.

## Reproducibility

`extract.prompt_version()` hashes the prompt file. Store that hash with every
output batch. Two corpora built under different prompt versions are different
datasets and must not be compared or pooled — and you *will* edit the prompt
after reading your first precision sample.
