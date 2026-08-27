# What this actually changes

Start with what it does not do: **it does not remove a single fish.** The
invasion is established, national eradication is not achievable, and no model
changes that. Any claim otherwise would not survive a judge who knows the
system.

What follows is the honest causal chain from this repository to less damage,
and the measured size of each step.

## The chain

**1. Surveillance is budget-constrained, and currently reactive.**
A provincial fisheries office has a few staff and a coastline. Surveys largely
follow reports — which arrive from places already invaded. Reports are a lagging
indicator by construction.

**2. Detection timing has a cliff, not a slope.**
Local eradication is genuinely possible while a population sits in a few ponds or
a short canal segment: drain, net, treat. Once it is across a connected canal
network, it is not. So moving detection earlier in a *few* places is worth more
than improving a map everywhere.

**3. Therefore the lever is allocation, not prediction.**
Same budget, different destinations. `allocate.py` does this.

**4. If the mechanism is human transport, the map changes shape.**
A diffusion model says *watch downstream of infested canals*. A transport model
says *watch pond clusters that buy fry from infested provinces, even across a
watershed boundary*. These give different answers, and the second is not
currently how surveillance is targeted.

**5. Mechanism creates a policy lever that otherwise does not exist.**
You cannot inspect a canal. You can inspect a hatchery. If spread is
fry-shipment-mediated, then certification and inspection at the hatchery become
available interventions — and they are *preventive*, which is worth more than any
amount of detection. This is the single largest potential impact in the project,
and it exists only if the mechanism question is answered.

## The measured part

200 subdistricts, 20 survey-days, expected damage averted (simulated risk and
asset distributions — replace with real ones before quoting):

| policy | sites | expected averted | vs. highest-risk |
|---|---|---|---|
| expected_value | 16 | 79.5 | 18.9× |
| largest_assets | 15 | 74.2 | 17.6× |
| highest_risk | 15 | 4.2 | 1.0× |

The chosen sites do not overlap **at all**: the highest-risk policy surveys sites
with p_invaded 0.54–0.78; the expected-value policy surveys 0.06–0.44. Zero of 15
sites in common. That is the concrete operational difference — two policies, same
budget, entirely different destinations.

### Read this honestly, because the headline number is misleading

Three caveats, and you should raise all three before a judge does.

**The magnitude is an artifact.** The gain over highest-risk ranges from 5.7× to
107× depending on `containability`'s `sharpness` parameter, which is *not
measured*. Only the direction is robust — expected-value wins at every value
tested. Quote the direction, not the multiple.

**Most of the gain needs no model at all.** Across 8 random trials, the full
model beat a trivially simple "protect the largest farming areas, ignore risk"
heuristic by a **mean of 1.06×** (range 1.03–1.12). Both beat highest-risk by
~17×. So virtually all of the benefit comes from *not chasing certainty*, which a
one-line heuristic already achieves. The sophisticated model contributes about
6%.

That is a deflating result and it belongs in the report. It is also genuinely
useful: if you can only get one message to a fisheries office, it is not "use my
model", it is **"stop sending survey teams to the places you are already sure
about."** That message is free, needs no software, and captures most of the
available value.

**The simulation is not Thailand.** These are synthetic risk and asset
distributions. Rerun with real subdistrict aquaculture area and real fitted
probabilities before quoting any number.

## Two deliverables, and one survives the other failing

Worth separating, because they have independent value:

**A. The early-warning pipeline.** If text mining recovers detections months
before official confirmation, that is a deployable monitoring system on its own —
cheap, continuous, flagging places for a human to check. It works whether or not
the human-transport hypothesis is right.

**B. The mechanism finding.** If human transport is confirmed, it redirects
surveillance and opens the hatchery-inspection lever. This is the higher-value
result and the less certain one — recovery is ~68% against a 50% baseline, so a
single comparison is suggestive, not conclusive.

If B fails, A still stands. Design the report so that is visible.

## Honest scope

This is a school project. The realistic best case is not a national policy
change; it is:

- a validated method someone else can extend,
- a ranked list a provincial office could use for one season,
- and, if the fieldwork happens, a handful of confirmed predictions at sites with
  no official record.

That last one is the strongest thing available: *ranked 20 subdistricts, visited
5 with no recorded detection, found the species in 3.* It is a real contribution
at a real scale, and claiming more would be the fastest way to lose credibility
with a judge who works on this.

## The one-sentence answer

> It does not remove fish. It moves a fixed surveillance budget from places
> already lost to places still savable, and — if the transport mechanism holds —
> points at the hatchery inspection that would stop new incursions before they
> start.
