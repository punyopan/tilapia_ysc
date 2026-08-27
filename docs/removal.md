# "Isn't the real problem getting rid of them?"

Yes. And that is not a different project from this one — it is what the spread
model is *for*, once it is framed correctly.

## Say the hard part plainly

National eradication is not achievable. Reasons, stated once:

- an open, tidally connected canal network spanning many provinces;
- a euryhaline species tolerating fresh through hypersaline water;
- a mouthbrooder, so juvenile survival is high;
- already established across many provinces.

Documented eradications of established fish happen in *closed* systems — a pond,
a quarry, an isolated lake — or very shortly after arrival. This is neither.
Thai policy has already shifted accordingly, so saying so is describing the
situation, not conceding it.

## Removal is two different problems

| | established core | new or weakly connected site |
|---|---|---|
| what clearing achieves | temporary density drop | permanent local eradication |
| why | neighbours refill it | nothing to refill from |
| honest name | suppression / maintenance | eradication |

The difference is **not** effort or technique. It is **reinvasion pressure** —
and that is exactly what the fitted spread model computes. So the network model
is not an alternative to removal work. It is the thing that tells you where
removal work lasts.

That reframes the project:

> not *where is the fish* (a map)
> not *where will it go* (a forecast)
> but **where does clearing it stay cleared** (a removal plan)

## The measured result: there is a window, and it closes

Simulated 40-site network, invasion driven by a fitted hybrid model, removal
budget held constant. `periods_clear` is capped at a 20-period planning horizon,
so "20.0" means *at least* 20, not literally forever.

| invaded | treadmill share | best stays-clear | targeted vs. worst-affected |
|---|---|---|---|
| 5/40 | 0.00 | 20.0 | 1.0× |
| 13/40 | 0.00 | 20.0 | **7.9×** |
| 21/40 | 0.00 | 20.0 | 8.5× |
| 25/40 | 0.64 | 7.9 | 3.9× |
| 31/40 | 0.71 | 5.0 | 4.3× |
| 36/40 | 1.00 | 2.0 | 2.3× |

Three things fall out, and all three are policy-relevant:

**1. Durable removal sites exist only below roughly half saturation.** Past
~60%, every candidate site refills within two periods — the treadmill share hits
1.0. At that point no targeting strategy recovers durability, because there is
nowhere left that is not adjacent to an invaded neighbour.

**2. Targeting matters most in the middle.** Early, everything is durable and any
sensible policy works (1.0×). Late, nothing is durable and targeting cannot save
it (2.3×). The 7.9× peak sits at roughly a third saturation — which is precisely
the phase where a programme is most likely to be spending its budget on the
loudest, worst-hit areas instead.

**3. The politically natural policy is the worst one.** "Go where it is worst"
targets the densest, most-complained-about sites — which are exactly the ones
that refill fastest. Up to 8.5× less durable benefit for the same money.

### Caveats, before a judge finds them

- **Simulated, not Thailand.** Rerun with the fitted real network before quoting
  any number. Where Thailand sits on this curve is the whole question, and 19
  provinces does not by itself tell you — it depends on connectivity, not count.
- **The horizon cap is a choice.** "20.0" is the cap, not a prediction of twenty
  years of protection. Show the ranking is stable at another value.
- **The model again adds little over a simple heuristic.** Ranking by durability
  beat ranking by asset size by only 1.08×. Consistent with the surveillance
  result: nearly all the value is in *not* defaulting to the worst-affected
  areas, and that message needs no model.

## What this means for the project

It sharpens the case rather than weakening it. The argument is now:

1. Removal is the goal. Agreed, and it is what the output is for.
2. Removal is permanent only inside a window defined by connectivity.
3. Whether a given site is inside that window is computable — from the spread
   model, not from a map of where the fish currently is.
4. Therefore early detection is not an alternative to removal. **It is the thing
   that keeps sites inside the window where removal is permanent.**
5. And prevention beats both: if the mechanism is fry-shipment contamination,
   hatchery inspection stops incursions from being created at all.

The one-sentence version:

> Clearing fish from the delta is maintenance; clearing them from a newly
> invaded subdistrict is eradication. This model tells you which one you are
> about to pay for.
