# Literary Clock TRMNL recipe

This self-contained TRMNL Recipe shows a book quotation containing the current
time. The annotated time phrase is black and bold; the rest is grey. It needs
no API key, cloud worker, subscription, or always-on personal server.

![Full-screen Literary Clock preview](preview.png)

## Data source

The recipe embeds Carlos Bonadeo's MIT-licensed
[`literature-clock`](https://github.com/cdmoro/literature-clock) English dataset.
The source contains 3,635 quotations. After the safety filter, this recipe uses
all 3,467 eligible quotations covering 1,410 of 1,440 minutes. It includes rows
marked `sfw` or `unknown`, excludes rows marked `nsfw`/`nswf`, chooses a stable
quote for each day and minute, and uses the nearest available minute for gaps.

The deployment downloads the CSV from GitHub commit
`cf83267d0ee007b87f235207be6741c4dc4a7e6e` and verifies SHA-256
`60393706e503a13be9548dc5c8c1d657b2d3be762dcbd906fa35191c575e6ef6`.
The build writes compact JSON into `settings.yml` as `static_data`, including
the upstream source, checksum, and complete MIT notice. The final payload is
under 1 MB. Once imported, the recipe does not fetch the data from GitHub or
any other server.

The Instructables version generated one 600×800 PNG per quote from an annotated
CSV. Its PHP generator grew the type until the quote filled the screen, rendered
the time phrase bold black and the rest grey, and its Kindle cron script chose a
random matching PNG each minute. Its original attachments were
`litclock_annotated.csv`, `quote_to_image.php.zip`, `timelit.zip`, and
`timetest.php.zip`. This is a modern adaptation rather than a byte-for-byte
port: it keeps that visual idea but renders on demand, uses the larger
maintained GitHub dataset, filters unsafe rows, fills gaps, and makes quote
selection stable for a given day and minute rather than random on every poll.

## Add it to TRMNL

Download `LITERARY_CLOCK_TRMNL_RECIPE.zip` from the
[latest GitHub release](https://github.com/saphid/trmnl-literary-clock/releases/latest),
or build the flat import archive from source:

```sh
./build-recipe-package.sh
```

Then open TRMNL's **Private Plugin** settings, choose **Import new**, and select
`dist/LITERARY_CLOCK_TRMNL_RECIPE.zip`. The import creates the static
plugin and adds it to the playlist. No URL or time-zone form field is needed;
TRMNL injects the account's current UTC offset into the Liquid template.

To publish it through TRMNL, open the imported plugin, choose **Publish**, and
select **Unlisted** for an immediate share link or **Public** for directory
review. The GitHub source and ZIP can also be shared directly.

## Timing limitation

TRMNL's hosted recipe generation currently refreshes static plugins no more
often than every 15 minutes. The quotation is correct for the minute when the
screen is generated, but it can remain displayed until the next refresh. The
local Kindle TRMNL service still refreshes its Literary Clock screen every
minute and is the exact-clock option.
