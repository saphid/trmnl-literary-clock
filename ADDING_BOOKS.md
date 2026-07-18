# Adding books safely

The Recipe can build from any pipe-delimited Literary Clock CSV supplied through
`RECIPE_DATA_PATH`, so a fork can add books without running a web service:

```sh
RECIPE_DATA_PATH=/path/to/quotes.csv ./build-recipe-package.sh
```

This is currently an unchecked custom-build escape hatch. The builder records
the custom file's checksum and does not claim the pinned dataset's licence, but
it does **not** validate excerpt rights. Do not publish a custom build until its
intake records have passed the review below.

Use the same columns as the pinned source:

```text
Time|Id|Quote time|Quote|Title|Author|SFW
```

Before publishing a new excerpt:

1. Start with a reusable edition from
   [Standard Ebooks](https://standardebooks.org/) or a Project Gutenberg item
   whose rights status is valid where the Recipe will be distributed.
2. Save an intake record beside the custom dataset. The planned
   rights-gated importer will use `book_intake.json`; until it exists, keep the
   same fields in a reviewed ledger: quote ID, title, author, edition URL/ID,
   source checksum, rights state, rights evidence URL or note, distribution
   jurisdiction, reviewer/date, time phrase and mapped minute, safety result,
   and genres.
3. Scan for an explicit time phrase, then copy only enough surrounding text for
   the quotation to make sense.
4. Check that `Quote time` appears exactly inside `Quote`, `Time` is a valid
   `HH:MM`, and the row is safe to display.
5. Have a person review the transcription, time mapping, length, safety, genre,
   and rights evidence.
6. Accept only a clear `public_domain`, `licensed`, or `permission` rights
   state. Do not assume a quote-dump repository's software licence clears
   copyright in modern excerpts.
7. Refresh `book_genres.json`, inspect the match, build the ZIP, and run the
   tests and TRMNL renderer before release.

Modern science fiction, fantasy, and romance are usually still protected.
Adding those works needs permission or a licence that expressly covers
redistributing the excerpt. Open Library availability or subject metadata is
not rights evidence.

## Classifying a new book

Generate a compact snapshot:

```sh
python3 update_book_genres.py \
  /path/to/quotes.csv \
  book_genres.json \
  --cache-dir build/open-library-subjects
```

The generator checks up to 3,000 works per subject and only accepts exact
normalized title-and-author matches. An unmatched book appears under **Other**;
do not loosen matching merely to force a label.

`update_book_genres.py` replaces `book_genres.json`; it does not preserve manual
edits. Keep reviewed corrections separately in
`book_genre_overrides.json`, reapply them after every snapshot refresh, and
review the resulting diff before building. The override file uses a schema-1
`books` list whose entries look like:

```json
{
  "schema": 1,
  "books": [
    {
      "title": "Example Book",
      "author": "Example Author",
      "genres": ["science_fiction", "fantasy"]
    }
  ]
}
```

The override merge is still manual in v1.1. A future intake tool should merge
this file explicitly instead of asking maintainers to edit generated data.

Supported names are `science_fiction`, `fantasy`, `romance`, `mystery_crime`,
`horror`, `historical_fiction`, `classics`, `children_ya`, and
`literary_fiction`. A book may have more than one.

This is an engineering intake policy, not legal advice.
