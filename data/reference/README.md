# Reference data

Nothing in this directory is generated. Everything here is either official
reference data you download once, or ground truth you assemble by hand and can
cite. Treat it as read-only during analysis.

## 1. Administrative gazetteer (required)

`geocode.Gazetteer.from_csv()` expects one row per subdistrict with columns:

```
adm1_code, adm1_name_th, adm2_code, adm2_name_th, adm3_code, adm3_name_th
```

Two workable sources:

- **DOPA subdistrict codes** — the Department of Provincial Administration
  publishes the official province/district/subdistrict code list. This is the
  authoritative version of the codes and the one government data joins against.
- **Thailand administrative boundaries (HDX / OCHA)** — shapefiles at ADM0–ADM3
  with both Thai and romanised names. Use this one if you want geometry, which
  you will for the spread graph.

Whichever you pick, **keep the codes**. They are the join key between the mined
records, the boundary geometry, and any DOF statistics you add later. Matching
provinces by name across three datasets will cost you an afternoon.

Check before you commit to a source: subdistricts are created, merged, and
renamed over time, and the invasion record spans well over a decade. A place
named in a 2013 article may not exist under that name in a 2024 boundary file.
Note which vintage you used.

## 2. Ground truth (`official_detections.csv`)

The official provincial detection sequence. See the header comments in the file
— the important discipline is recording date *precision* honestly rather than
padding partial dates into false day-level precision.

## 3. Corpus manifest (not committed)

Scraped documents go in `data/raw/`, which is gitignored — some sources will not
permit redistribution. What you should commit instead is a manifest: source id,
URL, publish date, retrieval date, and a hash of the text. That makes the corpus
reproducible without republishing anyone's content, and it lets you prove the
text did not change under you between runs.

## Bias, recorded up front

This corpus is built from documents people wrote, so it measures attention as
much as it measures fish. Provinces with more journalists, more Facebook use,
and more political salience generate more text per fish. Two consequences:

- The corpus cannot support "province A has more fish than province B."
- It can support "the fish was reported present in province A by date D," which
  is what the spread model actually consumes.

Keep the distinction visible in the writeup. A judge who knows ecology will go
looking for exactly this, and having named it first is worth more than a
defensive answer later.
