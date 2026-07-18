#!/bin/sh
set -eu

ROOT="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
PROJECT_ROOT="${RECIPE_PROJECT_ROOT:-${ROOT}}"
SOURCE="${ROOT}/package"
STAGE="${RECIPE_BUILD_DIR:-${PROJECT_ROOT}/build/literary-clock-recipe}"
DIST="${RECIPE_DIST_DIR:-${PROJECT_ROOT}/dist}"
ARCHIVE="${DIST}/LITERARY_CLOCK_TRMNL_RECIPE.zip"
DATA_URL="https://raw.githubusercontent.com/cdmoro/literature-clock/cf83267d0ee007b87f235207be6741c4dc4a7e6e/quotes/quotes.en-US.csv"
DATA_SHA256="60393706e503a13be9548dc5c8c1d657b2d3be762dcbd906fa35191c575e6ef6"
GENRES_PATH="${RECIPE_GENRES_PATH:-${ROOT}/book_genres.json}"
TEMP_DIR="$(mktemp -d -t trmnl-literary-recipe.XXXXXX)"
trap 'rm -rf "${TEMP_DIR}"' EXIT HUP INT TERM

if [ -n "${RECIPE_DATA_PATH:-}" ]; then
    DATA_PATH="${RECIPE_DATA_PATH}"
else
    DATA_PATH="${TEMP_DIR}/quotes.en-US.csv"
    curl -fsSL "${DATA_URL}" -o "${DATA_PATH}"
    ACTUAL_SHA256="$(shasum -a 256 "${DATA_PATH}" | awk '{print $1}')"
    [ "${ACTUAL_SHA256}" = "${DATA_SHA256}" ] || {
        echo "Literary Clock dataset checksum mismatch" >&2
        exit 1
    }
fi

rm -rf "${STAGE}"
mkdir -p "${STAGE}" "${DIST}"
python3 "${ROOT}/build_static_recipe.py" \
    "${DATA_PATH}" \
    "${GENRES_PATH}" \
    "${SOURCE}" \
    "${STAGE}"

rm -f "${ARCHIVE}"
(
  cd "${STAGE}"
  zip -q "${ARCHIVE}" \
    settings.yml \
    full.liquid \
    half_horizontal.liquid \
    half_vertical.liquid \
    quadrant.liquid
)
printf '%s\n' "${ARCHIVE}"
