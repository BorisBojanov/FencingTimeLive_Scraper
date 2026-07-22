"""
Post-processing step for the DB compile.

Scans a directory of scraped CSVs (from the FencingTimeLive scripts), groups
files by tournament, applies canonical AB Cup labels (auto-detect + overrides),
infers season, and emits tournament_manifest.json.

Also reports issues that would trip up the DB import:
  - duplicate URLs in tournament_urls.txt
  - tournaments missing one or more of the 4 expected CSVs
  - URL / tournament count gap (URLs in the list vs unique CSV basenames on disk)
  - ambiguous / unresolved AB Cup labels

Usage:
    python3 format_for_db.py \\
        --csv-dir "/Users/boris/Desktop/AFA Season 2024-2026" \\
        --urls tournament_urls.txt \\
        --overrides ab_cup_overrides.json \\
        --out tournament_manifest.json
"""

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path

CSV_SUFFIXES = ("_bout_orders.csv", "_fencing_results.csv", "_paired_matches.csv", "_pool_sheets.csv")

# Matches "AB Cup #2", "AB_Cup_2", "Alberta Cup #3", "Alberta_Cup_3", etc.
AB_CUP_RE = re.compile(r"(?:AB|Alberta)[\s_]*Cup[\s_]*#?(\d+)", re.IGNORECASE)

# Season patterns, longest-first so 2024-2025 wins over 2024-25 wins over 2024.
SEASON_PATTERNS = [
    (re.compile(r"20(\d{2})[-/]20(\d{2})"), "long"),   # 2024-2025 or 2025-2026
    (re.compile(r"20(\d{2})[-/](\d{2})"),   "mixed"),  # 2024-25
    (re.compile(r"(?<!\d)(\d{2})[-/](\d{2})(?!\d)"), "short"),  # 24-25 / 24/25
]

YEAR_RE = re.compile(r"20(\d{2})")


def strip_suffix(filename: str) -> str | None:
    for sfx in CSV_SUFFIXES:
        if filename.endswith(sfx):
            return filename[: -len(sfx)]
    return None


def infer_season(name: str) -> tuple[str | None, str]:
    """Return (season, confidence) — confidence is 'explicit' | 'guessed' | 'unknown'."""
    for pat, kind in SEASON_PATTERNS:
        m = pat.search(name)
        if not m:
            continue
        a, b = m.group(1), m.group(2)
        if kind == "long":
            return f"{a}/{b}", "explicit"
        if kind == "mixed":
            return f"{a}/{b}", "explicit"
        if kind == "short":
            return f"{a}/{b}", "explicit"

    years = [int(y) for y in YEAR_RE.findall(name)]
    if len(years) == 1:
        return None, "ambiguous_single_year"
    return None, "unknown"


def apply_labeling(basename: str, overrides: dict, review: dict) -> dict:
    """Decide canonical_name / season / is_ab_cup for one tournament basename."""
    # 1. Explicit override wins.
    if basename in overrides:
        ov = overrides[basename]
        return {
            "canonical_name": ov["canonical"],
            "season": ov.get("season"),
            "cup_number": ov.get("cup_number"),
            "is_ab_cup": True,
            "label_source": "override",
        }

    # 2. Regex auto-detect for AB Cup / Alberta Cup #N in the raw name.
    m = AB_CUP_RE.search(basename)
    if m:
        cup_number = int(m.group(1))
        season, season_confidence = infer_season(basename)
        # Review section may supply a season guess for review_needed items.
        if season is None and basename in review:
            season = review[basename].get("guess_season")
            season_confidence = "review_guess" if season else season_confidence
        canonical = f"{season} AB Cup #{cup_number}" if season else f"?? AB Cup #{cup_number}"
        return {
            "canonical_name": canonical,
            "season": season,
            "cup_number": cup_number,
            "is_ab_cup": True,
            "label_source": "auto",
            "season_confidence": season_confidence,
        }

    # 3. Not an AB Cup — keep raw name.
    season, season_confidence = infer_season(basename)
    return {
        "canonical_name": basename.replace("_", " "),
        "season": season,
        "cup_number": None,
        "is_ab_cup": False,
        "label_source": "raw",
        "season_confidence": season_confidence,
    }


def group_csvs(csv_dir: Path) -> dict[str, dict[str, str]]:
    """Return {basename: {file_type: filename}} for every *.csv in csv_dir."""
    groups: dict[str, dict[str, str]] = defaultdict(dict)
    for f in sorted(csv_dir.iterdir()):
        if not f.is_file() or not f.name.endswith(".csv"):
            continue
        base = strip_suffix(f.name)
        if not base:
            continue  # csv with an unrecognized suffix — skip
        for sfx in CSV_SUFFIXES:
            if f.name.endswith(sfx):
                # Strip the leading underscore too: "_bout_orders.csv" -> "bout_orders"
                file_type = sfx[1:-4]
                groups[base][file_type] = f.name
                break
    return groups


def read_urls(path: Path) -> list[str]:
    if not path.exists():
        return []
    return [line.strip() for line in path.read_text().splitlines() if line.strip()]


def find_duplicate_urls(urls: list[str]) -> list[tuple[str, list[int]]]:
    positions: dict[str, list[int]] = defaultdict(list)
    for i, u in enumerate(urls, start=1):
        positions[u].append(i)
    return [(u, lines) for u, lines in positions.items() if len(lines) > 1]


def build_manifest(csv_dir: Path, overrides_path: Path) -> tuple[dict, dict]:
    overrides_doc = json.loads(overrides_path.read_text()) if overrides_path.exists() else {}
    overrides = overrides_doc.get("overrides", {})
    review = overrides_doc.get("review_needed", {})

    groups = group_csvs(csv_dir)
    manifest: dict[str, dict] = {}
    for basename, files in sorted(groups.items()):
        label = apply_labeling(basename, overrides, review)
        expected = {sfx[1:-4] for sfx in CSV_SUFFIXES}
        present = set(files.keys())
        manifest[basename] = {
            **label,
            "raw_name": basename,
            "csv_files": files,
            "complete": expected == present,
            "missing_files": sorted(expected - present),
            "in_review_needed": basename in review,
        }
    return manifest, {"overrides_count": len(overrides), "review_needed_count": len(review)}


def report(manifest: dict, urls: list[str], overrides_path: Path) -> str:
    lines: list[str] = []

    lines.append("=" * 70)
    lines.append("TOURNAMENT MANIFEST REPORT")
    lines.append("=" * 70)

    # URL summary.
    unique_urls = set(urls)
    lines.append(f"\nURLs in tournament_urls.txt: {len(urls)} ({len(unique_urls)} unique)")
    dupes = find_duplicate_urls(urls)
    if dupes:
        lines.append(f"  Duplicate URLs: {len(dupes)}")
        for u, positions in dupes:
            lines.append(f"    line {positions}: {u}")
    else:
        lines.append("  No duplicate URLs.")

    # CSV summary.
    lines.append(f"\nTournaments on disk (unique CSV basenames): {len(manifest)}")
    gap = len(unique_urls) - len(manifest)
    if gap > 0:
        lines.append(f"  Gap: {gap} URL(s) in list without a matching CSV basename.")
        lines.append("  (Heuristic-only: URLs are opaque hashes, so I can't say WHICH ones")
        lines.append("   without scraping. Re-run runAllTheFencingTimeScripts.py to fill.)")
    elif gap < 0:
        lines.append(f"  {-gap} more CSV basename(s) than unique URLs — orphan CSVs?")
    else:
        lines.append("  Counts match.")

    # Incomplete CSV sets.
    incomplete = [(b, m) for b, m in manifest.items() if not m["complete"]]
    lines.append(f"\nIncomplete CSV sets: {len(incomplete)}")
    for base, m in incomplete:
        lines.append(f"  {base}: missing {m['missing_files']}")

    # AB Cup labels.
    ab_cups = [(b, m) for b, m in manifest.items() if m["is_ab_cup"]]
    lines.append(f"\nAB Cup labels applied: {len(ab_cups)}")
    for base, m in sorted(ab_cups, key=lambda x: (x[1].get("season") or "zz", x[1].get("cup_number") or 0)):
        src = m["label_source"]
        conf = m.get("season_confidence", "")
        conf_str = f" [{conf}]" if conf and conf != "explicit" else ""
        lines.append(f"  {m['canonical_name']:<28} <- {base}   ({src}{conf_str})")

    # Overrides that don't resolve to a CSV on disk.
    overrides_doc = json.loads(overrides_path.read_text()) if overrides_path.exists() else {}
    override_keys = set(overrides_doc.get("overrides", {}).keys())
    review_keys = set(overrides_doc.get("review_needed", {}).keys())
    missing_override_files = sorted(override_keys - manifest.keys())
    missing_review_files = sorted(review_keys - manifest.keys())
    if missing_override_files:
        lines.append(f"\nOverrides pointing at basenames NOT on disk: {len(missing_override_files)}")
        for k in missing_override_files:
            lines.append(f"  {k}")
    if missing_review_files:
        lines.append(f"\nreview_needed entries NOT on disk: {len(missing_review_files)}")
        for k in missing_review_files:
            lines.append(f"  {k}")

    # Ambiguous seasons.
    ambiguous = [(b, m) for b, m in manifest.items() if m.get("season_confidence") == "ambiguous_single_year"]
    if ambiguous:
        lines.append(f"\nAmbiguous single-year names (season not certain): {len(ambiguous)}")
        for base, m in ambiguous:
            lines.append(f"  {base}   (currently: {m['canonical_name']})")

    # Non-AB-Cup, kept raw.
    raws = [(b, m) for b, m in manifest.items() if not m["is_ab_cup"]]
    lines.append(f"\nNon-AB-Cup tournaments (kept raw): {len(raws)}")

    lines.append("")
    return "\n".join(lines)


def main() -> None:
    default_csv = Path("/Users/boris/Desktop/AFA Season 2024-2026")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv-dir", type=Path, default=default_csv)
    parser.add_argument("--urls", type=Path, default=Path("tournament_urls.txt"))
    parser.add_argument("--overrides", type=Path, default=Path("ab_cup_overrides.json"))
    parser.add_argument("--out", type=Path, default=Path("tournament_manifest.json"))
    args = parser.parse_args()

    if not args.csv_dir.is_dir():
        raise SystemExit(f"CSV dir not found: {args.csv_dir}")

    manifest, meta = build_manifest(args.csv_dir, args.overrides)
    urls = read_urls(args.urls)

    args.out.write_text(json.dumps({
        "meta": {
            "csv_dir": str(args.csv_dir),
            "urls_file": str(args.urls),
            "overrides_file": str(args.overrides),
            "url_count": len(urls),
            "unique_url_count": len(set(urls)),
            "tournament_count": len(manifest),
            **meta,
        },
        "tournaments": manifest,
    }, indent=2))

    print(report(manifest, urls, args.overrides))
    print(f"Manifest written to {args.out}")


if __name__ == "__main__":
    main()
