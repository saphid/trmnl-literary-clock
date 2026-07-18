#!/usr/bin/env python3
"""Build a compact, reproducible genre snapshot from Open Library subjects."""

from __future__ import annotations

import argparse
import json
import time
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import DefaultDict, Dict, Iterable, List, Set, Tuple

from literary_clock_common import (
    OPEN_LIBRARY_SUBJECTS,
    eligible_rows,
    normalize,
)


PAGE_SIZE = 1_000
USER_AGENT = (
    "trmnl-literary-clock/1.1 "
    "(+https://github.com/saphid/trmnl-literary-clock)"
)


def build_snapshot(
    dataset: Path,
    cache_dir: Path,
    *,
    pages: int,
    refresh: bool,
    retrieved_at: str,
) -> Dict[str, object]:
    """Match quote books exactly against cached Open Library subject lists."""
    books = _dataset_books(dataset)
    genres_by_book: DefaultDict[Tuple[str, str], Set[str]] = defaultdict(set)
    subject_sources: List[str] = []

    for genre, subject in OPEN_LIBRARY_SUBJECTS.items():
        for offset in range(0, pages * PAGE_SIZE, PAGE_SIZE):
            source_url = _subject_url(subject, offset)
            subject_sources.append(source_url)
            payload = _load_subject_page(
                cache_dir,
                subject,
                offset,
                source_url,
                refresh=refresh,
            )
            for work in payload.get("works", []):
                title = str(work.get("title") or "").strip()
                for author in work.get("authors") or []:
                    author_name = str(author.get("name") or "").strip()
                    key = (normalize(title), normalize(author_name))
                    if key in books:
                        genres_by_book[key].add(genre)

    matched_books = []
    genre_counts = {genre: 0 for genre in OPEN_LIBRARY_SUBJECTS}
    for key in sorted(genres_by_book, key=lambda item: books[item]):
        title, author = books[key]
        genres = sorted(genres_by_book[key])
        matched_books.append(
            {
                "title": title,
                "author": author,
                "genres": genres,
            }
        )
        for genre in genres:
            genre_counts[genre] += 1

    return {
        "schema": 1,
        "source": "Open Library subject indexes (exact normalized title/author match)",
        "retrieved_at": retrieved_at,
        "subject_sources": subject_sources,
        "match_method": "exact normalized title and author",
        "coverage": {
            "dataset_books": len(books),
            "matched_books": len(matched_books),
            "unmatched_books": len(books) - len(matched_books),
            "genre_book_counts": genre_counts,
        },
        "books": matched_books,
    }


def _dataset_books(dataset: Path) -> Dict[Tuple[str, str], Tuple[str, str]]:
    books: Dict[Tuple[str, str], Tuple[str, str]] = {}
    for row in eligible_rows(dataset, {"Title", "Author"}):
        title = str(row.get("Title") or "").strip()
        author = str(row.get("Author") or "").strip()
        if title and author:
            books.setdefault(
                (normalize(title), normalize(author)),
                (title, author),
            )
    if not books:
        raise ValueError("Literary Clock dataset contains no eligible books")
    return books


def _load_subject_page(
    cache_dir: Path,
    subject: str,
    offset: int,
    source_url: str,
    *,
    refresh: bool,
) -> Dict[str, object]:
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / f"{subject}-{offset}.json"
    if refresh or not cache_path.exists():
        request = urllib.request.Request(source_url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(request, timeout=60) as response:
            cache_path.write_bytes(response.read())
        # Open Library permits three requests/second for identified clients.
        time.sleep(0.35)
    return json.loads(cache_path.read_text(encoding="utf-8"))


def _subject_url(subject: str, offset: int) -> str:
    query = urllib.parse.urlencode(
        {"limit": PAGE_SIZE, "offset": offset, "details": "false"}
    )
    return f"https://openlibrary.org/subjects/{subject}.json?{query}"


def main(argv: Iterable[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=Path("build/open-library-subjects"),
    )
    parser.add_argument(
        "--pages",
        type=int,
        default=3,
        help="1,000-work pages to inspect per subject (default: 3)",
    )
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--retrieved-at", default=date.today().isoformat())
    args = parser.parse_args(argv)
    if not 1 <= args.pages <= 10:
        parser.error("--pages must be between 1 and 10")

    snapshot = build_snapshot(
        args.dataset,
        args.cache_dir,
        pages=args.pages,
        refresh=args.refresh,
        retrieved_at=args.retrieved_at,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
