
"""Dedicated Playwright worker for Bank Indonesia exchange rates."""

import argparse
import json
import subprocess
import sys
import traceback
import urllib.request
from pathlib import Path

from scraper_playwright import scrape_kurs


# =========================================================
# KONFIGURASI
# =========================================================

BI_URL = (
    "https://www.bi.go.id/id/statistik/"
    "informasi-kurs/transaksi-bi/default.aspx"
)


# =========================================================
# INSTALASI CHROMIUM
# =========================================================

def ensure_chromium_installed():
    """Memastikan browser Chromium tersedia untuk Playwright."""

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


# =========================================================
# TES KONEKSI WEBSITE BI
# =========================================================

def test_bi_connection():
    """Menguji koneksi HTTP dari Streamlit Cloud ke website BI."""

    print("Menguji koneksi langsung ke website BI...", flush=True)

    request = urllib.request.Request(
        BI_URL,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) "
                "AppleWebKit/537.36 Chrome/131.0.0.0 "
                "Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml",
        },
    )

    try:
        with urllib.request.urlopen(
            request,
            timeout=20,
        ) as response:
            print(
                f"Koneksi BI berhasil. HTTP {response.status}",
                flush=True,
            )
            print(
                "Content-Type:",
                response.headers.get("Content-Type"),
                flush=True,
            )

    except Exception as error:
        print(
            f"Koneksi langsung ke BI gagal: "
            f"{type(error).__name__}: {error}",
            flush=True,
        )
        raise


# =========================================================
# PROSES UTAMA
# =========================================================

def main():
    parser = argparse.ArgumentParser(
        description="Mengambil data kurs transaksi Bank Indonesia."
    )

    parser.add_argument(
        "--output",
        required=True,
        help="Lokasi file JSON untuk menyimpan hasil scraper.",
    )

    parser.add_argument(
        "--headless",
        choices=["true", "false"],
        default="true",
        help="Mode browser. Di Streamlit Cloud gunakan true.",
    )

    args = parser.parse_args()

    try:
        # 1. Pastikan Chromium tersedia
        ensure_chromium_installed()

        # 2. Tes koneksi HTTP ke website BI
        test_bi_connection()

        # 3. Ambil data kurs menggunakan browser headless
        print("Memulai proses scraping kurs BI...", flush=True)

        tanggal, records = scrape_kurs(headless=True)

        if not records:
            raise ValueError(
                "BI tidak mengembalikan data kurs."
            )

        # 4. Simpan hasil ke file JSON
        target = Path(args.output)
        target.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        result = {
            "tanggal": tanggal,
            "records": records,
        }

        target.write_text(
            json.dumps(
                result,
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        print(
            f"Berhasil mengambil {len(records)} data kurs "
            f"untuk tanggal {tanggal}.",
            flush=True,
        )

        print(
            f"Hasil disimpan ke: {target}",
            flush=True,
        )

        return 0

    except Exception:
        print(
            "Proses scraper gagal. Detail error:",
            file=sys.stderr,
            flush=True,
        )
        traceback.print_exc(file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
