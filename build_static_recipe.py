#!/usr/bin/env python3
"""Build a self-contained TRMNL Literary Clock recipe from the pinned CSV."""

from __future__ import annotations

import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import DefaultDict, Dict, List

from literary_clock_common import (
    ALL_GENRE_CODE,
    GENRES,
    OTHER_GENRE_CODE,
    book_key,
    eligible_rows,
)


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


def build_static_data(dataset: Path, genre_snapshot: Path) -> Dict[str, object]:
    genre_data = json.loads(genre_snapshot.read_text(encoding="utf-8"))
    genre_by_book = _genre_assignments(genre_data)
    quotes: DefaultDict[str, List[List[str]]] = defaultdict(list)
    required = {"Time", "Quote time", "Quote", "Title", "Author"}
    for row in eligible_rows(dataset, required):
        time_key = _minute_key(str(row["Time"]).strip())
        phrase = str(row["Quote time"] or "").strip()
        quote = str(row["Quote"] or "").strip()
        if not quote:
            continue
        before, highlighted, after = _segments(quote, phrase)
        title = str(row["Title"] or "").strip()
        author = str(row["Author"] or "").strip()
        quotes[time_key].append([before, highlighted, after, title, author])

    if not quotes:
        raise ValueError("Literary Clock dataset contains no eligible quotes")

    titles: List[str] = []
    authors: List[str] = []
    title_indexes: Dict[str, int] = {}
    author_indexes: Dict[str, int] = {}
    compact_quotes: List[List[object]] = []
    quote_genres: List[str] = []
    minute_buckets: List[List[int]] = [[] for _ in range(1440)]

    for time_key, rows in sorted(quotes.items()):
        minute = _minute_number(time_key)
        for before, highlighted, after, title, author in rows:
            if title not in title_indexes:
                title_indexes[title] = len(titles)
                titles.append(title)
            if author not in author_indexes:
                author_indexes[author] = len(authors)
                authors.append(author)
            quote_id = len(compact_quotes)
            compact_quotes.append(
                [
                    before,
                    highlighted,
                    after,
                    title_indexes[title],
                    author_indexes[author],
                ]
            )
            quote_genres.append(
                genre_by_book.get(book_key(title, author), OTHER_GENRE_CODE)
            )
            minute_buckets[minute].append(quote_id)

    all_codes = [
        ALL_GENRE_CODE,
        *(code for code, _name in GENRES.values()),
        OTHER_GENRE_CODE,
    ]
    nearest: Dict[str, List[int]] = {}
    for code in all_codes:
        available = [
            minute
            for minute, quote_ids in enumerate(minute_buckets)
            if any(code == "a" or code in quote_genres[quote_id] for quote_id in quote_ids)
        ]
        if not available:
            continue
        nearest[code] = [
            min(
                available,
                key=lambda candidate: (
                    _circular_distance(candidate, target),
                    candidate,
                ),
            )
            for target in range(1440)
        ]

    return {
        "metadata": {
            **_dataset_metadata(dataset),
            "genre_source": genre_data.get("source", "unknown"),
            "genre_retrieved_at": genre_data.get("retrieved_at", "unknown"),
        },
        "genre_names": {
            code: name
            for code, name in (
                (ALL_GENRE_CODE, "All Books"),
                *GENRES.values(),
                (OTHER_GENRE_CODE, "Other"),
            )
            if code in nearest
        },
        "titles": titles,
        "authors": authors,
        "quotes": compact_quotes,
        "quote_genres": quote_genres,
        "minutes": minute_buckets,
        "nearest": nearest,
    }


def build_recipe(
    dataset: Path,
    genre_snapshot: Path,
    source: Path,
    output: Path,
) -> None:
    data = build_static_data(dataset, genre_snapshot)
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
    if "__GENRE_OPTIONS__" not in settings:
        raise ValueError("settings template is missing __GENRE_OPTIONS__")
    genre_options = "\n".join(
        f"      - {label}: {_yaml_code(code)}"
        for code, label in data["genre_names"].items()
    )
    (output / "settings.yml").write_text(
        settings.replace("__STATIC_DATA__", compact_json).replace(
            "__GENRE_OPTIONS__", genre_options
        ),
        encoding="utf-8",
    )

    preamble = (source / "_quote.liquid").read_text(encoding="utf-8")
    footer = (source / "_footer.liquid").read_text(encoding="utf-8")
    for name in LAYOUTS:
        body = (source / name).read_text(encoding="utf-8")
        if "__QUOTE_FOOTER__" not in body:
            raise ValueError(f"{name} is missing __QUOTE_FOOTER__")
        body = body.replace("__QUOTE_FOOTER__", footer)
        (output / name).write_text(preamble + "\n" + body, encoding="utf-8")


def _segments(quote: str, phrase: str) -> tuple[str, str, str]:
    if not phrase:
        raise ValueError("quote highlight is empty")
    folded_quote_parts: List[str] = []
    folded_boundaries = {0: 0}
    folded_length = 0
    for index, character in enumerate(quote):
        folded_character = character.casefold()
        folded_quote_parts.append(folded_character)
        folded_length += len(folded_character)
        folded_boundaries[folded_length] = index + 1

    folded_phrase = phrase.casefold()
    folded_start = "".join(folded_quote_parts).find(folded_phrase)
    folded_end = folded_start + len(folded_phrase)
    if (
        folded_start < 0
        or folded_start not in folded_boundaries
        or folded_end not in folded_boundaries
    ):
        raise ValueError(f"quote highlight was not found: {phrase!r}")
    start = folded_boundaries[folded_start]
    end = folded_boundaries[folded_end]
    return quote[:start], quote[start:end], quote[end:]


def _genre_assignments(data: Dict[str, object]) -> Dict[str, str]:
    if data.get("schema") != 1 or not isinstance(data.get("books"), list):
        raise ValueError("book genre snapshot has an unsupported schema")
    assignments: Dict[str, str] = {}
    for item in data["books"]:
        if not isinstance(item, dict):
            raise ValueError("book genre snapshot contains an invalid book")
        title = str(item.get("title") or "").strip()
        author = str(item.get("author") or "").strip()
        genre_names = item.get("genres")
        if not title or not author or not isinstance(genre_names, list):
            raise ValueError("book genre snapshot contains an invalid book")
        try:
            codes = sorted({GENRES[str(name)][0] for name in genre_names})
        except KeyError as error:
            raise ValueError(f"unknown book genre: {error.args[0]}") from error
        assignments[book_key(title, author)] = (
            "".join(codes) or OTHER_GENRE_CODE
        )
    return assignments


def _dataset_metadata(dataset: Path) -> Dict[str, str]:
    digest = hashlib.sha256(dataset.read_bytes()).hexdigest()
    if digest == UPSTREAM_METADATA["sha256"]:
        return UPSTREAM_METADATA
    return {
        "source": f"custom dataset ({dataset.name})",
        "commit": "custom",
        "sha256": digest,
        "license": (
            "Custom dataset. The recipe builder does not assert redistribution "
            "rights for custom quotations."
        ),
    }


def _yaml_code(code: str) -> str:
    return '"y"' if code == "y" else code


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


def _circular_distance(left: int, right: int) -> int:
    distance = abs(left - right)
    return min(distance, 1440 - distance)


if __name__ == "__main__":
    if len(sys.argv) != 5:
        raise SystemExit(
            "usage: build_static_recipe.py DATASET GENRES SOURCE OUTPUT"
        )
    build_recipe(
        Path(sys.argv[1]),
        Path(sys.argv[2]),
        Path(sys.argv[3]),
        Path(sys.argv[4]),
    )
