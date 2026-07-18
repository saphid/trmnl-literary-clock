# Literary Clock genres and dataset expansion

Research date: 2026-07-18. “Verified” items below come from the linked
first-party documentation, API response, or source repository. “Recommendation”
items are design choices, not claims made by those sources.

## 1. TRMNL genre selector

### Verified

TRMNL Recipes accept `custom_fields` in YAML. A single `select` may use
label/value pairs; `default` is the value, not the label:

```yaml
custom_fields:
  - keyname: genre
    field_type: select
    name: Book type
    description: Choose the books used by the clock
    options:
      - All books: all
      - Science fiction: science_fiction
      - Fantasy: fantasy
      - Romance: romance
      - Mystery and crime: mystery_crime
      - Horror: horror
      - Classics: classics
    default: all
```

TRMNL also documents `multiple: true` for a multi-select. It exposes saved
values in the Markup Editor as
`trmnl.plugin_settings.custom_fields_values`; its example object contains the
field key and selected value. Source:
[TRMNL Custom plugin form builder](https://help.trmnl.com/en/articles/10513740-custom-plugin-form-builder).
Liquid supports property access using dot or bracket notation, so an individual
value can be read as:

```liquid
{% assign selected_genre =
  trmnl.plugin_settings.custom_fields_values.genre | default: "all" %}
```

Source: [Liquid types and object access](https://shopify.github.io/liquid/basics/types/).

For a Polling plugin, TRMNL fetches JSON on the user's behalf, accepts a
custom-field value in the polling URL, and documents this interpolation form:

```text
https://saphid.github.io/trmnl-literary-clock/data/##{{ genre }}.json
```

With one polling URL, keys in its JSON response are available directly as merge
variables. Source:
[TRMNL Private plugins: Polling and dynamic values](https://help.trmnl.com/en/articles/9510536-private-plugins).

### Recommendation

Start with a **single** genre selector plus `all`. Although the form builder
supports multi-select, its public documentation does not specify the serialized
shape well enough to use a multi-select value safely as a static filename.
Useful combined options such as `Sci-fi + fantasy` can be generated explicitly.

## 2. Genre enrichment

### Verified

Open Library's Search API can query by `title` and `author` and return selected
fields for several Work candidates in one response. A suitable build-time
request is:

```text
GET https://openlibrary.org/search.json
    ?title=Dune
    &author=Frank%20Herbert
    &fields=key,title,author_name,subject,subject_key,first_publish_year
    &limit=5
```

Sources:
[Open Library Search API](https://openlibrary.org/dev/docs/api/search) and
[Search syntax](https://openlibrary.org/search/howto).

Open Library subjects are multi-label and need interpretation. For example,
the live Dune Work record includes both `Science fiction` and
`Fantasy fiction`:
[Open Library Dune Work JSON](https://openlibrary.org/works/OL893415W.json).
The Subjects API can list Works for a subject such as
`/subjects/science_fiction.json`, but Open Library labels that API
“experimental”:
[Open Library Subjects API](https://openlibrary.org/dev/docs/api/subjects).

Open Library asks clients to cache responses and use its APIs for low-volume,
human-facing lookups rather than bulk harvesting. Its current limits are one
request per second when unidentified and three requests per second when an
identifying `User-Agent` and contact address are supplied. For catalog-scale
work, it provides monthly data dumps; the Work dump contains full JSON records.
Sources:
[Open Library API usage guidelines](https://openlibrary.org/developers/api) and
[Open Library data dumps](https://openlibrary.org/developers/dumps).

The Internet Archive says it asserts no new copyright over Open Library
database material, while warning that existing rights may remain in some
contributions and jurisdictions:
[Open Library licensing](https://openlibrary.org/developers/licensing).

### Recommendation

1. Deduplicate the current 3,467 rows into unique normalized
   `(title, author)` pairs before enrichment.
2. Resolve each pair to a canonical Open Library Work ID. Score exact normalized
   title, author overlap, and plausible publication year; send ambiguous matches
   to a small committed override file.
3. Preserve Open Library's raw subjects, then map them to a small stable
   multi-label taxonomy. Generic `fiction` must never decide a genre.
4. Store `work_olid`, raw subjects, normalized genres, match confidence, source
   URL, and retrieval date in a committed enrichment snapshot.
5. Use the API only for new or unresolved books. A full refresh should use the
   monthly Work dump, not thousands of one-book API requests.

Suggested first taxonomy: `science_fiction`, `fantasy`, `romance`,
`mystery_crime`, `horror`, `historical`, `classics`, `children_ya`,
`literary_fiction`, and `other`. A book may have several tags.

## 3. Sources for additional quotations

### Verified

The maintained English corpus currently used by this Recipe is
[`cdmoro/literature-clock`](https://github.com/cdmoro/literature-clock/tree/cf83267d0ee007b87f235207be6741c4dc4a7e6e/quotes).
That repository is MIT-licensed and also contains Spanish, Portuguese, French,
Italian, and German CSVs:
[`LICENSE`](https://github.com/cdmoro/literature-clock/blob/cf83267d0ee007b87f235207be6741c4dc4a7e6e/LICENSE).

The older English source
[`JohsEnevoldsen/literature-clock`](https://github.com/JohsEnevoldsen/literature-clock)
uses CC BY-NC-SA 2.5, not a permissive commercial license:
[`LICENCE.md`](https://github.com/JohsEnevoldsen/literature-clock/blob/master/LICENCE.md).
The newer Chinese Literary Clock corpus also uses CC BY-NC-SA 2.5:
[`yezhidong/literature-clock-zh`](https://github.com/yezhidong/literature-clock-zh).
These are useful provenance leads, but they are not a clearly safer source of
modern-book excerpts.

Two stronger sources for adding **new, rights-screened books** are:

- [Standard Ebooks](https://standardebooks.org/about), which says its ebook text
  and cover art are believed to be in the US public domain and that its own work
  is dedicated to the public domain. Its site states that content it produces is
  dedicated under
  [CC0](https://standardebooks.org/manual/1.8.0/introduction).
- [Project Gutenberg](https://www.gutenberg.org/policy/permission.html), which
  says the vast majority of its ebooks are public domain in the US and permits
  extracts, but explicitly warns that users outside the US must check local law
  and that some items remain copyrighted. It provides machine-readable catalog
  metadata and offline feeds:
  [Project Gutenberg offline catalogs](https://www.gutenberg.org/ebooks/offline_catalogs.html).

Open Library and Internet Archive can help locate scans and OCR, but catalog
availability is not reuse permission. Internet Archive's metadata schema makes
`licenseurl` and `rights` item metadata fields; they are not guaranteed to be
present:
[Internet Archive metadata schema](https://archive.org/developers/metadata-schema/index.html).
Its item metadata API is documented here:
[Internet Archive metadata API](https://archive.org/developers/md-read.html).

### Recommendation

Do not search for another large modern-book quote dump and assume its repository
license clears the excerpts. Add books through a separate, auditable pipeline:

1. Select a Standard Ebooks or Project Gutenberg edition whose text is verified
   reusable in every target jurisdiction.
2. Scan its plain text for explicit time expressions.
3. Save the surrounding passage, exact highlighted phrase, normalized minute,
   title, author, edition URL/ID, source checksum, rights evidence, and collector.
4. Manually verify every candidate for meaning, transcription, length, safety,
   and genre before merging it.

This can add public-domain classics immediately. Modern sci-fi, fantasy, and
romance should be added only with permission from the rightsholder or under a
licence that explicitly covers the excerpt.

## 4. Copyright boundary

### Verified

Australian Government guidance says literary works are protected; copyright
owners control copying, publication, communication, and public performance.
Using less than a whole work may still infringe when the reproduced portion is
substantial. Australia's fair-dealing exceptions are purpose-specific
(including research/study, criticism/review, reporting news, professional
advice, parody/satire, and accessible-format copying), and copyright in works
generally lasts 70 years after the author's death:
[Australian Attorney-General's Department: Copyright basics](https://www.ag.gov.au/rights-and-protections/copyright/copyright-basics).

A repository-level licence cannot grant rights its author does not own.
Creative Commons explicitly says a CC licence applies only to rights held by
the licensor and that third-party material used under an exception should be
marked separately:
[Creative Commons FAQ](https://creativecommons.org/faq/#may-i-apply-a-cc-license-to-my-work-if-it-incorporates-material-used-under-fair-use-or-another-exception-or-limitation-to-copyright).

### Recommendation

Treat the current quote corpus as legally reviewable third-party content, not as
automatically cleared by its MIT file. Keep source and rights evidence per quote,
offer a takedown route, and require a `public_domain`, `licensed`, or
`permission` status before accepting new text. This note is engineering
research, not legal advice; public publication of modern excerpts warrants
qualified Australian copyright review.

## 5. Recommended no-server architecture

### Recommendation

Use GitHub as a build and static-hosting layer, with no Open Library or book API
calls during TRMNL rendering:

```text
pinned quote sources
        + rights ledger
        + Open Library enrichment snapshot
        + manual overrides
                 |
           deterministic build
                 |
       data/all.json
       data/science_fiction.json
       data/fantasy.json
       data/romance.json ...
                 |
             GitHub Pages
                 |
       TRMNL polling Recipe + genre select
```

GitHub Pages is static hosting directly from a repository, and GitHub Actions
workflows can run on a push, manually, or on a schedule. Sources:
[GitHub Pages](https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages)
and
[GitHub Actions workflows](https://docs.github.com/en/actions/get-started/understand-github-actions#workflows).

Build each genre JSON with:

- a shared-schema version and source manifest;
- quote rows referencing a deduplicated book table;
- precomputed minute buckets and nearest-minute fallbacks;
- only safe/unknown quotations that passed the rights gate;
- deterministic daily selection inputs; and
- counts, checksums, genre coverage, and licence provenance.

The build should fail on an unknown book, missing rights status, broken
time-phrase highlight, empty genre, missing minute fallback, or unexpected size
growth. It should also generate the self-contained ZIP from the same canonical
data so the existing offline Recipe remains reproducible.

This design scales beyond the current embedded payload without a paid service
or always-on home server. Its trade-off is that genre data depends on public
GitHub Pages availability. The self-contained `all` Recipe should remain as the
offline fallback.
