# "Isn't this just collecting online posts and drawing a map?"

A fair question, and worth being able to answer in one sentence at a poster
board. If the project stopped at *scraped Thai news → extracted mentions →
coloured map*, the answer would be yes: that is data journalism. Competent, but
not science, and a judge would be right to ask "so what?"

Here is what makes the difference.

## The extraction is the instrument, not the result

Building a telescope is not astronomy. But you cannot do the astronomy without
one, and nobody had built this particular telescope: there was no
subdistrict-resolution occurrence record for this species in Thailand. The
pipeline exists because the question needs more than 19 observations, not
because mining text is interesting in itself.

The paper is not "I built a text-mining pipeline." It is "here is what the
resulting record shows, and here is the hypothesis it rules in or out."

## Four things that separate this from reporting

**1. A hypothesis that came from somewhere else.** The claim that human
transport drives this invasion is not read off the map. It is derived from
independent evidence — published population genetics reporting multiple
introductions and regionally distinct populations with limited mixing.
Genetically separate populations were not connected by swimming fish. The text
corpus is then used to *test* a prediction that evidence implies, not to
generate a story after the fact.

**2. A comparison that could come out the other way.** `spread.py` fits two
competing models to the same data — waterway connectivity versus
aquaculture-mediated human transport — plus nulls including distance-only and
aquaculture-area-only. If the waterway model predicts as well as the hybrid,
the hypothesis is wrong. That outcome is possible, and reporting it would be a
legitimate result. A map cannot be wrong; a ranked prediction can.

**3. Out-of-sample prediction, not fit.** `experiment.py` withholds the later
part of the invasion sequence, fits on the earlier part, predicts which region
falls next, and scores the rank of the region that actually did. In-sample fit
would prove nothing — the hybrid model has more parameters and always fits
better. Prediction is not free that way: a parameter fitting noise makes the
next prediction worse.

**4. The instrument itself gets a measured accuracy.** The pipeline is validated
by independently recovering the documented provincial detections and reporting
how far in advance it would have flagged each. "Recovered N of 19, median M
months early, P% precision on a hand-labelled sample" is a measurement with a
number attached, not a claim about how nice the map looks.

## The strongest version: go and look

The project's `excess_provinces()` output lists places the corpus claims but the
official record never confirmed. The model produces a ranked list of subdistricts
with no recorded detection.

Visit some of them.

"My model ranked these 20 subdistricts; I visited 5 with no official record; I
found the species in 3" is a **prospective validated prediction**. That is not
reporting under any definition, and it is about as strong as a school project
gets. Finding nothing is also a result, and a much better one than not having
looked.

Commit the ranking in writing *before* the fieldwork. A prediction recorded in
advance and then checked is a different kind of evidence from one explained
afterwards, and judges know the difference.

## The honest caveat, which you should raise first

Run `can_this_experiment_work()` before believing any of this. At province-level
resolution the design is weakly powered: roughly 20 nodes and 10 invasion events
is not much to separate two correlated network layers with. The synthetic check
plants a known signal and measures how often the comparison finds it.

If that number is low, say so. "I established that province-level data cannot
answer this question, and here is the resolution at which it can" is a genuine
methodological finding, arrived at before spending a season on fieldwork rather
than after. It is a better result than a confident answer the design could not
have supported.

That check is also the complete answer to "how do you know your model isn't just
fitting noise?" — you tested it against a case where you knew the truth.
