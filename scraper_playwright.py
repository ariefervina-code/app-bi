
"""Scraper Kurs Transaksi Bank Indonesia untuk Streamlit Cloud."""

import os
import re
import time
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, Error as PlaywrightError


# =========================================================
# KONFIGURASI
# =========================================================

load_dotenv()

BI_URL = os.getenv(
    "BI_URL",
    "https://www.bi.go.id/id/statistik/informasi-kurs/transaksi-bi/default.aspx",
)

TIMEOUT_MS = int(os.getenv("SCRAPE_TIMEOUT_MS", "60000"))
MAX_RETRIES = 3

MONTHS = {
    "januari": 1,
    "februari": 2,
    "maret": 3,
    "april": 4,
    "mei": 5,
    "juni": 6,
    "juli": 7,
    "agustus": 8,
    "september": 9,
    "oktober": 10,
    "november": 11,
    "desember": 12,
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "mei": 5,
    "jun": 6,
    "jul": 7,
    "agu": 8,
    "agt": 8,
    "sep": 9,
    "okt": 10,
    "nov": 11,
    "des": 12,
}


# =========================================================
# PARSING TANGGAL
# =========================================================

def parse_date(value: str) -> str:
    """Mengubah tanggal sumber menjadi format YYYY-MM-DD."""

    value = re.sub(r"\s+", " ", str(value or "").strip())

    match = re.search(
        r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})",
        value,
        flags=re.IGNORECASE,
    )

    if match:
        day, month, year = match.groups()
        month_number = MONTHS.get(month.lower())

        if month_number:
            return date(
                int(year),
                month_number,
                int(day),
            ).isoformat()

    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            continue

    raise ValueError(
        f"Tanggal sumber tidak dikenali: {value!r}. "
        "Data tidak disimpan untuk mencegah tanggal yang salah."
    )


# =========================================================
# PARSING ANGKA KURS
# =========================================================

def parse_decimal(value: str) -> float:
    """Mengubah angka dengan format Indonesia menjadi float."""

    value = re.sub(r"\s+", "", str(value or ""))
    value = value.replace("Rp", "")
    value = value.replace(".", "")
    value = value.replace(",", ".")

    try:
        number = Decimal(value)
    except (InvalidOperation, ValueError) as error:
        raise ValueError(
            f"Angka kurs tidak valid: {value!r}"
        ) from error

    if not number.is_finite():
        raise ValueError(f"Angka kurs tidak valid: {value!r}")

    return float(number)


# =========================================================
# MEMBACA TANGGAL SUMBER BI
# =========================================================

def extract_source_date(page) -> str:
    """Mengambil tanggal pembaruan dari halaman BI."""

    body_text = page.locator("body").inner_text()

    patterns = [
        r"Update\s+Terakhir\s*:?\s*(\d{1,2}\s+[A-Za-z]+\s+\d{4})",
        r"(?:Kurs\s+Tanggal|Tanggal)\s*:?\s*(\d{1,2}\s+[A-Za-z]+\s+\d{4})",
    ]

    for pattern in patterns:
        match = re.search(
            pattern,
            body_text,
            flags=re.IGNORECASE,
        )

        if match:
            return parse_date(match.group(1))

    raise ValueError(
        "Tanggal kurs tidak ditemukan pada halaman BI. "
        "Format halaman mungkin telah berubah."
    )


# =========================================================
# MEMBUKA WEBSITE BI DENGAN RETRY
# =========================================================

def open_bi_page(page) -> None:
    """Membuka halaman BI dan mencoba ulang jika gagal."""

    last_error = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            print(
                f"Membuka website BI, percobaan "
                f"{attempt}/{MAX_RETRIES}...",
                flush=True,
            )

            page.goto(
                BI_URL,
                wait_until="domcontentloaded",
                timeout=TIMEOUT_MS,
            )

            page.get_by_text(
                "USD",
                exact=True,
            ).last.wait_for(
                state="visible",
                timeout=15000,
            )

            print("Halaman BI berhasil dibuka.", flush=True)
            return

        except PlaywrightError as error:
            last_error = error

            print(
                f"Gagal mengakses halaman BI: {error}",
                flush=True,
            )

            if attempt < MAX_RETRIES:
                time.sleep(3 * attempt)

    raise RuntimeError(
        "Website BI gagal diakses setelah "
        f"{MAX_RETRIES} percobaan. "
        "Periksa koneksi Streamlit Cloud atau akses website BI."
    ) from last_error


# =========================================================
# MEMBACA TABEL KURS
# =========================================================

def extract_kurs_records(page, tanggal: str) -> list[dict]:
    """Membaca tabel kurs jual, kurs beli, dan nilai."""

    records = []
    tables = page.locator("table")

    for i in range(tables.count()):
        table = tables.nth(i)
        header_text = table.inner_text().lower()

        required_headers = (
            "mata uang",
            "kurs jual",
            "kurs beli",
        )

        if not all(
            header in header_text
            for header in required_headers
        ):
            continue

        rows = table.locator("tr")

        for j in range(rows.count()):
            cells = rows.nth(j).locator("td")

            if cells.count() < 4:
                continue

            values = [
                cells.nth(k).inner_text().strip()
                for k in range(4)
            ]

            currency = values[0].upper()

            if not re.fullmatch(r"[A-Z]{3}", currency):
                continue

            try:
                record = {
                    "tanggal": tanggal,
                    "mata_uang": currency,
                    "nilai": parse_decimal(values[1]),
                    "kurs_jual": parse_decimal(values[2]),
                    "kurs_beli": parse_decimal(values[3]),
                    "sumber": BI_URL,
                }

                if (
                    record["nilai"] > 0
                    and record["kurs_jual"] > 0
                    and record["kurs_beli"] > 0
                ):
                    records.append(record)

            except ValueError as error:
                print(
                    f"Baris {currency} dilewati: {error}",
                    flush=True,
                )

        if records:
            break

    # Hilangkan duplikat berdasarkan kode mata uang
    unique_records = {
        record["mata_uang"]: record
        for record in records
    }

    return list(unique_records.values())


# =========================================================
# FUNGSI UTAMA SCRAPER
# =========================================================

def scrape_kurs(headless: bool = True) -> tuple[str, list[dict]]:
    """
    Mengambil data kurs yang sedang ditampilkan pada halaman BI.

    Mengembalikan:
        tanggal: tanggal sumber dalam format YYYY-MM-DD
        records: daftar data kurs per mata uang
    """

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=headless,
        )

        try:
            context = browser.new_context(
                locale="id-ID",
                viewport={
                    "width": 1440,
                    "height": 900,
                },
            )

            page = context.new_page()
            page.set_default_timeout(TIMEOUT_MS)

            # Buka halaman dan coba ulang jika koneksi gagal
            open_bi_page(page)

            # Pastikan tanggal berasal dari halaman BI
            tanggal = extract_source_date(page)

            print(
                f"Tanggal sumber BI: {tanggal}",
                flush=True,
            )

            # Ambil data kurs
            records = extract_kurs_records(page, tanggal)

            if not records:
                diagnostic_path = Path("data/debug_bi.html")
                diagnostic_path.parent.mkdir(
                    parents=True,
                    exist_ok=True,
                )

                diagnostic_path.write_text(
                    page.content(),
                    encoding="utf-8",
                )

                raise RuntimeError(
                    "Tabel kurs tidak terbaca. "
                    "Halaman diagnostik disimpan di "
                    "data/debug_bi.html."
                )

            print(
                f"Berhasil mengambil {len(records)} "
                f"mata uang untuk tanggal {tanggal}.",
                flush=True,
            )

            return tanggal, records

        finally:
            browser.close()
