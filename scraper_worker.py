
"""Dedicated Playwright worker. Run separately from the Streamlit event loop."""
import argparse
import json
import sys
import traceback
import subprocess
from pathlib import Path

from scraper_playwright import scrape_kurs


def ensure_chromium_installed():
    """Ensure the Playwright Chromium browser is available."""
    print("Memeriksa instalasi Chromium...", flush=True)

    subprocess.run(
        [
            sys.executable,
            "-m",
            "playwright",
            "install",
            "chromium",
        ],
        check=True,
    )

    print("Chromium siap digunakan.", flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument(
        "--headless",
        choices=["true", "false"],
        default="true",
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
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        print(
            f"Berhasil mengambil {len(records)} data kurs "
            f"untuk tanggal {tanggal}.",
            flush=True,
        )

    except Exception:
        traceback.print_exc(file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
