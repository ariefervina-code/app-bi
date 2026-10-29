
"""Dedicated Playwright worker. Run separately from the Streamlit event loop."""
import argparse
import json
import sys
import traceback
import subprocess
from pathlib import Path

from playwright.sync_api import sync_playwright
from scraper_playwright import scrape_kurs


def ensure_chromium_installed():
    """Install Chromium if its executable is missing."""
    with sync_playwright() as p:
        browser_path = Path(p.chromium.executable_path)

    if not browser_path.exists():
        print("Chromium belum tersedia. Menginstal browser...", flush=True)
        subprocess.run(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            check=True
        )
        print("Instalasi Chromium selesai.", flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument(
        "--headless",
        choices=["true", "false"],
        default="false"
    )
    args = parser.parse_args()

    try:
        ensure_chromium_installed()

        tanggal, records = scrape_kurs(
            headless=(args.headless == "true")
        )

        if not records:
            raise ValueError("BI tidak mengembalikan baris kurs.")

        target = Path(args.output)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(
                {"tanggal": tanggal, "records": records},
                ensure_ascii=False
            ),
            encoding="utf-8"
        )

    except Exception:
        traceback.print_exc(file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
