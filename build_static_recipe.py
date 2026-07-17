#!/usr/bin/env python3
"""Build a self-contained TRMNL Literary Clock recipe from the pinned CSV."""

from __future__ import annotations

import csv
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import DefaultDict, Dict, List


SAFE_RATINGS = {"sfw", "unknown"}
LAYOUTS = (
    "full.liquid",
    "half_horizontal.liquid",
    "half_vertical.liquid",
    "quadrant.liquid",
)
MAX_STATIC_DATA_BYTES = 1_000_000
UPSTREAM_METADATA = {
    "source": "https://github.com/cdmoro/literature-clock",
    "commit": "cf83267d0ee007b87f235207be6741c4dc4a7e6e",
    "sha256": "60393706e503a13be9548dc5c8c1d657b2d3be762dcbd906fa35191c575e6ef6",
    "license": (
        "MIT License\n\nCopyright (c) 2024 Carlos Bonadeo\n\n"
        "Permission is hereby granted, free of charge, to any person obtaining "
        "a copy of this software and associated documentation files (the "
        '"Software"), to deal in the Software without restriction, including '
        "without limitation the rights to use, copy, modify, merge, publish, "
        "distribute, sublicense, and/or sell copies of the Software, and to "
        "permit persons to whom the Software is furnished to do so, subject "
        "to the following conditions:\n\nThe above copyright notice and this "
        "permission notice shall be included in all copies or substantial "
        "portions of the Software.\n\nTHE SOFTWARE IS PROVIDED \"AS IS\", WITHOUT "
        "WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO "
        "THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE "
        "AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS "
        "BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN "
        "ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN "
        "CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE."
    ),
}


def build_static_data(dataset: Path) -> Dict[str, object]:
    quotes: DefaultDict[str, List[List[str]]] = defaultdict(list)
    with dataset.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="|")
        required = {"Time", "Quote time", "Quote", "Title", "Author", "SFW"}
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise ValueError("Literary Clock CSV has an unsupported header")

        for row in reader:
            rating = str(row.get("SFW") or "").strip().casefold()
            if rating not in SAFE_RATINGS:
                continue
            time_key = _minute_key(str(row["Time"]).strip())
            phrase = str(row["Quote time"] or "").strip()
            quote = str(row["Quote"] or "").strip()
            if not quote:
                continue
            before, highlighted, after = _segments(quote, phrase)
            quotes[time_key].append(
                [
                    before,
                    highlighted,
                    after,
                    str(row["Title"] or "").strip(),
                    str(row["Author"] or "").strip(),
                ]
            )

    if not quotes:
        raise ValueError("Literary Clock dataset contains no eligible quotes")

    minutes = sorted(_minute_number(key) for key in quotes)
    nearest: Dict[str, str] = {}
    for target in range(1440):
        key = _key_for_minute(target)
        if key in quotes:
            continue
        closest = min(
            minutes,
            key=lambda candidate: (_circular_distance(candidate, target), candidate),
        )
        nearest[key] = _key_for_minute(closest)

    return {
        "metadata": UPSTREAM_METADATA,
        "quotes": dict(sorted(quotes.items())),
        "nearest": nearest,
    }


def build_recipe(dataset: Path, source: Path, output: Path) -> None:
    data = build_static_data(dataset)
    compact_json = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    data_size = len(compact_json.encode("utf-8"))
    if data_size >= MAX_STATIC_DATA_BYTES:
        raise ValueError(
            f"static quote data is {data_size} bytes; limit is {MAX_STATIC_DATA_BYTES}"
        )

    output.mkdir(parents=True, exist_ok=True)
    settings = (source / "settings.yml.in").read_text(encoding="utf-8")
    if "__STATIC_DATA__" not in settings:
        raise ValueError("settings template is missing __STATIC_DATA__")
    (output / "settings.yml").write_text(
        settings.replace("__STATIC_DATA__", compact_json),
        encoding="utf-8",
    )

    preamble = (source / "_quote.liquid").read_text(encoding="utf-8")
    for name in LAYOUTS:
        body = (source / name).read_text(encoding="utf-8")
        (output / name).write_text(preamble + "\n" + body, encoding="utf-8")


def _segments(quote: str, phrase: str) -> tuple[str, str, str]:
    start = quote.casefold().find(phrase.casefold())
    if start < 0:
        return quote, "", ""
    end = start + len(phrase)
    return quote[:start], quote[start:end], quote[end:]


def _minute_key(value: str) -> str:
    try:
        hour_text, minute_text = value.split(":", 1)
        hour, minute = int(hour_text), int(minute_text)
    except (AttributeError, ValueError) as error:
        raise ValueError(f"invalid Literary Clock time: {value!r}") from error
    if not 0 <= hour <= 23 or not 0 <= minute <= 59:
        raise ValueError(f"invalid Literary Clock time: {value!r}")
    return f"{hour:02d}{minute:02d}"


def _minute_number(key: str) -> int:
    return int(key[:2]) * 60 + int(key[2:])


def _key_for_minute(minute: int) -> str:
    return f"{minute // 60:02d}{minute % 60:02d}"


def _circular_distance(left: int, right: int) -> int:
    distance = abs(left - right)
    return min(distance, 1440 - distance)


if __name__ == "__main__":
    if len(sys.argv) != 4:
        raise SystemExit("usage: build_static_recipe.py DATASET SOURCE OUTPUT")
    build_recipe(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]))
