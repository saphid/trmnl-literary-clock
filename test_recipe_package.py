import hashlib
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from subprocess import run

RECIPE = Path(__file__).resolve().parent
sys.path.insert(0, str(RECIPE))

from build_static_recipe import GENRES, _segments, build_static_data
from update_book_genres import OPEN_LIBRARY_SUBJECTS, build_snapshot


REQUIRED_FILES = {
    "settings.yml",
    "full.liquid",
    "half_horizontal.liquid",
    "half_vertical.liquid",
    "quadrant.liquid",
}


class RecipePackageTests(unittest.TestCase):
    def test_source_contains_every_trmnl_layout(self) -> None:
        package = RECIPE / "package"
        self.assertTrue((package / "settings.yml.in").exists())
        for name in REQUIRED_FILES - {"settings.yml"}:
            self.assertTrue((package / name).exists(), name)

    def test_build_creates_a_flat_importable_zip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dataset = Path(tmp) / "quotes.csv"
            genres = Path(tmp) / "book-genres.json"
            dataset.write_text(
                "Time|Id|Quote time|Quote|Title|Author|SFW\n"
                "09:23|0923-001|twenty-three past nine|At twenty-three past nine the train left.|Book A|Author A|sfw\n"
                "09:24|0924-001|nine twenty-four|At nine twenty-four something unsafe happened.|Book B|Author B|nsfw\n"
                "09:25|0925-001|twenty-five past nine|At twenty-five past nine the bell rang.|Book C|Author C|unknown\n",
                encoding="utf-8",
            )
            genres.write_text(
                json.dumps(
                    {
                        "schema": 1,
                        "source": "test fixture",
                        "books": [
                            {
                                "title": "Book A",
                                "author": "Author A",
                                "genres": ["science_fiction", "fantasy"],
                            },
                            {
                                "title": "Book C",
                                "author": "Author C",
                                "genres": ["romance"],
                            },
                        ],
                    }
                ),
                encoding="utf-8",
            )
            archive = Path(tmp) / "recipe.zip"
            run(
                [str(RECIPE / "build-recipe-package.sh")],
                cwd=RECIPE,
                env={
                    "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
                    "RECIPE_DATA_PATH": str(dataset),
                    "RECIPE_GENRES_PATH": str(genres),
                    "RECIPE_BUILD_DIR": str(Path(tmp) / "build"),
                    "RECIPE_DIST_DIR": str(Path(tmp) / "dist"),
                },
                check=True,
                capture_output=True,
                text=True,
            )
            built = Path(tmp) / "dist" / "LITERARY_CLOCK_TRMNL_RECIPE.zip"
            archive.write_bytes(built.read_bytes())
            with zipfile.ZipFile(archive) as bundle:
                self.assertEqual(set(bundle.namelist()), REQUIRED_FILES)
                settings = bundle.read("settings.yml").decode()
                layouts = {
                    name: bundle.read(name).decode()
                    for name in REQUIRED_FILES - {"settings.yml"}
                }

            static_data = _static_data(settings)
            self.assertIn("strategy: static", settings)
            self.assertIn("refresh_interval: 15", settings)
            self.assertNotIn("polling_url", settings)
            self.assertNotIn("RECIPE_ENDPOINT", settings)
            self.assertIn("field_type: select", settings)
            self.assertIn("Science Fiction: s", settings)
            self.assertIn("Romance: r", settings)
            self.assertEqual(static_data["titles"], ["Book A", "Book C"])
            self.assertEqual(static_data["authors"], ["Author A", "Author C"])
            self.assertEqual(len(static_data["quotes"]), 2)
            self.assertEqual(len(static_data["minutes"]), 1440)
            self.assertEqual(static_data["minutes"][9 * 60 + 23], [0])
            self.assertEqual(static_data["minutes"][9 * 60 + 25], [1])
            self.assertEqual(static_data["quote_genres"], ["fs", "r"])
            for quote_ids in static_data["minutes"]:
                self.assertTrue(
                    all(0 <= quote_id < len(static_data["quotes"]) for quote_id in quote_ids)
                )
            for quote in static_data["quotes"]:
                self.assertTrue(0 <= quote[3] < len(static_data["titles"]))
                self.assertTrue(0 <= quote[4] < len(static_data["authors"]))
            for code, source_minutes in static_data["nearest"].items():
                self.assertEqual(len(source_minutes), 1440, code)
                self.assertTrue(all(0 <= minute < 1440 for minute in source_minutes))
            self.assertEqual(
                static_data["nearest"]["s"][9 * 60 + 24],
                9 * 60 + 23,
            )
            self.assertEqual(
                static_data["nearest"]["r"][9 * 60 + 24],
                9 * 60 + 25,
            )
            self.assertEqual(static_data["metadata"]["commit"], "custom")
            self.assertEqual(
                static_data["metadata"]["sha256"],
                hashlib.sha256(dataset.read_bytes()).hexdigest(),
            )
            self.assertNotIn("Mystery & Crime", settings)
            self.assertNotIn("unsafe", json.dumps(static_data))
            compact = json.dumps(
                static_data,
                ensure_ascii=False,
                separators=(",", ":"),
            )
            self.assertLess(len(compact.encode()), 1_000_000)
            for layout in layouts.values():
                self.assertIn('assign local_epoch = "now"', layout)
                self.assertIn(
                    "trmnl.plugin_settings.custom_fields_values.genre",
                    layout,
                )
                self.assertIn("assign choices = minutes[source_minute]", layout)
                self.assertIn("candidate_genres contains selected_genre", layout)
                self.assertIn("trmnl.user.utc_offset", layout)
                self.assertNotIn("quotes[choices[0]]", layout)
                self.assertIn("No matching quotes", layout)
                self.assertNotIn("__QUOTE_FOOTER__", layout)

    def test_builder_rejects_quote_when_highlight_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dataset = root / "quotes.csv"
            dataset.write_text(
                "Time|Id|Quote time|Quote|Title|Author|SFW\n"
                "09:23|0923-001|twenty-three past nine|At nine the train left.|Book A|Author A|sfw\n",
                encoding="utf-8",
            )
            genres = root / "book-genres.json"
            genres.write_text('{"schema":1,"books":[]}', encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "highlight"):
                build_static_data(dataset, genres)

    def test_highlight_offsets_survive_unicode_case_folding(self) -> None:
        self.assertEqual(
            _segments("Straße at noon", "AT NOON"),
            ("Straße ", "at noon", ""),
        )

    def test_builder_rejects_unknown_genre_snapshot_schema(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dataset = _write_dataset(Path(tmp))
            genres = Path(tmp) / "book-genres.json"
            genres.write_text('{"schema":2,"books":[]}', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "schema"):
                build_static_data(dataset, genres)

    def test_builder_rejects_unknown_genre_name(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dataset = _write_dataset(Path(tmp))
            genres = Path(tmp) / "book-genres.json"
            genres.write_text(
                json.dumps(
                    {
                        "schema": 1,
                        "books": [
                            {
                                "title": "Book A",
                                "author": "Author A",
                                "genres": ["space_opera"],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "unknown book genre"):
                build_static_data(dataset, genres)

    def test_genre_snapshot_uses_exact_title_author_matches(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dataset = _write_dataset(root)
            cache = root / "cache"
            for subject in OPEN_LIBRARY_SUBJECTS.values():
                works = []
                if subject == "science_fiction":
                    works = [
                        {
                            "title": "Book A",
                            "authors": [{"name": "Author A"}],
                        },
                        {
                            "title": "Book C",
                            "authors": [{"name": "Wrong Author"}],
                        },
                    ]
                (cache / f"{subject}-0.json").parent.mkdir(
                    parents=True,
                    exist_ok=True,
                )
                (cache / f"{subject}-0.json").write_text(
                    json.dumps({"works": works}),
                    encoding="utf-8",
                )

            snapshot = build_snapshot(
                dataset,
                cache,
                pages=1,
                refresh=False,
                retrieved_at="2026-07-18",
            )
            self.assertEqual(snapshot["coverage"]["dataset_books"], 2)
            self.assertEqual(snapshot["coverage"]["matched_books"], 1)
            self.assertEqual(
                snapshot["books"],
                [
                    {
                        "title": "Book A",
                        "author": "Author A",
                        "genres": ["science_fiction"],
                    }
                ],
            )

    def test_production_snapshot_and_static_indexes_are_consistent(self) -> None:
        snapshot_path = RECIPE / "book_genres.json"
        if not snapshot_path.exists():
            self.skipTest("production genre snapshot not generated yet")
        snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
        counts = snapshot["coverage"]["genre_book_counts"]
        self.assertTrue(all(counts[name] > 0 for name in GENRES), counts)
        self.assertEqual(
            snapshot["coverage"]["dataset_books"],
            snapshot["coverage"]["matched_books"]
            + snapshot["coverage"]["unmatched_books"],
        )


def _write_dataset(root: Path) -> Path:
    dataset = root / "quotes.csv"
    dataset.write_text(
        "Time|Id|Quote time|Quote|Title|Author|SFW\n"
        "09:23|0923-001|twenty-three past nine|At twenty-three past nine the train left.|Book A|Author A|sfw\n"
        "09:24|0924-001|nine twenty-four|At nine twenty-four something unsafe happened.|Book B|Author B|nsfw\n"
        "09:25|0925-001|twenty-five past nine|At twenty-five past nine the bell rang.|Book C|Author C|unknown\n",
        encoding="utf-8",
    )
    return dataset


def _static_data(settings: str) -> dict:
    marker = "static_data: |-\n  "
    start = settings.index(marker) + len(marker)
    payload = settings[start:].splitlines()[0]
    return json.loads(payload)


if __name__ == "__main__":
    unittest.main()
