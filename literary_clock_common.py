"""Shared Literary Clock catalogue and text matching rules."""

from __future__ import annotations

import csv
import unicodedata
from pathlib import Path
from typing import Dict, Iterator, Set, Tuple


SAFE_RATINGS = {"sfw", "unknown"}
ALL_GENRE_CODE = "a"
OTHER_GENRE_CODE = "o"

# slug: (compact recipe code, display label, Open Library subject)
GENRE_CATALOG: Dict[str, Tuple[str, str, str]] = {
    "science_fiction": ("s", "Science Fiction", "science_fiction"),
    "fantasy": ("f", "Fantasy", "fantasy"),
    "romance": ("r", "Romance", "romance"),
    "mystery_crime": ("m", "Mystery & Crime", "mystery_and_detective_stories"),
    "horror": ("h", "Horror", "horror"),
    "historical_fiction": ("l", "Historical Fiction", "historical_fiction"),
    "classics": ("c", "Classics", "classic_literature"),
    "children_ya": ("y", "Children & Young Adult", "juvenile_fiction"),
    "literary_fiction": ("i", "Literary Fiction", "literary_fiction"),
}

GENRES = {
    slug: (code, label)
    for slug, (code, label, _subject) in GENRE_CATALOG.items()
}
OPEN_LIBRARY_SUBJECTS = {
    slug: subject
    for slug, (_code, _label, subject) in GENRE_CATALOG.items()
}


def normalize(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).casefold()
    return " ".join(
        "".join(
            character if character.isalnum() else " "
            for character in value
        ).split()
    )


def book_key(title: str, author: str) -> str:
    return f"{normalize(title)}\u001f{normalize(author)}"


def eligible_rows(
    dataset: Path, required_fields: Set[str]
) -> Iterator[Dict[str, str]]:
    """Yield safe or unrated rows from a supported Literary Clock CSV."""
    with dataset.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="|")
        required = set(required_fields) | {"SFW"}
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise ValueError("Literary Clock CSV has an unsupported header")
        for row in reader:
            rating = str(row.get("SFW") or "").strip().casefold()
            if rating in SAFE_RATINGS:
                yield row
