import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from subprocess import run


RECIPE = Path(__file__).resolve().parent
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
            dataset.write_text(
                "Time|Id|Quote time|Quote|Title|Author|SFW\n"
                "09:23|0923-001|twenty-three past nine|At twenty-three past nine the train left.|Book A|Author A|sfw\n"
                "09:24|0924-001|nine twenty-four|At nine twenty-four something unsafe happened.|Book B|Author B|nsfw\n"
                "09:25|0925-001|twenty-five past nine|At twenty-five past nine the bell rang.|Book C|Author C|unknown\n",
                encoding="utf-8",
            )
            archive = Path(tmp) / "recipe.zip"
            run(
                [str(RECIPE / "build-recipe-package.sh")],
                cwd=RECIPE,
                env={
                    "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
                    "RECIPE_DATA_PATH": str(dataset),
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
            self.assertEqual(set(static_data["quotes"]), {"0923", "0925"})
            self.assertEqual(static_data["nearest"]["0924"], "0923")
            self.assertEqual(
                static_data["metadata"]["license"].splitlines()[0],
                "MIT License",
            )
            self.assertEqual(
                static_data["metadata"]["commit"],
                "cf83267d0ee007b87f235207be6741c4dc4a7e6e",
            )
            self.assertNotIn("unsafe", json.dumps(static_data))
            compact = json.dumps(
                static_data,
                ensure_ascii=False,
                separators=(",", ":"),
            )
            self.assertLess(len(compact.encode()), 1_000_000)
            for layout in layouts.values():
                self.assertIn('assign local_epoch = "now"', layout)
                self.assertIn("assign choices = quotes[quote_time_key]", layout)
                self.assertIn("trmnl.user.utc_offset", layout)


def _static_data(settings: str) -> dict:
    marker = "static_data: |-\n  "
    start = settings.index(marker) + len(marker)
    payload = settings[start:].splitlines()[0]
    return json.loads(payload)


if __name__ == "__main__":
    unittest.main()
