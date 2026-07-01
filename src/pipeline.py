from __future__ import annotations

import argparse
import csv
import html
import json
import os
import re
import shutil
import ssl
import unicodedata
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from zipfile import ZipFile
import xml.etree.ElementTree as ET

from schema import (
    BRAND_TO_QA_SHEET,
    CANONICAL_FIELD_ORDER,
    MEDIA_TYPE_SLUGS,
    RAW_SHEET_NAME,
    RAW_TO_CANONICAL_COLUMNS,
    SPANISH_MONTHS,
    is_excluded_product_brand,
)


ROOT_DIR = Path(__file__).resolve().parent.parent
PROCESSED_DETAIL_OUTPUT = ROOT_DIR / "input" / "processed" / "latest_base_bruta.csv"
MASTER_CSV_OUTPUT = ROOT_DIR / "output" / "master" / "master_investment_detail.csv"
MASTER_JSON_OUTPUT = ROOT_DIR / "output" / "master" / "master_investment_detail.json"
PRODUCT_OUTPUT_DIR = ROOT_DIR / "output" / "data_products" / "inversion_semanal_por_casino_ilegal"
CHANGES_OUTPUT_DIR = ROOT_DIR / "output" / "data_products" / "cambios_vs_corte_anterior_semanal"
PAYMENT_PROCESSOR_INPUT_DIR = ROOT_DIR / "input" / "url_payment_processors"
PAYMENT_PROCESSOR_OUTPUT_DIR = ROOT_DIR / "output" / "data_products" / "infraestructura_pagos_urls"
INFOLOBBY_OUTPUT_DIR = ROOT_DIR / "output" / "data_products" / "lobby_casas_apuesta"
VISUALIZATION_OUTPUT_DIR = ROOT_DIR / "output" / "visualizations"
SITE_OUTPUT_DIR = ROOT_DIR / "output" / "site"
VALIDATION_OUTPUT = ROOT_DIR / "output" / "master" / "validation_report.json"
QA_OUTPUT = ROOT_DIR / "output" / "master" / "qa_report.json"
VISUALIZATION_HTML_OUTPUT = VISUALIZATION_OUTPUT_DIR / "inversion_semanal_por_casino_ilegal.html"
VISUALIZATION_DATA_OUTPUT = VISUALIZATION_OUTPUT_DIR / "inversion_semanal_por_casino_ilegal_summary.json"
STACKED_SVG_OUTPUT = VISUALIZATION_OUTPUT_DIR / "inversion_por_marca_stackeada.svg"
HEATMAP_SVG_OUTPUT = VISUALIZATION_OUTPUT_DIR / "inversion_por_semana_heatmap.svg"
SITE_INDEX_OUTPUT = SITE_OUTPUT_DIR / "index.html"
SITE_VERSIONS_OUTPUT = SITE_OUTPUT_DIR / "versiones.json"
SITE_VERSIONS_DIR = SITE_OUTPUT_DIR / "versiones"
SITE_SUMMARY_OUTPUT = SITE_OUTPUT_DIR / "data" / "inversion_semanal_por_casino_ilegal_summary.json"
SITE_MASTER_OUTPUT = SITE_OUTPUT_DIR / "data" / "master_investment_detail.json"
SITE_PAYMENT_PROCESSOR_OUTPUT_DIR = SITE_OUTPUT_DIR / "data" / "infraestructura_pagos_urls"
SITE_INFOLOBBY_OUTPUT_DIR = SITE_OUTPUT_DIR / "data" / "lobby_casas_apuesta"
REPO_URL = "https://github.com/dna33/casas_de_apuesta_y_casinos_ilegales"
AJUTER_URL = "https://ajuter.org/"
AJUTER_LUDOPATIA_URL = "https://ajuter.org/que-es-la-ludopatia/"
INFOLOBBY_CATALOG_URL = "https://www.infolobby.cl/DatosAbiertos/Catalogos"
INFOLOBBY_CACHE_DIR = Path(os.environ.get("INFOLOBBY_CACHE_DIR", "/tmp/infolobby"))
INFOLOBBY_INPUT_DIR = ROOT_DIR / "input" / "infolobby"
INFOLOBBY_CATALOGS = {
    "activos.csv": "https://datosinfolobby.cplt.cl/catalogos/activos.csv",
    "datosAudiencia.csv": "https://datosinfolobby.cplt.cl/catalogos/datosAudiencia.csv",
    "asistenciasPasivos.csv": "https://datosinfolobby.cplt.cl/catalogos/asistenciasPasivos.csv",
    "representaciones.csv": "https://datosinfolobby.cplt.cl/catalogos/representaciones.csv",
    "trabajaPara.csv": "https://datosinfolobby.cplt.cl/catalogos/trabajaPara.csv",
}
INFOLOBBY_TOPIC_PATTERN = re.compile(
    r"ley\s+de\s+casino|ley\s+de\s+casinos|casinos?\s+online|casinos?\s+on\s*line|"
    r"casinos?\s+en\s+l[ií]nea|apuestas?\s+online|apuestas?\s+on\s*line|"
    r"apuestas?\s+en\s+l[ií]nea|plataformas?\s+de\s+apuestas|"
    r"juegos?\s+de\s+azar\s+en\s+l[ií]nea|casas?\s+de\s+apuestas|"
    r"proyecto\s+de\s+ley.*apuestas|proyecto\s+de\s+ley.*casinos?",
    re.IGNORECASE,
)
RAW_SHEET_CANDIDATES = (RAW_SHEET_NAME, "DATOS")
SUMMARY_SHEET_CANDIDATES = ("RESUMEN", "CRUCES")
PAYMENT_PROCESSOR_FIELD_ORDER = [
    "observed_at",
    "brand_name",
    "url",
    "domain",
    "payment_label",
    "payment_processor",
    "payment_method",
    "is_available",
    "source_file",
    "source_sheet",
]
PAYMENT_PROCESSOR_NAMES = (
    "ALPS SPA",
    "ASTROPAY",
    "BINANCE PAY",
    "CLEO",
    "ETPAY",
    "FINTOC",
    "FLOW",
    "KHIPU",
    "KUSHKI",
    "MACH",
    "MIFINITY",
    "MONNET",
    "MUCHBETTER",
    "NETELLER",
    "PAGO46",
    "PAYKU",
    "PAYRETAILERS",
    "PK",
    "PRONTOPAGA",
    "SAFETYPAY",
    "SKRILL",
    "WEBPAY",
)
PAYMENT_PROCESSOR_ALIASES = {
    "ALPS": "ALPS SPA",
}
BRAND_DOMAIN_ALIASES = {
    "APUESTAS ROYAL": ("ROYAL",),
    "BETANO": ("BETANO",),
    "BETSSON": ("BETSSON",),
    "COOLBET": ("COOLBET",),
    "EPICBET": ("EPICBET",),
    "JUGABET": ("JUGABET",),
    "LATAMWIN": ("LATAMWIN",),
    "MI CASINO": ("MICASINO",),
    "NOVIBET": ("NOVIBET",),
    "ROJABET": ("ROJABET",),
    "TONYBET": ("TONYBET",),
    "1XBET": ("1XBET",),
}
MANUAL_PRIMARY_BRAND_DOMAINS = {
    "1XBET": "1xbet.cl",
    "APUESTAS ROYAL": "apuestasroyal.com",
    "BETSSON": "betssonchile.cl",
    "COOLBET": "coolbet.com",
    "EPICBET": "epicbet.io",
    "JUEGA EN LINEA": "juegaenlinea.net",
    "LATAMWIN": "latamwin.online",
    "MI CASINO": "micasinoenvivo.com",
    "NOVIBET": "novibet.com",
    "ROJABET": "rojabet.com",
    "TONYBET": "tonybet.com",
}
GENERIC_PAYMENT_METHODS = {
    "BITCOIN": "crypto",
    "CRIPTO": "crypto",
    "DEPOSITO BANCARIO (TRANSFERENCIA)": "bank_transfer",
    "INGRESAR DEBITO/CREDITO": "card",
    "PAGO EN EFECTIVO": "cash",
}

EXCEL_NS = {
    "main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "rel": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}
EXCEL_EPOCH = datetime(1899, 12, 30)
QA_TOLERANCE = 0.01
PUBLICITY_DATA_SOURCE = "Integrametrics"
MONTH_NAMES_BY_NUMBER = {
    1: "enero",
    2: "febrero",
    3: "marzo",
    4: "abril",
    5: "mayo",
    6: "junio",
    7: "julio",
    8: "agosto",
    9: "septiembre",
    10: "octubre",
    11: "noviembre",
    12: "diciembre",
}


def find_available_workbooks() -> list[Path]:
    return sorted((ROOT_DIR / "input" / "raw").glob("*.xlsx"))


def workbook_sheet_names(workbook_path: Path) -> list[str]:
    with ZipFile(workbook_path) as workbook:
        workbook_root = ET.fromstring(workbook.read("xl/workbook.xml"))
    return [sheet.attrib["name"] for sheet in workbook_root.find("main:sheets", EXCEL_NS)]


def resolve_available_sheet_name(workbook_path: Path, candidates: tuple[str, ...]) -> str | None:
    available_sheets = set(workbook_sheet_names(workbook_path))
    return next((candidate for candidate in candidates if candidate in available_sheets), None)


def workbook_coverage_end(workbook_path: Path) -> str:
    raw_sheet_name = resolve_available_sheet_name(workbook_path, RAW_SHEET_CANDIDATES)
    if not raw_sheet_name:
        return ""
    rows = parse_worksheet_rows(workbook_path, raw_sheet_name)
    if len(rows) <= 1:
        return ""
    header_row = rows[0]
    date_column = next((column for column, header in header_row.items() if normalize_text(header) == "Fecha"), None)
    if not date_column:
        return ""
    max_date = ""
    for row in rows[1:]:
        raw_date = row.get(date_column, "")
        if not raw_date:
            continue
        iso_date = excel_serial_to_date(raw_date)
        if iso_date > max_date:
            max_date = iso_date
    return max_date


def default_input_workbook() -> Path:
    workbooks = find_available_workbooks()
    if not workbooks:
        return ROOT_DIR / "input" / "raw" / "latest.xlsx"
    return max(workbooks, key=lambda path: (workbook_coverage_end(path), path.name))


def default_previous_workbook(current_input: Path) -> Path | None:
    workbooks = [path for path in find_available_workbooks() if path.resolve() != current_input.resolve()]
    if not workbooks:
        return None
    return max(workbooks, key=lambda path: (workbook_coverage_end(path), path.name))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build weekly illegal casino investment tables from the raw workbook."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=default_input_workbook(),
        help="Path to the current raw input workbook (.xlsx). Defaults to the newest workbook under input/raw/.",
    )
    parser.add_argument(
        "--previous-input",
        type=Path,
        default=None,
        help="Optional path to the previous workbook used to compute changes between cuts.",
    )
    return parser.parse_args()


def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).strip().split())


def parse_number(value: str) -> str:
    raw = normalize_text(value)
    if not raw:
        return "0"
    number = float(raw)
    if number.is_integer():
        return str(int(number))
    return f"{number:.6f}".rstrip("0").rstrip(".")


def parse_optional_number(value: str) -> str:
    raw = normalize_text(value)
    if not raw:
        return ""
    try:
        return parse_number(raw)
    except ValueError:
        return raw


def excel_serial_to_date(value: str) -> str:
    raw = normalize_text(value)
    if not raw:
        return ""
    serial = float(raw)
    return (EXCEL_EPOCH + timedelta(days=serial)).date().isoformat()


def parse_shared_strings(workbook: ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in workbook.namelist():
        return []

    root = ET.fromstring(workbook.read("xl/sharedStrings.xml"))
    strings: list[str] = []

    for item in root.findall("main:si", EXCEL_NS):
        texts = [node.text or "" for node in item.iterfind(".//main:t", EXCEL_NS)]
        strings.append("".join(texts))

    return strings


def resolve_sheet_target(workbook: ZipFile, sheet_name: str) -> str:
    workbook_root = ET.fromstring(workbook.read("xl/workbook.xml"))
    rel_root = ET.fromstring(workbook.read("xl/_rels/workbook.xml.rels"))
    rel_map = {rel.attrib["Id"]: rel.attrib["Target"] for rel in rel_root}

    for sheet in workbook_root.find("main:sheets", EXCEL_NS):
        if sheet.attrib["name"] == sheet_name:
            relationship_id = sheet.attrib["{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"]
            return f"xl/{rel_map[relationship_id]}"

    raise ValueError(f"Worksheet not found: {sheet_name}")


def parse_worksheet_rows(workbook_path: Path, sheet_name: str) -> list[dict[str, str]]:
    with ZipFile(workbook_path) as workbook:
        shared_strings = parse_shared_strings(workbook)
        worksheet_path = resolve_sheet_target(workbook, sheet_name)
        worksheet_root = ET.fromstring(workbook.read(worksheet_path))

    rows: list[dict[str, str]] = []
    sheet_data = worksheet_root.find("main:sheetData", EXCEL_NS)
    if sheet_data is None:
        return rows

    for row in sheet_data:
        parsed_row: dict[str, str] = {}
        for cell in row.findall("main:c", EXCEL_NS):
            cell_ref = cell.attrib.get("r", "")
            column = "".join(character for character in cell_ref if character.isalpha())
            cell_type = cell.attrib.get("t")

            value = ""
            value_node = cell.find("main:v", EXCEL_NS)
            inline_node = cell.find("main:is", EXCEL_NS)

            if value_node is not None:
                raw_value = value_node.text or ""
                value = shared_strings[int(raw_value)] if cell_type == "s" else raw_value
            elif inline_node is not None:
                parts = [node.text or "" for node in inline_node.iterfind(".//main:t", EXCEL_NS)]
                value = "".join(parts)

            parsed_row[column] = value
        rows.append(parsed_row)

    return rows


def normalize_workbook_record(raw_record: dict[str, str], headers_by_column: dict[str, str]) -> dict[str, str]:
    normalized = {field: "" for field in CANONICAL_FIELD_ORDER}

    for column, raw_value in raw_record.items():
        header = headers_by_column.get(column, "")
        canonical_field = RAW_TO_CANONICAL_COLUMNS.get(header)
        if not canonical_field:
            continue
        normalized[canonical_field] = normalize_text(raw_value)

    normalized["brand_name"] = normalized["brand_name"].upper()
    normalized["media_type"] = normalized["media_type"].upper()
    normalized["month_name"] = normalized["month_name"].upper()
    normalized["observed_at"] = excel_serial_to_date(normalized["observed_at"])
    normalized["gross_investment"] = parse_number(normalized["gross_investment"])
    normalized["net_investment"] = parse_number(normalized["net_investment"])
    normalized["duration_seconds"] = parse_optional_number(normalized["duration_seconds"])
    normalized["tv_duration_seconds"] = parse_optional_number(normalized["tv_duration_seconds"])

    year = normalized["year"]
    month_number = SPANISH_MONTHS.get(normalized["month_name"])
    normalized["month"] = f"{year}-{month_number:02d}" if year and month_number else ""
    if normalized["observed_at"]:
        observed_date = datetime.fromisoformat(normalized["observed_at"]).date()
        week_ending = observed_date + timedelta(days=(6 - observed_date.weekday()))
        normalized["week_ending"] = week_ending.isoformat()

    return normalized


def load_records(input_path: Path) -> list[dict[str, str]]:
    if not input_path.exists():
        raise FileNotFoundError(
            f"Input file not found: {input_path}. Put the source workbook under input/raw/."
        )

    if input_path.suffix.lower() != ".xlsx":
        raise ValueError(f"Unsupported input format: {input_path.suffix}. Expected .xlsx")

    raw_sheet_name = resolve_available_sheet_name(input_path, RAW_SHEET_CANDIDATES)
    if not raw_sheet_name:
        raise ValueError(
            f"Could not find a supported raw sheet in {input_path.name}. Expected one of: {', '.join(RAW_SHEET_CANDIDATES)}"
        )

    rows = parse_worksheet_rows(input_path, raw_sheet_name)
    if not rows:
        raise ValueError(f"Worksheet {raw_sheet_name} is empty.")

    headers_by_column = rows[0]
    return [normalize_workbook_record(row, headers_by_column) for row in rows[1:]]


def validate_records(records: list[dict[str, str]]) -> list[str]:
    errors: list[str] = []
    required_fields = ("year", "month_name", "month", "week_ending", "observed_at", "media_type", "brand_name", "net_investment")

    for row_number, record in enumerate(records, start=2):
        for field in required_fields:
            if not record.get(field):
                errors.append(f"row {row_number}: missing required field '{field}'")

        if record.get("month_name") and record["month_name"] not in SPANISH_MONTHS:
            errors.append(f"row {row_number}: invalid month_name '{record['month_name']}'")

        if record.get("media_type") and record["media_type"] not in MEDIA_TYPE_SLUGS:
            errors.append(f"row {row_number}: unsupported media_type '{record['media_type']}'")

    return errors


def sort_periods(periods: set[str]) -> list[str]:
    return sorted(periods, key=lambda value: datetime.strptime(value, "%Y-%m-%d" if len(value) == 10 else "%Y-%m"))


def published_records(records: list[dict[str, str]]) -> list[dict[str, str]]:
    return [record for record in records if not is_excluded_product_brand(record["brand_name"])]


def format_amount(value: float) -> str:
    return f"{value:.2f}"


def format_cut_label(input_path: Path) -> str:
    coverage_end = workbook_coverage_end(input_path)
    if coverage_end:
        observed_date = datetime.fromisoformat(coverage_end).date()
        month_name = MONTH_NAMES_BY_NUMBER[observed_date.month]
        return f"Corte al {observed_date.day:02d} de {month_name} de {observed_date.year}"
    return "Corte disponible"


def format_period_label(periods: list[str]) -> str:
    if not periods:
        return "periodo disponible"

    first_date = datetime.fromisoformat(periods[0]).date()
    last_date = datetime.fromisoformat(periods[-1]).date()
    first_month = MONTH_NAMES_BY_NUMBER[first_date.month]
    last_month = MONTH_NAMES_BY_NUMBER[last_date.month]

    if first_date.year == last_date.year and first_date.month == last_date.month:
        return f"{last_month} {last_date.year}"
    if first_date.year == last_date.year:
        return f"{first_month}-{last_month} {last_date.year}"
    return f"{first_month} {first_date.year}-{last_month} {last_date.year}"


def format_publicity_source_label(input_path: Path, periods: list[str]) -> str:
    period_label = format_period_label(periods)
    cut_label = format_cut_label(input_path).lower()
    return f"{PUBLICITY_DATA_SOURCE}, periodo {period_label} ({cut_label})"


def version_id_for_input(input_path: Path) -> str:
    coverage_end = workbook_coverage_end(input_path)
    if coverage_end:
        return coverage_end
    return re.sub(r"[^a-z0-9]+", "-", input_path.stem.lower()).strip("-") or "version"


def build_site_version_entry(input_path: Path, path: str, archive_path: str) -> dict[str, str]:
    return {
        "id": version_id_for_input(input_path),
        "label": format_cut_label(input_path),
        "coverage_end": workbook_coverage_end(input_path),
        "source_file": input_path.name,
        "path": path,
        "archive_path": archive_path,
    }


def aggregate_period_tables(
    records: list[dict[str, str]],
    period_field: str,
) -> tuple[list[str], list[str], dict[str, dict[str, dict[str, float]]]]:
    product_records = [
        record for record in records if record["brand_name"] and not is_excluded_product_brand(record["brand_name"])
    ]

    periods = sort_periods({record[period_field] for record in product_records})
    brands = sorted({record["brand_name"] for record in product_records})

    aggregations: dict[str, dict[str, dict[str, float]]] = defaultdict(lambda: defaultdict(lambda: defaultdict(float)))

    for record in product_records:
        brand = record["brand_name"]
        period = record[period_field]
        media_type = record["media_type"]
        net_investment = float(record["net_investment"])

        aggregations["total"][brand][period] += net_investment
        aggregations[MEDIA_TYPE_SLUGS[media_type]][brand][period] += net_investment

    return periods, brands, aggregations


def build_summary_rows(periods: list[str], brands: list[str], values_by_brand: dict[str, dict[str, float]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []

    for brand in brands:
        period_values = values_by_brand.get(brand, {})
        total = 0.0
        row = {"brand_name": brand}
        for period in periods:
            amount = period_values.get(period, 0.0)
            row[period] = format_amount(amount)
            total += amount
        row["total"] = format_amount(total)
        rows.append(row)

    return rows


def normalize_sheet_label(value: str) -> str:
    return normalize_text(value).upper()


def excel_column_number(column_letters: str) -> int:
    value = 0
    for character in column_letters:
        value = value * 26 + (ord(character.upper()) - 64)
    return value


def parse_sheet_float(value: str) -> float:
    raw = normalize_text(value)
    if not raw:
        return 0.0
    return float(raw)


def month_label_to_iso(year: str, month_label: str) -> str:
    month_number = SPANISH_MONTHS.get(normalize_sheet_label(month_label))
    if not month_number:
        raise ValueError(f"Unsupported month label in QA sheet: {month_label}")
    return f"{year}-{month_number:02d}"


def load_resumen_expectations(input_path: Path, monthly_periods: list[str]) -> dict[str, dict[str, float]]:
    summary_sheet_name = resolve_available_sheet_name(input_path, SUMMARY_SHEET_CANDIDATES)
    if summary_sheet_name == "CRUCES":
        return load_cruces_expectations(input_path, monthly_periods)
    if not summary_sheet_name:
        return {}

    rows = parse_worksheet_rows(input_path, summary_sheet_name)
    year = monthly_periods[0][:4]
    month_columns: dict[str, str] = {}
    for column_letter, label in rows[1].items():
        normalized_label = normalize_sheet_label(label)
        if normalized_label in SPANISH_MONTHS and excel_column_number(column_letter) < excel_column_number("G"):
            month_columns[column_letter] = month_label_to_iso(year, label)
    expectations: dict[str, dict[str, float]] = {}

    for row in rows[2:]:
        brand = normalize_sheet_label(row.get("B", ""))
        if not brand:
            continue
        if brand == "TOTAL GENERAL":
            break
        if is_excluded_product_brand(brand):
            continue
        expectations[brand] = {period: parse_sheet_float(row.get(column_letter, "")) for column_letter, period in month_columns.items()}

    return expectations


def load_cruces_expectations(input_path: Path, monthly_periods: list[str]) -> dict[str, dict[str, float]]:
    rows = parse_worksheet_rows(input_path, "CRUCES")
    if len(rows) < 3:
        return {}

    year = monthly_periods[0][:4]
    month_columns: dict[str, str] = {}
    for column_letter, label in rows[1].items():
        normalized_label = normalize_sheet_label(label)
        if normalized_label in SPANISH_MONTHS and excel_column_number(column_letter) < excel_column_number("G"):
            month_columns[column_letter] = month_label_to_iso(year, label)

    expectations: dict[str, dict[str, float]] = {}
    for row in rows[2:]:
        brand = normalize_sheet_label(row.get("A", ""))
        if not brand:
            continue
        if brand == "TOTAL GENERAL":
            break
        if is_excluded_product_brand(brand):
            continue
        expectations[brand] = {
            period: parse_sheet_float(row.get(column_letter, ""))
            for column_letter, period in month_columns.items()
        }

    return expectations


def load_brand_media_expectations(input_path: Path, brand: str, monthly_periods: list[str]) -> dict[str, dict[str, float]]:
    sheet_name = BRAND_TO_QA_SHEET.get(brand, brand)
    if sheet_name not in workbook_sheet_names(input_path):
        return {}

    rows = parse_worksheet_rows(input_path, sheet_name)
    expectations: dict[str, dict[str, float]] = {}
    year = monthly_periods[0][:4]
    month_columns: dict[str, str] = {}
    for column_letter, label in rows[1].items():
        normalized_label = normalize_sheet_label(label)
        if normalized_label in SPANISH_MONTHS and excel_column_number(column_letter) < excel_column_number("F"):
            month_columns[column_letter] = month_label_to_iso(year, label)

    for row in rows[5:10]:
        media_label = normalize_sheet_label(row.get("B", ""))
        if media_label == brand or media_label == "TOTAL GENERAL" or media_label not in MEDIA_TYPE_SLUGS:
            continue
        media_slug = MEDIA_TYPE_SLUGS[media_label]
        expectations[media_slug] = {period: parse_sheet_float(row.get(column_letter, "")) for column_letter, period in month_columns.items()}

    return expectations


def run_qa(
    input_path: Path,
    monthly_periods: list[str],
    brands: list[str],
    monthly_aggregations: dict[str, dict[str, dict[str, float]]],
    weekly_periods: list[str] | None = None,
    weekly_aggregations: dict[str, dict[str, dict[str, float]]] | None = None,
) -> dict[str, Any]:
    summary_sheet_name = resolve_available_sheet_name(input_path, SUMMARY_SHEET_CANDIDATES)
    mismatches: list[dict[str, Any]] = []
    checks: list[dict[str, Any]] = []

    resumen_expectations = load_resumen_expectations(input_path, monthly_periods)
    available_expectation_months = sorted(
        {
            month
            for values in resumen_expectations.values()
            for month, expected in values.items()
            if expected or month in monthly_periods
        }
    )
    if summary_sheet_name == "CRUCES" and not set(monthly_periods).issubset(set(available_expectation_months)):
        return {
            "passed": True,
            "skipped": True,
            "skip_reason": "CRUCES does not cover all months present in DATOS; skipping blocking QA for this cut.",
            "tolerance": QA_TOLERANCE,
            "checks_run": 0,
            "mismatch_count": 0,
            "mismatches": [],
        }

    for brand in brands:
        for month in monthly_periods:
            expected = resumen_expectations.get(brand, {}).get(month, 0.0)
            actual = monthly_aggregations["total"].get(brand, {}).get(month, 0.0)
            difference = round(actual - expected, 6)
            check = {
                "scope": "total",
                "brand_name": brand,
                "month": month,
                "expected": expected,
                "actual": actual,
                "difference": difference,
            }
            checks.append(check)
            if abs(difference) > QA_TOLERANCE:
                mismatches.append(check)

    for brand in brands:
        media_expectations = load_brand_media_expectations(input_path, brand, monthly_periods)
        for media_slug, values in media_expectations.items():
            for month in monthly_periods:
                expected = values.get(month, 0.0)
                actual = monthly_aggregations.get(media_slug, {}).get(brand, {}).get(month, 0.0)
                difference = round(actual - expected, 6)
                check = {
                    "scope": media_slug,
                    "brand_name": brand,
                    "month": month,
                    "expected": expected,
                    "actual": actual,
                    "difference": difference,
                }
                checks.append(check)
                if abs(difference) > QA_TOLERANCE:
                    mismatches.append(check)

    accepted_latest_week_mismatches: list[dict[str, Any]] = []
    if summary_sheet_name == "CRUCES" and mismatches and weekly_periods and weekly_aggregations:
        latest_month = monthly_periods[-1] if monthly_periods else ""
        latest_week = weekly_periods[-1]
        latest_week_totals = weekly_aggregations.get("total", {})
        can_accept_latest_week_gap = True

        for mismatch in mismatches:
            brand = mismatch["brand_name"]
            latest_week_value = latest_week_totals.get(brand, {}).get(latest_week, 0.0)
            if (
                mismatch["scope"] != "total"
                or mismatch["month"] != latest_month
                or abs(mismatch["difference"] - latest_week_value) > QA_TOLERANCE
            ):
                can_accept_latest_week_gap = False
                break

        if can_accept_latest_week_gap:
            accepted_latest_week_mismatches = mismatches
            return {
                "passed": True,
                "skipped": True,
                "skip_reason": (
                    "CRUCES excludes the latest week present in DATOS; accepted DATOS totals "
                    f"for the current cut through {latest_week}."
                ),
                "tolerance": QA_TOLERANCE,
                "checks_run": len(checks),
                "mismatch_count": len(mismatches),
                "accepted_mismatch_count": len(accepted_latest_week_mismatches),
                "mismatches": mismatches,
            }

    return {
        "passed": not mismatches,
        "tolerance": QA_TOLERANCE,
        "checks_run": len(checks),
        "mismatch_count": len(mismatches),
        "mismatches": mismatches,
    }


def build_visualization_payload(
    input_path: Path,
    source_sheet_name: str | None,
    records: list[dict[str, str]],
    periods: list[str],
    brands: list[str],
    aggregations: dict[str, dict[str, dict[str, float]]],
    qa_report: dict[str, Any],
    payment_summary: dict[str, Any] | None = None,
    infolobby_lobby_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    media_order = [slug for slug in ("tv_abierta", "tv_cable", "radio", "via_publica", "digital", "prensa") if slug in aggregations]
    brand_totals: list[dict[str, Any]] = []

    for brand in brands:
        media_breakdown = {}
        media_series = {}
        total = 0.0
        for media_slug in media_order:
            amount = sum(aggregations.get(media_slug, {}).get(brand, {}).get(period, 0.0) for period in periods)
            media_breakdown[media_slug] = round(amount, 2)
            media_series[media_slug] = {
                period: round(aggregations.get(media_slug, {}).get(brand, {}).get(period, 0.0), 2)
                for period in periods
            }
            total += amount
        period_values = {period: round(aggregations["total"].get(brand, {}).get(period, 0.0), 2) for period in periods}
        brand_totals.append(
            {
                "brand_name": brand,
                "total": round(total, 2),
                "series": period_values,
                "media_breakdown": media_breakdown,
                "media_series": media_series,
            }
        )

    brand_totals.sort(key=lambda item: item["total"], reverse=True)

    sample_records = [
        {
            "brand_name": record["brand_name"],
            "observed_at": record["observed_at"],
            "media_type": record["media_type"],
            "outlet_name": record["outlet_name"],
            "program_name": record["program_name"],
            "ad_type": record["ad_type"],
            "creative_version": record["creative_version"],
            "evidence_url": record["evidence_url"],
            "net_investment": round(float(record["net_investment"]), 2),
        }
        for record in records
        if record["brand_name"] in brands and record["evidence_url"]
    ][:200]

    readme_text = (ROOT_DIR / "README.md").read_text(encoding="utf-8")
    prevention_context = {
        "title": "Prevención, evidencia y estándares de protección",
        "intro": (
            "La publicidad intensiva de apuestas configura un entorno de exposición permanente que incrementa el riesgo de daño para personas vulnerables."
        ),
        "signals": [
            "La televisión, la radio, internet, la vía pública y los sistemas de pago conforman un ecosistema de exposición reiterada.",
            "Los bonos de entrada y promociones reducen la percepción de riesgo y refuerzan el consumo.",
            "Las plataformas fuera del marco legal chileno carecen de mecanismos verificables de protección al usuario.",
            "La medición visibiliza a medios, agencias e intermediarios que habilitan este circuito comercial.",
        ],
        "recovery": (
            "El contraste relevante es entre entornos sin control efectivo y mercados con estándares internacionales de juego responsable, supervisión, auditoría y resguardo activo del usuario."
        ),
        "source_label": "Fuente base de prevencion: AJUTER",
        "source_url": AJUTER_LUDOPATIA_URL,
    }

    source_label = format_publicity_source_label(input_path, periods)

    return {
        "title": "Inversion semanal por casino de apuesta ilegal",
        "currency": "CLP",
        "repo_url": REPO_URL,
        "prevention_context": prevention_context,
        "source_file": format_cut_label(input_path),
        "source_name": PUBLICITY_DATA_SOURCE,
        "source_period": format_period_label(periods),
        "source_label": source_label,
        "source_workbook": input_path.name,
        "source_sheet": source_sheet_name,
        "period_granularity": "week",
        "periods": periods,
        "brands": brands,
        "media_order": media_order,
        "brand_totals": brand_totals,
        "sample_records": sample_records,
        "readme_html": markdown_to_html(readme_text),
        "qa_passed": qa_report["passed"],
        "qa_checks_run": qa_report["checks_run"],
        "payment_infrastructure": payment_summary,
        "infolobby_lobby": infolobby_lobby_summary,
    }


def with_site_version_context(
    payload: dict[str, Any],
    current_version: dict[str, str],
    version_manifest_path: str,
) -> dict[str, Any]:
    contextualized = dict(payload)
    contextualized["current_version"] = current_version
    contextualized["version_manifest_path"] = version_manifest_path
    return contextualized


def svg_currency(value: float) -> str:
    return "$" + f"{round(value):,}".replace(",", ".")


def svg_compact(value: float) -> str:
    thresholds = (
        (1_000_000_000, "MM"),
        (1_000_000, "M"),
        (1_000, "mil"),
    )
    absolute = abs(value)
    for threshold, suffix in thresholds:
        if absolute >= threshold:
            scaled = value / threshold
            text = f"{scaled:.1f}".rstrip("0").rstrip(".")
            return f"${text} {suffix}"
    return svg_currency(value)


def svg_escape(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def render_inline_markdown(text: str) -> str:
    escaped = html.escape(text)
    escaped = re.sub(r"`([^`]+)`", r"<code>\1</code>", escaped)
    escaped = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", escaped)
    escaped = re.sub(r"\*([^*]+)\*", r"<em>\1</em>", escaped)
    escaped = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2" target="_blank" rel="noreferrer">\1</a>', escaped)
    return escaped


def markdown_to_html(markdown_text: str) -> str:
    lines = markdown_text.splitlines()
    parts: list[str] = []
    paragraph: list[str] = []
    list_items: list[str] = []
    in_code = False
    code_lines: list[str] = []

    def flush_paragraph() -> None:
        nonlocal paragraph
        if paragraph:
            parts.append(f"<p>{render_inline_markdown(' '.join(paragraph).strip())}</p>")
            paragraph = []

    def flush_list() -> None:
        nonlocal list_items
        if list_items:
            items = "".join(f"<li>{render_inline_markdown(item)}</li>" for item in list_items)
            parts.append(f"<ul>{items}</ul>")
            list_items = []

    def flush_code() -> None:
        nonlocal code_lines
        if code_lines:
            parts.append(f"<pre><code>{html.escape(chr(10).join(code_lines))}</code></pre>")
            code_lines = []

    for raw_line in lines:
        line = raw_line.rstrip()
        stripped = line.strip()

        if stripped.startswith("```"):
            flush_paragraph()
            flush_list()
            if in_code:
                flush_code()
                in_code = False
            else:
                in_code = True
            continue

        if in_code:
            code_lines.append(line)
            continue

        if not stripped:
            flush_paragraph()
            flush_list()
            continue

        if stripped == "---":
            flush_paragraph()
            flush_list()
            parts.append("<hr>")
            continue

        if stripped.startswith("#"):
            flush_paragraph()
            flush_list()
            level = min(len(stripped) - len(stripped.lstrip("#")), 6)
            content = stripped[level:].strip()
            parts.append(f"<h{level + 1}>{render_inline_markdown(content)}</h{level + 1}>")
            continue

        if re.match(r"^\d+\.\s+", stripped):
            flush_paragraph()
            flush_list()
            parts.append(f"<p>{render_inline_markdown(stripped)}</p>")
            continue

        if stripped.startswith("- "):
            flush_paragraph()
            list_items.append(stripped[2:].strip())
            continue

        if stripped.startswith("![") and "](" in stripped:
            flush_paragraph()
            flush_list()
            match = re.match(r"!\[([^\]]*)\]\(([^)]+)\)", stripped)
            if match:
                alt_text, src = match.groups()
                parts.append(
                    f'<figure><img src="{html.escape(src)}" alt="{html.escape(alt_text)}"><figcaption>{html.escape(alt_text)}</figcaption></figure>'
                )
                continue

        paragraph.append(stripped)

    flush_paragraph()
    flush_list()
    if in_code:
        flush_code()

    return "".join(parts)


def build_stacked_bars_svg(payload: dict[str, Any]) -> str:
    media_colors = {
        "tv_abierta": "#b91c1c",
        "tv_cable": "#f97316",
        "radio": "#0f766e",
        "via_publica": "#7c3aed",
        "digital": "#2563eb",
        "prensa": "#475569",
    }
    labels = {
        "tv_abierta": "TV abierta",
        "tv_cable": "TV cable",
        "radio": "Radio",
        "via_publica": "Via publica",
        "digital": "Digital",
        "prensa": "Prensa",
    }
    width = 1280
    height = 920
    margin_left = 200
    margin_right = 170
    margin_top = 110
    margin_bottom = 150
    plot_width = width - margin_left - margin_right
    row_height = 48
    max_total = max((item["total"] for item in payload["brand_totals"]), default=1.0)
    ticks = 5
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">',
        '<title id="title">Distribucion estimada de inversion por marca y medio</title>',
        '<desc id="desc">Barras horizontales stackeadas con la distribucion estimada de inversion por marca y desglose por medio.</desc>',
        '<rect width="100%" height="100%" fill="#f6f2e9"/>',
        '<text x="48" y="54" font-family="Helvetica Neue, Arial, sans-serif" font-size="34" font-weight="700" fill="#1f2937">Distribucion estimada de inversion por marca y medio</text>',
        '<text x="48" y="84" font-family="Helvetica Neue, Arial, sans-serif" font-size="18" fill="#5f6b7a">Composicion por tipo de medio. Montos estimados en CLP segun observacion y tarifas estandar.</text>',
        '<rect x="48" y="840" width="1184" height="44" rx="14" fill="#fff4dd" stroke="#f59e0b" stroke-width="1.5"/>',
        '<text x="70" y="868" font-family="Helvetica Neue, Arial, sans-serif" font-size="16" font-weight="700" fill="#92400e">Prevencion:</text>',
        '<text x="178" y="868" font-family="Helvetica Neue, Arial, sans-serif" font-size="16" fill="#7c2d12">AJUTER describe la ludopatia como una adiccion conductual cronica; no es solo perdida de dinero.</text>',
        f'<text x="48" y="905" font-family="Helvetica Neue, Arial, sans-serif" font-size="14" fill="#5f6b7a">Fuente: {svg_escape(payload["source_label"])}</text>',
    ]

    legend_x = 48
    legend_y = 110
    for slug in payload["media_order"]:
        parts.append(f'<rect x="{legend_x}" y="{legend_y - 12}" width="14" height="14" rx="7" fill="{media_colors[slug]}"/>')
        parts.append(
            f'<text x="{legend_x + 24}" y="{legend_y}" font-family="Helvetica Neue, Arial, sans-serif" font-size="16" fill="#334155">{labels[slug]}</text>'
        )
        legend_x += 130

    for tick_index in range(ticks + 1):
        x = margin_left + plot_width * tick_index / ticks
        value = max_total * tick_index / ticks
        parts.append(f'<line x1="{x}" y1="{margin_top}" x2="{x}" y2="{height - margin_bottom}" stroke="#e8e3d8" stroke-width="1"/>')
        parts.append(
            f'<text x="{x}" y="{height - 34}" text-anchor="middle" font-family="Helvetica Neue, Arial, sans-serif" font-size="14" fill="#64748b">{svg_escape(svg_compact(value))}</text>'
        )

    for index, item in enumerate(payload["brand_totals"]):
        y = margin_top + index * row_height
        cursor = margin_left
        parts.append(
            f'<text x="{margin_left - 14}" y="{y + 22}" text-anchor="end" font-family="Helvetica Neue, Arial, sans-serif" font-size="16" fill="#1f2937">{svg_escape(item["brand_name"])}</text>'
        )
        for slug in payload["media_order"]:
            value = item["media_breakdown"].get(slug, 0.0)
            segment_width = 0 if max_total == 0 else plot_width * value / max_total
            if segment_width > 0:
                parts.append(
                    f'<rect x="{cursor}" y="{y + 6}" width="{segment_width}" height="24" rx="4" fill="{media_colors[slug]}"/>'
                )
                cursor += segment_width
        parts.append(
            f'<text x="{margin_left + plot_width + 14}" y="{y + 23}" font-family="Helvetica Neue, Arial, sans-serif" font-size="15" fill="#334155">{svg_escape(svg_currency(item["total"]))}</text>'
        )

    parts.append("</svg>")
    return "".join(parts)


def build_lines_svg(payload: dict[str, Any]) -> str:
    width = 1280
    height = 960
    margin_left = 210
    margin_right = 70
    margin_top = 110
    margin_bottom = 170
    plot_width = width - margin_left - margin_right
    plot_height = height - margin_top - margin_bottom
    max_value = max(
        (item["series"].get(period, 0.0) for item in payload["brand_totals"] for period in payload["periods"]),
        default=1.0,
    )
    rows = max(len(payload["brand_totals"]), 1)
    cols = max(len(payload["periods"]), 1)
    cell_width = plot_width / cols
    cell_height = plot_height / rows

    def heat_color(value: float) -> str:
        ratio = 0.0 if max_value == 0 else min(max(value / max_value, 0.0), 1.0) ** 0.55
        start = (244, 241, 232)
        end = (139, 30, 63)
        channels = [round(start[i] + (end[i] - start[i]) * ratio) for i in range(3)]
        return "#" + "".join(f"{channel:02x}" for channel in channels)

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">',
        '<title id="title">Mapa de calor semanal de la inversion estimada por marca</title>',
        '<desc id="desc">Mapa de calor con la evolucion semanal estimada de la inversion por marca.</desc>',
        '<rect width="100%" height="100%" fill="#f6f2e9"/>',
        '<text x="48" y="52" font-family="Helvetica Neue, Arial, sans-serif" font-size="34" font-weight="700" fill="#1f2937">Mapa de calor semanal de la inversion estimada por marca</text>',
        '<text x="48" y="82" font-family="Helvetica Neue, Arial, sans-serif" font-size="18" fill="#5f6b7a">Cada celda representa un corte semanal de 2026. Cuanto mas intenso el color, mayor la inversion estimada observada.</text>',
        '<rect x="48" y="882" width="1184" height="44" rx="14" fill="#fff4dd" stroke="#f59e0b" stroke-width="1.5"/>',
        '<text x="70" y="910" font-family="Helvetica Neue, Arial, sans-serif" font-size="16" font-weight="700" fill="#92400e">Prevencion:</text>',
        '<text x="178" y="910" font-family="Helvetica Neue, Arial, sans-serif" font-size="16" fill="#7c2d12">AJUTER advierte que el juego puede pasar a ocupar prioridad sobre otras actividades y persistir pese a danos.</text>',
        f'<text x="48" y="945" font-family="Helvetica Neue, Arial, sans-serif" font-size="14" fill="#5f6b7a">Fuente: {svg_escape(payload["source_label"])}</text>',
    ]

    for period_index, period in enumerate(payload["periods"]):
        x = margin_left + cell_width * period_index + cell_width / 2
        parts.append(
            f'<text x="{x}" y="{margin_top - 18}" text-anchor="middle" font-family="Helvetica Neue, Arial, sans-serif" font-size="14" fill="#64748b">{svg_escape(period)}</text>'
        )
        parts.append(f'<line x1="{margin_left + cell_width * period_index}" y1="{margin_top}" x2="{margin_left + cell_width * period_index}" y2="{margin_top + plot_height}" stroke="#efeadd" stroke-width="1"/>')

    for brand_index, item in enumerate(payload["brand_totals"]):
        y = margin_top + cell_height * brand_index
        parts.append(
            f'<text x="{margin_left - 14}" y="{y + cell_height / 2 + 5}" text-anchor="end" font-family="Helvetica Neue, Arial, sans-serif" font-size="16" fill="#1f2937">{svg_escape(item["brand_name"])}</text>'
        )
        for period_index, period in enumerate(payload["periods"]):
            value = item["series"].get(period, 0.0)
            x = margin_left + cell_width * period_index
            parts.append(
                f'<rect x="{x + 2}" y="{y + 2}" width="{cell_width - 4}" height="{cell_height - 4}" rx="6" fill="{heat_color(value)}"/>'
            )
            if value > 0:
                text_color = "#ffffff" if max_value and value / max_value > 0.45 else "#1f2937"
                parts.append(
                    f'<text x="{x + cell_width / 2}" y="{y + cell_height / 2 + 4}" text-anchor="middle" font-family="Helvetica Neue, Arial, sans-serif" font-size="12" fill="{text_color}">{svg_escape(svg_compact(value))}</text>'
                )

    legend_x = 48
    legend_y = height - 42
    for step in range(6):
        value = max_value * step / 5
        x = legend_x + step * 90
        parts.append(f'<rect x="{x}" y="{legend_y - 16}" width="44" height="16" rx="6" fill="{heat_color(value)}"/>')
        parts.append(
            f'<text x="{x + 22}" y="{legend_y + 18}" text-anchor="middle" font-family="Helvetica Neue, Arial, sans-serif" font-size="13" fill="#64748b">{svg_escape(svg_compact(value))}</text>'
        )

    parts.append("</svg>")
    return "".join(parts)


def build_visualization_html(payload: dict[str, Any]) -> str:
    payload_json = json.dumps(payload, ensure_ascii=True)
    return """<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Visualizacion: Inversion mensual por casino de apuesta ilegal</title>
  <style>
    :root {
      --bg: #080b10;
      --panel: rgba(18, 24, 34, 0.86);
      --panel-strong: #111827;
      --ink: #eef2f7;
      --muted: #94a3b8;
      --soft: #cbd5e1;
      --accent: #d7b56d;
      --accent-2: #72d6c9;
      --campaign: #ff784f;
      --campaign-2: #56c7ff;
      --danger: #e06a6a;
      --border: rgba(148, 163, 184, 0.22);
      --grid: rgba(148, 163, 184, 0.14);
      --shadow: 0 28px 90px rgba(0, 0, 0, 0.34);
      --tv_abierta: #d36a5f;
      --tv_cable: #d99f62;
      --radio: #6ac4b0;
      --via_publica: #a889dd;
      --digital: #6aa5e8;
      --prensa: #9aa7b7;
    }
    * { box-sizing: border-box; }
    html { scroll-behavior: smooth; }
    body {
      margin: 0;
      font-family: "Avenir Next", "Helvetica Neue", Arial, sans-serif;
      color: var(--ink);
      background:
        radial-gradient(circle at 18% 0%, rgba(255, 120, 79, 0.18), transparent 28%),
        radial-gradient(circle at 82% 10%, rgba(86, 199, 255, 0.12), transparent 26%),
        linear-gradient(180deg, #07090d 0%, #0d121b 48%, #07090d 100%);
      min-height: 100vh;
    }
    body::before {
      content: "";
      position: fixed;
      inset: 0;
      pointer-events: none;
      background-image: linear-gradient(rgba(255,255,255,0.025) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.02) 1px, transparent 1px);
      background-size: 44px 44px;
      mask-image: linear-gradient(180deg, rgba(0,0,0,0.65), transparent 78%);
    }
    a { color: var(--accent); }
    .page {
      max-width: 1320px;
      margin: 0 auto;
      padding: 28px 20px 56px;
      position: relative;
    }
    .topbar {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      margin-bottom: 42px;
      color: var(--muted);
      font-size: 0.88rem;
      letter-spacing: 0.04em;
      text-transform: uppercase;
    }
    .brand-mark {
      display: inline-flex;
      align-items: center;
      gap: 10px;
      color: var(--ink);
      font-weight: 700;
    }
    .brand-mark::before {
      content: "";
      width: 9px;
      height: 9px;
      border-radius: 999px;
      background: var(--accent);
      box-shadow: 0 0 28px rgba(255, 120, 79, 0.58);
    }
    .nav-links { display: flex; gap: 18px; flex-wrap: wrap; }
    .nav-links a { color: var(--muted); text-decoration: none; }
    .nav-links a:hover { color: var(--ink); }
    .topbar-tools {
      display: flex;
      align-items: center;
      gap: 16px;
      flex-wrap: wrap;
      justify-content: flex-end;
    }
    .version-switcher {
      display: grid;
      gap: 5px;
      min-width: 220px;
    }
    .version-switcher label {
      font-size: 0.68rem;
      color: var(--muted);
      letter-spacing: 0.14em;
      text-transform: uppercase;
    }
    .version-switcher select {
      width: 100%;
      padding: 9px 12px;
      border: 1px solid var(--border);
      border-radius: 14px;
      background: rgba(255, 255, 255, 0.055);
      color: var(--ink);
      font: inherit;
    }
    .version-switcher option {
      background: #101722;
      color: var(--ink);
    }
    .kicker {
      color: var(--campaign);
      font-size: 0.78rem;
      letter-spacing: 0.2em;
      text-transform: uppercase;
      margin-bottom: 18px;
      font-weight: 800;
    }
    .hero {
      display: grid;
      grid-template-columns: minmax(0, 1.7fr) minmax(280px, 0.8fr);
      gap: 22px;
      margin-bottom: 24px;
      align-items: stretch;
    }
    .panel {
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 26px;
      box-shadow: var(--shadow);
      padding: 26px;
      backdrop-filter: blur(18px);
    }
    .hero-main {
      min-height: 470px;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
      background:
        linear-gradient(135deg, rgba(255, 120, 79, 0.16), transparent 36%),
        radial-gradient(circle at 90% 12%, rgba(86, 199, 255, 0.16), transparent 24%),
        linear-gradient(160deg, rgba(255,255,255,0.05), transparent 42%),
        var(--panel);
      position: relative;
      overflow: hidden;
    }
    .hero-main::after {
      content: "NO";
      position: absolute;
      right: clamp(18px, 4vw, 58px);
      top: clamp(18px, 5vw, 70px);
      font-family: Georgia, "Times New Roman", serif;
      font-size: clamp(5rem, 16vw, 15rem);
      line-height: 0.78;
      color: rgba(255, 120, 79, 0.08);
      letter-spacing: -0.12em;
      pointer-events: none;
    }
    .context-panel {
      background:
        linear-gradient(180deg, rgba(255,255,255,0.055), rgba(255,255,255,0.018)),
        rgba(12, 17, 25, 0.9);
    }
    h1, h2, h3 { margin: 0 0 10px; }
    h1 {
      font-family: Georgia, "Times New Roman", serif;
      font-size: clamp(2.7rem, 7.6vw, 7.6rem);
      line-height: 0.84;
      letter-spacing: -0.075em;
      max-width: 980px;
    }
    .title-small {
      display: block;
      font-family: "Avenir Next", "Helvetica Neue", Arial, sans-serif;
      font-size: clamp(1rem, 1.8vw, 1.45rem);
      line-height: 1;
      letter-spacing: 0.18em;
      text-transform: uppercase;
      color: var(--campaign-2);
      margin-bottom: 12px;
    }
    .title-punch {
      color: var(--campaign);
      text-shadow: 0 0 42px rgba(255, 120, 79, 0.22);
    }
    .title-rest { display: block; }
    h2 { font-size: clamp(1.35rem, 2.2vw, 2.05rem); letter-spacing: -0.035em; }
    h3 { font-size: 0.8rem; color: var(--muted); text-transform: uppercase; letter-spacing: 0.16em; }
    p { margin: 0 0 10px; line-height: 1.65; }
    .lede { font-size: clamp(1.05rem, 1.7vw, 1.28rem); max-width: 68ch; color: var(--soft); }
    .note { color: var(--muted); font-size: 0.94rem; }
    .meta { margin: 0; }
    .meta dt { font-size: 0.72rem; color: var(--muted); text-transform: uppercase; letter-spacing: 0.14em; }
    .meta dd { margin: 5px 0 18px; font-weight: 700; color: var(--ink); overflow-wrap: anywhere; }
    .stats {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 14px;
      margin: 30px 0 0;
    }
    .stat {
      background: rgba(255, 255, 255, 0.045);
      border: 1px solid var(--border);
      border-radius: 20px;
      padding: 18px;
    }
    .stat .label {
      display: block;
      font-size: 0.78rem;
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0.14em;
      margin-bottom: 6px;
    }
    .stat strong { font-size: clamp(1.22rem, 2vw, 1.85rem); letter-spacing: -0.04em; }
    .stat small {
      display: block;
      color: var(--muted);
      line-height: 1.45;
      margin-top: 7px;
      font-size: 0.82rem;
    }
    .support-leaders {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 12px;
      margin-top: 14px;
    }
    .support-card {
      position: relative;
      overflow: hidden;
      border: 1px solid var(--border);
      border-radius: 20px;
      padding: 16px;
      background: rgba(255, 255, 255, 0.04);
    }
    .support-card::before {
      content: "";
      position: absolute;
      inset: 0 auto 0 0;
      width: 5px;
      background: var(--support-color);
    }
    .support-card span {
      display: block;
      color: var(--muted);
      font-size: 0.72rem;
      text-transform: uppercase;
      letter-spacing: 0.13em;
      margin-bottom: 6px;
    }
    .support-card strong {
      display: block;
      color: var(--ink);
      font-size: 1.05rem;
      line-height: 1.25;
    }
    .support-card small {
      display: block;
      color: var(--muted);
      margin-top: 7px;
      line-height: 1.45;
      font-size: 0.82rem;
    }
    .prevention-grid {
      display: grid;
      grid-template-columns: minmax(0, 1.15fr) minmax(280px, 0.85fr);
      gap: 22px;
      margin: 24px 0;
    }
    .warning-panel {
      background:
        linear-gradient(135deg, rgba(245, 158, 11, 0.16), rgba(239, 68, 68, 0.10)),
        rgba(18, 24, 34, 0.9);
    }
    .warning-list {
      margin: 18px 0 0;
      padding-left: 18px;
      color: var(--soft);
    }
    .warning-list li { margin-bottom: 10px; line-height: 1.6; }
    .warning-chip {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 6px 12px;
      border-radius: 999px;
      border: 1px solid rgba(245, 158, 11, 0.34);
      background: rgba(245, 158, 11, 0.12);
      color: #fde68a;
      font-size: 0.8rem;
      font-weight: 700;
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }
    .briefing {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 12px;
      margin-top: 22px;
    }
    .briefing-card {
      border: 1px solid var(--border);
      background:
        linear-gradient(150deg, rgba(255, 120, 79, 0.10), rgba(86, 199, 255, 0.06)),
        rgba(0, 0, 0, 0.18);
      border-radius: 24px;
      padding: 18px;
    }
    .briefing-card span {
      display: block;
      color: var(--campaign-2);
      font-size: 0.72rem;
      text-transform: uppercase;
      letter-spacing: 0.14em;
      font-weight: 800;
      margin-bottom: 7px;
    }
    .briefing-card strong { display: block; color: var(--ink); line-height: 1.35; }
    .payment-grid {
      display: grid;
      grid-template-columns: minmax(280px, 0.85fr) minmax(0, 1.4fr);
      gap: 22px;
      margin: 24px 0;
    }
    .payment-summary {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 12px;
      margin-top: 18px;
    }
    .payment-card {
      border: 1px solid var(--border);
      border-radius: 22px;
      padding: 16px;
      background:
        linear-gradient(145deg, rgba(86, 199, 255, 0.08), rgba(255, 120, 79, 0.06)),
        rgba(255, 255, 255, 0.035);
    }
    .payment-card span {
      display: block;
      color: var(--muted);
      font-size: 0.74rem;
      letter-spacing: 0.13em;
      text-transform: uppercase;
      margin-bottom: 7px;
    }
    .payment-card strong { font-size: 1.55rem; letter-spacing: -0.04em; }
    .payment-profiles {
      display: grid;
      gap: 12px;
    }
    .payment-profile {
      display: grid;
      grid-template-columns: 150px minmax(0, 1fr);
      gap: 14px;
      border: 1px solid var(--grid);
      border-radius: 20px;
      padding: 14px;
      background: rgba(8, 11, 16, 0.36);
    }
    .payment-profile h4 {
      margin: 0 0 8px;
      font-size: 1rem;
      letter-spacing: -0.02em;
    }
    .payment-profile small { color: var(--muted); line-height: 1.45; }
    .chip-row {
      display: flex;
      flex-wrap: wrap;
      gap: 7px;
    }
    .chip {
      display: inline-flex;
      align-items: center;
      border: 1px solid rgba(148, 163, 184, 0.26);
      border-radius: 999px;
      padding: 4px 9px;
      color: var(--soft);
      background: rgba(255, 255, 255, 0.045);
      font-size: 0.78rem;
      white-space: nowrap;
    }
    .chip.processor {
      color: var(--ink);
      border-color: rgba(86, 199, 255, 0.28);
      background: rgba(86, 199, 255, 0.08);
    }
    .chip.domain {
      color: #dbeafe;
      border-color: rgba(96, 165, 250, 0.28);
      background: rgba(37, 99, 235, 0.12);
    }
    .chip.primary-domain {
      color: #d1fae5;
      border-color: rgba(16, 185, 129, 0.34);
      background: rgba(16, 185, 129, 0.12);
      font-weight: 700;
    }
    .payment-bars {
      display: grid;
      gap: 9px;
      margin-top: 18px;
    }
    .payment-bar {
      display: grid;
      grid-template-columns: 104px minmax(0, 1fr) 32px;
      gap: 10px;
      align-items: center;
      color: var(--soft);
      font-size: 0.86rem;
    }
    .payment-bar-track {
      height: 10px;
      border-radius: 999px;
      background: rgba(255, 255, 255, 0.07);
      overflow: hidden;
    }
    .payment-bar-fill {
      height: 100%;
      border-radius: inherit;
      background: linear-gradient(90deg, var(--campaign), var(--campaign-2));
    }
    .payment-evolution {
      display: grid;
      gap: 12px;
      margin-top: 18px;
    }
    .payment-evolution-header {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: end;
      flex-wrap: wrap;
    }
    .payment-evolution-header strong {
      display: block;
      font-size: 1.15rem;
      letter-spacing: -0.03em;
    }
    .payment-evolution-header span {
      color: var(--muted);
      font-size: 0.82rem;
      line-height: 1.4;
    }
    .payment-change {
      border: 1px solid var(--grid);
      border-radius: 18px;
      padding: 14px;
      background: rgba(8, 11, 16, 0.34);
    }
    .payment-change h4 {
      margin: 0 0 10px;
      font-size: 0.98rem;
      letter-spacing: -0.02em;
    }
    .payment-change-section {
      display: grid;
      gap: 7px;
      margin-top: 9px;
    }
    .payment-change-section span {
      color: var(--muted);
      font-size: 0.72rem;
      letter-spacing: 0.12em;
      text-transform: uppercase;
    }
    .chip.added {
      color: #d1fae5;
      border-color: rgba(16, 185, 129, 0.34);
      background: rgba(16, 185, 129, 0.12);
    }
    .chip.removed {
      color: #fee2e2;
      border-color: rgba(239, 68, 68, 0.34);
      background: rgba(239, 68, 68, 0.12);
    }
    .chip.url-count {
      color: #dbeafe;
      border-color: rgba(96, 165, 250, 0.28);
      background: rgba(37, 99, 235, 0.12);
    }
    .legend {
      display: flex;
      flex-wrap: wrap;
      gap: 10px 16px;
      margin-top: 20px;
    }
    .legend span {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      font-size: 0.92rem;
      color: var(--soft);
    }
    .legend i {
      width: 12px;
      height: 12px;
      border-radius: 999px;
      display: inline-block;
    }
    .line-legend {
      display: flex;
      flex-wrap: wrap;
      gap: 10px 16px;
      margin-top: 18px;
    }
    .line-legend span {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      font-size: 0.9rem;
      color: var(--soft);
    }
    .line-legend i {
      width: 12px;
      height: 12px;
      border-radius: 999px;
      display: inline-block;
    }
    .charts {
      display: grid;
      grid-template-columns: 1fr;
      gap: 22px;
      margin-bottom: 24px;
    }
    .heatmap-stack {
      display: grid;
      gap: 18px;
      margin-top: 18px;
    }
    .heatmap-card {
      border: 1px solid var(--grid);
      border-radius: 22px;
      padding: 18px;
      background: rgba(8, 11, 16, 0.34);
    }
    .heatmap-card h3 {
      color: var(--ink);
      font-size: 1.05rem;
      letter-spacing: -0.02em;
      text-transform: none;
      margin-bottom: 4px;
    }
    .section-label {
      color: var(--campaign);
      letter-spacing: 0.16em;
      text-transform: uppercase;
      font-size: 0.76rem;
      font-weight: 800;
      margin-bottom: 10px;
    }
    .chart-wrap {
      overflow-x: auto;
      padding-bottom: 8px;
    }
    svg {
      width: 100%;
      min-width: 480px;
      height: auto;
      display: block;
      overflow: visible;
    }
    .axis-label { fill: var(--muted); font-size: 12px; }
    .axis-line, .grid-line { stroke: var(--grid); stroke-width: 1; }
    .line-label { font-size: 11px; font-weight: bold; }
    .table-wrap {
      overflow: auto;
      border: 1px solid var(--border);
      border-radius: 20px;
      max-height: 680px;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      font-size: 0.95rem;
      background: rgba(8, 11, 16, 0.42);
    }
    th, td {
      padding: 13px 14px;
      border-bottom: 1px solid var(--grid);
      text-align: left;
      vertical-align: top;
      color: var(--soft);
    }
    th {
      font-size: 0.78rem;
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0.1em;
      position: sticky;
      top: 0;
      background: #101722;
      z-index: 2;
      cursor: default;
    }
    tbody tr:hover { background: rgba(255,255,255,0.045); }
    td strong { color: var(--ink); }
    .media-badge {
      display: inline-flex;
      align-items: center;
      border: 1px solid var(--border);
      border-radius: 999px;
      padding: 3px 9px;
      font-size: 0.78rem;
      color: var(--ink);
      background: rgba(255,255,255,0.055);
      margin-bottom: 6px;
    }
    #piecesTable th:first-child,
    #piecesTable td:first-child {
      min-width: 170px;
      white-space: nowrap;
    }
    .viewer {
      display: grid;
      grid-template-columns: 320px 1fr;
      gap: 22px;
      margin-top: 24px;
    }
    .controls {
      display: grid;
      gap: 12px;
      align-content: start;
    }
    .control {
      display: grid;
      gap: 6px;
    }
    .control label {
      font-size: 0.8rem;
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }
    .control select, .control input {
      width: 100%;
      padding: 10px 12px;
      border: 1px solid var(--border);
      border-radius: 14px;
      background: rgba(255, 255, 255, 0.055);
      color: var(--ink);
      font: inherit;
    }
    .control select option { background: #101722; color: var(--ink); }
    .methodology {
      display: grid;
      grid-template-columns: minmax(0, 1fr) minmax(260px, 0.7fr);
      gap: 22px;
      margin-top: 24px;
    }
    .method-list {
      display: grid;
      gap: 14px;
      margin: 18px 0 0;
      padding: 0;
      list-style: none;
    }
    .method-list li {
      border-top: 1px solid var(--grid);
      padding-top: 14px;
      color: var(--soft);
    }
    .pill {
      display: inline-block;
      padding: 4px 10px;
      border-radius: 999px;
      background: rgba(114, 214, 201, 0.12);
      color: var(--accent-2);
      font-size: 0.85rem;
      font-weight: bold;
    }
    .footer {
      margin-top: 32px;
      color: var(--muted);
      display: flex;
      justify-content: space-between;
      gap: 16px;
      flex-wrap: wrap;
      border-top: 1px solid var(--grid);
      padding-top: 22px;
      font-size: 0.92rem;
    }
    @media (max-width: 960px) {
      .hero, .charts, .viewer, .stats, .methodology, .payment-grid { grid-template-columns: 1fr; }
      .briefing, .support-leaders { grid-template-columns: 1fr; }
      .payment-summary { grid-template-columns: 1fr 1fr; }
      .payment-profile { grid-template-columns: 1fr; }
      .page { padding: 18px 14px 40px; }
      .topbar { align-items: flex-start; flex-direction: column; margin-bottom: 28px; }
      .hero-main { min-height: auto; }
      h1 { font-size: clamp(2.7rem, 16vw, 4.8rem); }
      .panel { padding: 20px; border-radius: 22px; }
      svg { min-width: 860px; }
      .chart-wrap { margin: 0 -4px; }
    }
  </style>
</head>
<body>
  <div class="page">
    <header class="topbar">
      <div class="brand-mark">EXPOSICIÓN PUBLICITARIA DE APUESTAS EN CHILE – DATOS ABIERTOS</div>
      <div class="topbar-tools">
        <nav class="nav-links" aria-label="Navegacion principal">
          <a href="#serie">Serie semanal</a>
          <a href="#prevencion">Prevencion</a>
          <a href="#tabla">Tabla</a>
          <a href="#pagos">Pagos</a>
          <a href="#lobby">Lobby</a>
          <a href="#piezas">Piezas</a>
          <a href="#metodologia">Metodo</a>
        </nav>
        <div class="version-switcher">
          <label for="versionSelect">Version publicada</label>
          <select id="versionSelect" aria-label="Seleccionar version publicada">
            <option value="">Cargando versiones...</option>
          </select>
        </div>
      </div>
    </header>
    <section class="hero">
      <div class="panel hero-main">
        <div>
          <div class="kicker">EXPOSICIÓN PUBLICITARIA DE APUESTAS EN CHILE – DATOS ABIERTOS</div>
          <h1><span class="title-small">Prevención, evidencia y estándares de protección</span><span class="title-punch">Exposición sistemática</span><span class="title-rest">y riesgo acumulado</span></h1>
        </div>
        <p class="lede">Para las personas más vulnerables, la publicidad intensiva de apuestas no es solo marketing: configura un entorno de exposición permanente que incrementa el riesgo de daño. Este observatorio dimensiona la inversión del mercado ilegal de casinos en línea en Chile e identifica a los actores que sostienen esa presión cotidiana.</p>
        <p class="note">Al operar fuera del marco legal chileno, estas plataformas carecen de mecanismos verificables de protección al usuario: no ofrecen sistemas integrados de autoexclusión, ni estándares auditables de trazabilidad, ni condiciones de transparencia equivalentes a aquellas exigidas en mercados con certificación internacional vigente.</p>
        <p class="note">La televisión, la radio, internet, la vía pública y los sistemas de pago no actúan de forma aislada. Desde una perspectiva de prevención, conforman un ecosistema que normaliza el juego y expone de manera reiterada a personas vulnerables, reforzando el consumo mediante incentivos agresivos —bonos de entrada y promociones— que reducen la percepción de riesgo.</p>
        <p class="note">Por ello, esta medición no solo cuantifica inversión: también visibiliza la red de medios, agencias e intermediarios que habilitan este circuito comercial, evidenciando la brecha entre entornos sin control efectivo y aquellos que operan bajo estándares internacionales de juego responsable, con supervisión, auditoría y resguardo activo del usuario.</p>
        <div class="briefing" id="briefing"></div>
        <div class="stats" id="stats"></div>
        <div class="support-leaders" id="supportLeaders"></div>
        <div class="legend" id="legend"></div>
      </div>
      <aside class="panel context-panel">
        <h3>Contexto</h3>
        <dl class="meta">
          <dt>Moneda</dt>
          <dd id="metaCurrency"></dd>
          <dt>Fuente</dt>
          <dd id="metaSource"></dd>
          <dt>Hoja</dt>
          <dd id="metaSheet"></dd>
          <dt>Actualizado</dt>
          <dd id="metaUpdatedAt"></dd>
          <dt>QA</dt>
          <dd><span class="pill" id="metaQa"></span></dd>
        </dl>
      </aside>
    </section>

    <section class="prevention-grid" id="prevencion">
      <article class="panel warning-panel">
        <div class="section-label">Prevencion</div>
        <h2 id="preventionTitle"></h2>
        <p class="lede" id="preventionIntro"></p>
        <ul class="warning-list" id="preventionSignals"></ul>
      </article>
      <aside class="panel">
        <div class="warning-chip">Salud publica</div>
        <p class="note" id="preventionRecovery"></p>
        <p class="note">La referencia editorial de esta seccion proviene de AJUTER, organizacion chilena que trabaja rehabilitacion y visibilizacion de la ludopatia.</p>
        <p class="note">Como marco regulatorio, la SCJ advierte que estas plataformas operan al margen de la legalidad, sin regulacion ni fiscalizacion local y sin garantias suficientes de transparencia ni proteccion para usuarios.</p>
        <p class="note"><a id="preventionSourceLink" target="_blank" rel="noreferrer">Ver informacion base de AJUTER</a></p>
      </aside>
    </section>

    <section class="charts" id="serie">
      <article class="panel">
        <div class="section-label">Mapas de calor</div>
        <h2>Inversion publicitaria semanal estimada por marca y medio</h2>
        <p class="note">Cada mapa separa un universo de inversion: total general y desglose por medio. Cada celda representa una semana de 2026; cuanto mas intenso el color, mayor la inversion estimada observada para esa marca, medio y semana.</p>
        <div class="heatmap-stack" id="heatmapStack"></div>
      </article>
      <article class="panel">
        <div class="section-label">Composicion</div>
        <h2>Distribucion estimada por marca y medio</h2>
        <p class="note">Cada barra resume la estimacion total por marca y la descompone por tipo de medio segun la publicidad observada y valorizada con tarifa estandar.</p>
        <div class="chart-wrap"><svg id="stackedBars" viewBox="0 0 960 560" aria-label="Grafico de barras stackeadas"></svg></div>
      </article>
    </section>

    <section class="panel" id="tabla">
      <div class="section-label">Tabla de lectura rapida</div>
      <h2>Tabla resumen</h2>
      <p class="note">Totales acumulados estimados por marca en CLP a partir de publicidad observada y valorizada con tarifa estandar.</p>
      <div class="table-wrap">
        <table id="summaryTable"></table>
      </div>
    </section>

    <section class="payment-grid" id="pagos">
      <aside class="panel">
        <div class="section-label">Sistema de pago</div>
        <h2>La banca operativa del circuito</h2>
        <p class="lede">Los procesadores y medios de pago permiten que el flujo economico exista: reciben depositos de usuarios, conectan medios locales con operadores y hacen posible el pago de premios.</p>
        <p class="note">Esta vista resume los medios y PSP observados por marca. La presencia de un procesador indica vinculacion observable con el flujo transaccional, no una conclusion juridica definitiva sobre ese actor.</p>
        <div class="payment-summary" id="paymentSummary"></div>
        <div class="payment-bars" id="paymentBars"></div>
        <div class="payment-evolution" id="paymentEvolution"></div>
      </aside>
      <article class="panel">
        <div class="section-label">Mapa de infraestructura</div>
        <h2>Medios de pago y procesadores por casino</h2>
        <p class="note">Cada fila muestra, para el ultimo corte disponible, los PSP identificables, los rotulos originales observados y las URLs o dominios activos detectados en la planilla fuente.</p>
        <div class="payment-profiles" id="paymentProfiles"></div>
      </article>
    </section>

    <section class="panel" id="lobby">
      <div class="section-label">El lobby de las casas de apuesta</div>
      <h2>Reuniones sobre casinos y apuestas en linea</h2>
      <p class="note" id="lobbySource"></p>
      <div class="table-wrap">
        <table id="lobbyTable"></table>
      </div>
    </section>

    <section class="viewer" id="piezas">
      <aside class="panel controls">
        <div>
          <div class="section-label">Exploracion</div>
          <h2>Explorador de piezas</h2>
          <p class="note">Filtra por marca, medio y texto para revisar piezas, programas, evidencia y magnitud estimada. En el sitio publicado se carga automaticamente el JSON maestro.</p>
        </div>
        <div class="control">
          <label for="jsonLoader">Cargar JSON maestro</label>
          <input id="jsonLoader" type="file" accept=".json,application/json">
        </div>
        <div class="control">
          <label for="brandFilter">Marca</label>
          <select id="brandFilter"><option value="">Todas</option></select>
        </div>
        <div class="control">
          <label for="mediaFilter">Tipo de medio</label>
          <select id="mediaFilter"><option value="">Todos</option></select>
        </div>
        <div class="control">
          <label for="searchFilter">Buscar texto</label>
          <input id="searchFilter" type="search" placeholder="medio, programa, version">
        </div>
        <div class="control">
          <label for="sortFilter">Ordenar por</label>
          <select id="sortFilter">
            <option value="investment">Mayor inversion estimada</option>
            <option value="observations">Mas apariciones</option>
            <option value="recent">Mas reciente</option>
            <option value="brand">Marca</option>
          </select>
        </div>
        <p class="note" id="piecesStatus">Intentando cargar el JSON maestro. Si no esta disponible, se mostrara una muestra embebida.</p>
      </aside>
      <section class="panel">
        <div class="table-wrap">
          <table id="piecesTable"></table>
        </div>
      </section>
    </section>

    <section class="methodology" id="metodologia">
      <article class="panel">
        <div class="section-label">Metodo</div>
        <h2>Como leer estos datos</h2>
        <p class="lede">La medicion cruza apariciones publicitarias observadas en espacios publicos con tarifas estandar de mercado. El resultado es una estimacion comparable de inversion, no una declaracion tributaria ni un registro contable de las empresas.</p>
        <ul class="method-list">
          <li><strong>Observacion:</strong> cada fila registra fecha, marca, medio, programa, tipo de aviso y evidencia disponible.</li>
          <li><strong>Valorizacion:</strong> la aparicion se multiplica por una tarifa estandar para estimar inversion neta.</li>
          <li><strong>Publicacion:</strong> se excluyen marcas reguladas en Chile y se publican agregados semanales junto con una muestra explorable de piezas.</li>
          <li><strong>Lectura preventiva:</strong> la intensidad publicitaria se interpreta tambien como presion comercial sobre personas expuestas, no solo como gasto de marketing.</li>
          <li><strong>Mercado negro:</strong> al tratarse de plataformas fuera del marco legal chileno, la exposicion se produce sin un sistema unificado de autoexclusion, sin fiscalizacion local equivalente y con incentivos promocionales de alto riesgo como bonos de entrada.</li>
        </ul>
      </article>
      <aside class="panel">
        <h3>Notas editoriales</h3>
        <p class="note">Los montos estan expresados en pesos chilenos. Las semanas cierran en domingo. La lectura correcta es comparativa: magnitud, tendencia y composicion por medio.</p>
        <p class="note">Este observatorio documenta publicidad observable; no reemplaza asesorias legales, regulatorias ni financieras.</p>
        <p class="note">AJUTER describe la ludopatia como un trastorno del juego con perdida de control, persistencia pese a consecuencias negativas e impacto en la salud mental, la vida familiar y la situacion economica.</p>
        <p class="note">La SCJ sostiene que, mientras no exista una ley especifica que las habilite y regule, las plataformas de apuestas en linea operan fuera del marco legal chileno, sin regulacion, fiscalizacion ni transparencia suficientes para proteger a quienes participan.</p>
        <p class="note">Fuente de informacion publicitaria: Integrametrics, con periodo consignado segun la version publicada. La medicion observa apariciones publicitarias y estima inversion con tarifas estandar.</p>
        <a id="repoLink" target="_blank" rel="noreferrer">Repositorio y datos abiertos</a>
      </aside>
    </section>

    <footer class="footer">
      <span>Observatorio abierto de publicidad de apuestas online en Chile</span>
      <span>Actualizado segun la version publicada del sitio</span>
    </footer>
  </div>

  <script id="payload" type="application/json">__PAYLOAD__</script>
  <script>
    const payload = JSON.parse(document.getElementById("payload").textContent);
    const numberFormatter = new Intl.NumberFormat("es-CL", { maximumFractionDigits: 0 });
    const compactFormatter = new Intl.NumberFormat("es-CL", { notation: "compact", maximumFractionDigits: 1 });
    const periodFormatter = new Intl.DateTimeFormat("es-CL", { day: "2-digit", month: "short", year: "numeric" });
    let pieceRecords = payload.sample_records.slice();
    let usingEmbeddedSamples = true;

    function formatMoney(value) {
      return "$" + numberFormatter.format(Math.round(value));
    }

    function formatCompact(value) {
      return "$" + compactFormatter.format(value);
    }

    function prettyPeriod(value) {
      const [year, month, day] = value.split("-").map(Number);
      return periodFormatter.format(new Date(year, month - 1, day));
    }

    function compactPeriod(value) {
      const [year, month, day] = value.split("-").map(Number);
      return new Intl.DateTimeFormat("es-CL", { day: "2-digit", month: "short" })
        .format(new Date(year, month - 1, day))
        .replace(".", "");
    }

    function mediaLabel(slug) {
      const labels = {
        total: "Total",
        tv_abierta: "TV abierta",
        tv_cable: "TV cable",
        radio: "Radio",
        via_publica: "Via publica",
        digital: "Digital",
        prensa: "Prensa"
      };
      return labels[slug] || slug;
    }

    function colorFor(slug) {
      return getComputedStyle(document.documentElement).getPropertyValue("--" + slug).trim() || "#64748b";
    }

    function truncateText(value, maxLength) {
      return value.length <= maxLength ? value : value.slice(0, maxLength - 1) + "…";
    }

    function escapeHtml(value) {
      return String(value ?? '').replace(/[&<>"']/g, (character) => ({
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#39;'
      }[character]));
    }

    function brandColor(index) {
      const palette = ["#8b1e3f", "#0b6e4f", "#2563eb", "#f97316", "#7c3aed", "#b91c1c", "#0f766e", "#475569", "#d97706", "#4f46e5"];
      return palette[index % palette.length];
    }

    function heatmapTitle(slug) {
      if (slug === "total") return "Inversion publicitaria semanal estimada por marca: total general";
      return "Inversion publicitaria semanal estimada por marca en " + mediaLabel(slug);
    }

    function heatmapPalette(slug) {
      const palettes = {
        total: { start: [244, 241, 232], end: [139, 30, 63] },
        tv_abierta: { start: [255, 238, 232], end: [194, 65, 52] },
        tv_cable: { start: [255, 242, 222], end: [190, 103, 35] },
        radio: { start: [226, 249, 244], end: [19, 122, 105] },
        via_publica: { start: [242, 232, 255], end: [110, 73, 181] },
        digital: { start: [229, 241, 255], end: [37, 99, 180] },
        prensa: { start: [235, 239, 244], end: [71, 85, 105] }
      };
      return palettes[slug] || palettes.total;
    }

    function rgbText(channels) {
      return "rgb(" + channels.join(",") + ")";
    }

    function setMeta() {
      const prevention = payload.prevention_context || {};
      document.getElementById("metaCurrency").textContent = payload.currency;
      document.getElementById("metaSource").textContent = payload.source_label || payload.source_file;
      document.getElementById("metaSheet").textContent = payload.source_sheet;
      const pageUpdatedAt = document.lastModified
        ? new Intl.DateTimeFormat("es-CL", { dateStyle: "short", timeStyle: "short" }).format(new Date(document.lastModified))
        : "No disponible";
      document.getElementById("metaUpdatedAt").textContent = pageUpdatedAt;
      document.getElementById("metaQa").textContent = payload.qa_passed ? "QA OK (" + payload.qa_checks_run + " chequeos)" : "QA con observaciones";
      document.getElementById("repoLink").href = payload.repo_url;
      document.getElementById("repoLink").textContent = payload.repo_url;

      const totalInvestment = payload.brand_totals.reduce((sum, item) => sum + item.total, 0);
      const topBrand = payload.brand_totals[0];
      const latestPeriod = payload.periods[payload.periods.length - 1];
      const latestPressure = payload.brand_totals
        .map((item) => ({ brand_name: item.brand_name, value: item.series[latestPeriod] || 0 }))
        .sort((left, right) => right.value - left.value)[0];
      const leadingMedia = payload.media_order
        .map((slug) => ({
          slug,
          value: payload.brand_totals.reduce((sum, item) => sum + (item.media_breakdown[slug] || 0), 0)
        }))
        .sort((left, right) => right.value - left.value)[0];
      document.getElementById("briefing").innerHTML = [
        { label: "Ultimo corte", value: latestPressure.brand_name + " ejerce la mayor presion semanal con " + formatCompact(latestPressure.value) },
        { label: "Mayor acumulado", value: topBrand.brand_name + " concentra " + formatCompact(topBrand.total) + " del periodo" },
        { label: "Medio dominante", value: mediaLabel(leadingMedia.slug) + " suma " + formatCompact(leadingMedia.value) }
      ].map((item) => '<div class="briefing-card"><span>' + item.label + '</span><strong>' + item.value + '</strong></div>').join("");
      const stats = [
        { label: "Marcas", value: payload.brands.length, note: "incluidas en el producto publico" },
        { label: "Cortes", value: payload.periods.length, note: "semanas con cierre dominical" },
        { label: "Inversion total", value: formatCompact(totalInvestment), note: "estimacion acumulada en CLP" },
        { label: "Mayor presion", value: topBrand.brand_name, note: formatCompact(topBrand.total) + " acumulados" }
      ];
      document.getElementById("stats").innerHTML = stats.map((item) =>
        '<div class="stat"><span class="label">' + item.label + '</span><strong>' + item.value + '</strong><small>' + item.note + '</small></div>'
      ).join("");

      const supportLeaders = payload.media_order
        .map((slug) => {
          const total = payload.brand_totals.reduce((sum, item) => sum + (item.media_breakdown[slug] || 0), 0);
          const highestPressure = payload.brand_totals
            .map((item) => ({ brand_name: item.brand_name, value: item.media_breakdown[slug] || 0 }))
            .sort((left, right) => right.value - left.value)[0];
          return { slug, total, highestPressure };
        })
        .filter((item) => item.total > 0 && item.highestPressure && item.highestPressure.value > 0);
      document.getElementById("supportLeaders").innerHTML = supportLeaders.map((item) => {
        const color = rgbText(heatmapPalette(item.slug).end);
        return '<div class="support-card" style="--support-color:' + color + '">' +
          '<span>Mayor presion en ' + mediaLabel(item.slug) + '</span>' +
          '<strong>' + item.highestPressure.brand_name + ' · ' + formatCompact(item.highestPressure.value) + '</strong>' +
          '<small>Total del soporte: ' + formatCompact(item.total) + '</small>' +
        '</div>';
      }).join("");

      document.getElementById("legend").innerHTML = payload.media_order.map((slug) =>
        '<span><i style="background:' + colorFor(slug) + '"></i>' + mediaLabel(slug) + '</span>'
      ).join("");
      document.getElementById("preventionTitle").textContent = prevention.title || "Prevencion y ludopatia";
      document.getElementById("preventionIntro").textContent = prevention.intro || "";
      document.getElementById("preventionSignals").innerHTML = (prevention.signals || [])
        .map((item) => '<li>' + item + '</li>')
        .join("");
      document.getElementById("preventionRecovery").textContent = prevention.recovery || "";
      document.getElementById("preventionSourceLink").href = prevention.source_url || "";
      document.getElementById("preventionSourceLink").textContent = prevention.source_label || "Fuente";
    }

    async function loadVersionManifest() {
      const select = document.getElementById("versionSelect");
      const currentVersion = payload.current_version || {};
      const fallbackLabel = currentVersion.label || payload.source_file || "Version actual";
      select.innerHTML = '<option value="">' + fallbackLabel + '</option>';
      select.disabled = true;

      if (!payload.version_manifest_path) {
        return;
      }

      try {
        const manifestUrl = new URL(payload.version_manifest_path, window.location.href);
        const response = await fetch(manifestUrl);
        if (!response.ok) throw new Error("version manifest unavailable");
        const parsed = await response.json();
        const versions = Array.isArray(parsed.versions) ? parsed.versions : [];
        if (!versions.length) {
          return;
        }

        select.innerHTML = versions.map((item) => {
          const versionUrl = new URL(item.path || ".", manifestUrl);
          const isCurrent = item.id === currentVersion.id;
          return '<option value="' + versionUrl.href + '"' + (isCurrent ? ' selected' : '') + '>' + item.label + '</option>';
        }).join("");
        select.disabled = false;
        select.addEventListener("change", () => {
          if (select.value && select.value !== window.location.href) {
            window.location.href = select.value;
          }
        });
      } catch (error) {
        select.innerHTML = '<option value="">' + fallbackLabel + '</option>';
      }
    }

    function renderStackedBars() {
      const svg = document.getElementById("stackedBars");
      const width = 980;
      const height = Math.max(520, 90 + payload.brand_totals.length * 42);
      svg.setAttribute("viewBox", "0 0 " + width + " " + height);
      const margin = { top: 24, right: 118, bottom: 36, left: 170 };
      const plotWidth = width - margin.left - margin.right;
      const rowHeight = 34;
      const maxValue = Math.max(...payload.brand_totals.map((item) => item.total), 1);
      const ticks = 5;
      let content = "";

      for (let i = 0; i <= ticks; i += 1) {
        const value = maxValue * i / ticks;
        const x = margin.left + (plotWidth * i / ticks);
        content += '<line class="grid-line" x1="' + x + '" y1="' + margin.top + '" x2="' + x + '" y2="' + (height - margin.bottom) + '"></line>';
        content += '<text class="axis-label" x="' + x + '" y="' + (height - 12) + '" text-anchor="middle">' + formatCompact(value) + '</text>';
      }

      payload.brand_totals.forEach((item, index) => {
        const y = margin.top + index * rowHeight + 4;
        let cursor = margin.left;
        content += '<text class="axis-label" x="' + (margin.left - 12) + '" y="' + (y + 16) + '" text-anchor="end">' + item.brand_name + '</text>';
        payload.media_order.forEach((slug) => {
          const value = item.media_breakdown[slug] || 0;
          const segmentWidth = plotWidth * (value / maxValue);
          if (segmentWidth > 0) {
            content += '<rect x="' + cursor + '" y="' + y + '" width="' + segmentWidth + '" height="22" rx="4" fill="' + colorFor(slug) + '"></rect>';
            cursor += segmentWidth;
          }
        });
        content += '<text class="axis-label" x="' + (width - 12) + '" y="' + (y + 16) + '" text-anchor="end">' + formatMoney(item.total) + '</text>';
      });

      svg.innerHTML = content;
    }

    function renderHeatmapSvg(svg, slug, valuesForBrand) {
      const activeBrands = payload.brand_totals.filter((item) =>
        payload.periods.some((period) => (valuesForBrand(item, period) || 0) > 0)
      );
      const width = 980;
      const height = Math.max(280, 120 + activeBrands.length * 42);
      svg.setAttribute("viewBox", "0 0 " + width + " " + height);
      const margin = { top: 70, right: 24, bottom: 70, left: 180 };
      const plotWidth = width - margin.left - margin.right;
      const plotHeight = height - margin.top - margin.bottom;
      const maxValue = Math.max(...activeBrands.flatMap((item) => payload.periods.map((period) => valuesForBrand(item, period) || 0)), 1);
      const cellWidth = plotWidth / Math.max(payload.periods.length, 1);
      const cellHeight = plotHeight / Math.max(activeBrands.length, 1);
      function heatColor(value) {
        const ratio = Math.pow(Math.min(Math.max(value / maxValue, 0), 1), 0.55);
        const palette = heatmapPalette(slug);
        const start = palette.start;
        const end = palette.end;
        const channels = start.map((channel, index) => Math.round(channel + (end[index] - channel) * ratio));
        return "rgb(" + channels.join(",") + ")";
      }
      let content = "";

      payload.periods.forEach((period, index) => {
        const x = margin.left + cellWidth * index;
        content += '<line class="axis-line" x1="' + x + '" y1="' + margin.top + '" x2="' + x + '" y2="' + (height - margin.bottom) + '"></line>';
        content += '<text class="axis-label" x="' + (x + cellWidth / 2) + '" y="' + (margin.top - 12) + '" text-anchor="middle">' + compactPeriod(period) + '</text>';
      });

      activeBrands.forEach((item, rowIndex) => {
        const y = margin.top + cellHeight * rowIndex;
        content += '<text class="axis-label" x="' + (margin.left - 12) + '" y="' + (y + cellHeight / 2 + 4) + '" text-anchor="end">' + item.brand_name + '</text>';
        payload.periods.forEach((period, columnIndex) => {
          const value = valuesForBrand(item, period) || 0;
          const x = margin.left + cellWidth * columnIndex;
          const textColor = value / maxValue > 0.45 ? '#ffffff' : '#1f2937';
          content += '<rect x="' + (x + 2) + '" y="' + (y + 2) + '" width="' + (cellWidth - 4) + '" height="' + (cellHeight - 4) + '" rx="6" fill="' + heatColor(value) + '"></rect>';
          if (value > 0) {
            content += '<text x="' + (x + cellWidth / 2) + '" y="' + (y + cellHeight / 2 + 4) + '" text-anchor="middle" font-size="11" fill="' + textColor + '">' + formatCompact(value) + '</text>';
          }
        });
      });

      svg.innerHTML = content;
    }

    function renderLineChartSvg(svg, slug, valuesForBrand) {
      const activeBrands = payload.brand_totals.filter((item) =>
        payload.periods.some((period) => (valuesForBrand(item, period) || 0) > 0)
      );
      const width = 980;
      const height = 420;
      svg.setAttribute("viewBox", "0 0 " + width + " " + height);
      const margin = { top: 30, right: 28, bottom: 60, left: 70 };
      const plotWidth = width - margin.left - margin.right;
      const plotHeight = height - margin.top - margin.bottom;
      const maxValue = Math.max(...activeBrands.flatMap((item) => payload.periods.map((period) => valuesForBrand(item, period) || 0)), 1);
      const xStep = payload.periods.length > 1 ? plotWidth / (payload.periods.length - 1) : 0;
      const yForValue = (value) => margin.top + plotHeight - (Math.max(value, 0) / maxValue) * plotHeight;
      let content = "";

      for (let i = 0; i <= 4; i += 1) {
        const value = maxValue * i / 4;
        const y = margin.top + plotHeight - (plotHeight * i / 4);
        content += '<line class="grid-line" x1="' + margin.left + '" y1="' + y + '" x2="' + (width - margin.right) + '" y2="' + y + '"></line>';
        content += '<text class="axis-label" x="' + (margin.left - 10) + '" y="' + (y + 4) + '" text-anchor="end">' + formatCompact(value) + '</text>';
      }

      payload.periods.forEach((period, index) => {
        const x = margin.left + xStep * index;
        content += '<line class="axis-line" x1="' + x + '" y1="' + margin.top + '" x2="' + x + '" y2="' + (height - margin.bottom) + '"></line>';
        content += '<text class="axis-label" x="' + x + '" y="' + (height - 18) + '" text-anchor="middle">' + compactPeriod(period) + '</text>';
      });

      activeBrands.forEach((item, index) => {
        const series = payload.periods.map((period, periodIndex) => ({
          x: margin.left + xStep * periodIndex,
          y: yForValue(valuesForBrand(item, period) || 0),
          value: valuesForBrand(item, period) || 0
        }));
        const stroke = brandColor(index);
        const pathData = series.map((point, pointIndex) => (pointIndex === 0 ? 'M' : 'L') + point.x + ' ' + point.y).join(' ');
        content += '<path d="' + pathData + '" fill="none" stroke="' + stroke + '" stroke-width="3" stroke-linejoin="round" stroke-linecap="round"></path>';
        series.forEach((point) => {
          content += '<circle cx="' + point.x + '" cy="' + point.y + '" r="3.5" fill="' + stroke + '"></circle>';
        });
        const lastPoint = series[series.length - 1];
        content += '<text class="line-label" x="' + (lastPoint.x + 8) + '" y="' + (lastPoint.y + 4) + '" fill="' + stroke + '">' + item.brand_name + '</text>';
      });

      svg.innerHTML = content;
    }

    function renderHeatmaps() {
      const stack = document.getElementById("heatmapStack");
      const lineScopes = payload.media_order
        .filter((slug) => payload.brand_totals.some((item) => (item.media_breakdown[slug] || 0) > 0))
        .map((slug) => ({
          slug,
          valuesForBrand: (item, period) => ((item.media_series || {})[slug] || {})[period] || 0
        }));
      stack.innerHTML =
        '<article class="heatmap-card">' +
          '<h3>' + heatmapTitle('total') + '</h3>' +
          '<p class="note">Suma todos los medios publicitarios observados. Se muestran solo marcas con datos en este alcance.</p>' +
          '<div class="chart-wrap"><svg id="heatmap-total" aria-label="' + heatmapTitle('total') + '"></svg></div>' +
          '<div class="line-legend">' +
            '<span><i style="background:' + rgbText(heatmapPalette('total').start) + '"></i>Menor inversion semanal</span>' +
            '<span><i style="background:' + rgbText(heatmapPalette('total').end) + '"></i>Mayor inversion semanal</span>' +
          '</div>' +
        '</article>' +
        lineScopes.map((scope) =>
          '<article class="heatmap-card">' +
            '<h3>' + heatmapTitle(scope.slug) + '</h3>' +
            '<p class="note">Incluye solo inversion observada en ' + mediaLabel(scope.slug) + '. Cada linea muestra la trayectoria semanal de una marca dentro de este soporte.</p>' +
            '<div class="chart-wrap"><svg id="line-' + scope.slug + '" aria-label="' + heatmapTitle(scope.slug) + '"></svg></div>' +
          '</article>'
        ).join("");
      renderHeatmapSvg(document.getElementById("heatmap-total"), "total", (item, period) => item.series[period] || 0);
      lineScopes.forEach((scope) => {
        renderLineChartSvg(document.getElementById("line-" + scope.slug), scope.slug, scope.valuesForBrand);
      });
    }

    function renderSummaryTable() {
      const table = document.getElementById("summaryTable");
      const header = ['<thead><tr><th>Marca</th>', ...payload.periods.map((period) => '<th>' + prettyPeriod(period) + '</th>'), '<th>Total</th></tr></thead>'].join("");
      const rows = payload.brand_totals.map((item) => {
        return '<tr><td><strong>' + item.brand_name + '</strong></td>' +
          payload.periods.map((period) => '<td>' + formatMoney(item.series[period] || 0) + '</td>').join('') +
          '<td>' + formatMoney(item.total) + '</td></tr>';
      }).join("");
      const totalsByPeriod = payload.periods.map((period) =>
        payload.brand_totals.reduce((sum, item) => sum + (item.series[period] || 0), 0)
      );
      const grandTotal = payload.brand_totals.reduce((sum, item) => sum + item.total, 0);
      const totalRow = '<tr><td><strong>Total</strong></td>' +
        totalsByPeriod.map((value) => '<td><strong>' + formatMoney(value) + '</strong></td>').join('') +
        '<td><strong>' + formatMoney(grandTotal) + '</strong></td></tr>';
      table.innerHTML = header + '<tbody>' + rows + totalRow + '</tbody>';
    }

    function paymentMethodLabel(value) {
      const labels = {
        bank_transfer: "Transferencia",
        card: "Tarjetas",
        cash: "Efectivo",
        crypto: "Cripto",
        unknown: "Sin clasificar",
        wallet_or_psp: "Billetera/PSP"
      };
      return labels[value] || value;
    }

    function changeChips(items, type) {
      return (items || []).map((item) => '<span class="chip ' + type + '">' + item + '</span>').join('');
    }

    function structuralChangeCount(item) {
      const sections = [item.payment_gateways, item.payment_methods, item.casino_urls];
      return sections.reduce((sum, section) =>
        sum + ((section && section.added) ? section.added.length : 0) + ((section && section.removed) ? section.removed.length : 0),
        0
      );
    }

    function renderChangeSection(label, section) {
      if (!section || (!section.added.length && !section.removed.length)) return '';
      return '<div class="payment-change-section">' +
        '<span>' + label + '</span>' +
        '<div class="chip-row">' +
          changeChips(section.added, 'added') +
          changeChips(section.removed, 'removed') +
        '</div>' +
      '</div>';
    }

    function renderPaymentEvolution(payment) {
      const target = document.getElementById("paymentEvolution");
      const report = payment.payment_infrastructure_changes_report || payment.changes_report;
      if (!report || !report.changed_brands || !report.changed_brands.length) {
        target.innerHTML =
          '<div class="payment-change"><h4>Evolucion del levantamiento</h4>' +
          '<p class="note">No hay cambios estructurales detectados contra el levantamiento anterior.</p></div>';
        return;
      }

      const structuralChanges = report.changed_brands
        .map((item) => ({ ...item, structural_count: structuralChangeCount(item) }))
        .filter((item) => item.structural_count > 0)
        .sort((left, right) => right.structural_count - left.structural_count || left.brand_name.localeCompare(right.brand_name));
      const visibleChanges = structuralChanges.slice(0, 6);
      const urlOnlyChanges = report.changed_brands.length - structuralChanges.length;

      target.innerHTML =
        '<div class="payment-evolution-header">' +
          '<div><strong>Evolucion del levantamiento</strong><span>' + report.previous_input + ' -> ' + report.current_input + '</span></div>' +
          '<span>' + report.changed_brand_count + ' casinos con cambios; ' + urlOnlyChanges + ' solo cambian URLs transaccionales.</span>' +
        '</div>' +
        visibleChanges.map((item) => {
          const urlDelta = item.observed_payment_urls || { added: [], removed: [] };
          return '<div class="payment-change">' +
            '<h4>' + item.brand_name + '</h4>' +
            renderChangeSection('Pasarelas', item.payment_gateways) +
            renderChangeSection('Medios de pago', item.payment_methods) +
            renderChangeSection('URLs propias del casino', item.casino_urls) +
            '<div class="payment-change-section"><span>URLs de pago observadas</span><div class="chip-row">' +
              '<span class="chip url-count">+' + urlDelta.added.length + '</span>' +
              '<span class="chip url-count">-' + urlDelta.removed.length + '</span>' +
            '</div></div>' +
          '</div>';
        }).join('');
    }

    function renderPaymentInfrastructure() {
      const payment = payload.payment_infrastructure;
      const summary = document.getElementById("paymentSummary");
      const bars = document.getElementById("paymentBars");
      const profiles = document.getElementById("paymentProfiles");
      const evolution = document.getElementById("paymentEvolution");
      if (!payment || !payment.brand_profiles || !payment.brand_profiles.length) {
        summary.innerHTML = '<div class="payment-card"><span>Datos</span><strong>No disponibles</strong></div>';
        bars.innerHTML = '';
        evolution.innerHTML = '';
        profiles.innerHTML = '<p class="note">No hay un producto de medios de pago disponible para esta publicacion.</p>';
        return;
      }

      summary.innerHTML = [
        { label: "Casinos", value: payment.brand_count },
        { label: "PSP", value: payment.payment_processor_count },
        { label: "Dominios", value: payment.domain_count },
        { label: "URLs", value: payment.url_count },
        { label: "Medios", value: payment.payment_label_count },
        { label: "Observaciones", value: payment.latest_available_observation_count }
      ].map((item) => '<div class="payment-card"><span>' + item.label + '</span><strong>' + item.value + '</strong></div>').join("");

      const processorCounts = Object.entries(payment.processor_brand_counts || {})
        .sort((left, right) => right[1] - left[1])
        .slice(0, 8);
      const maxCount = Math.max(...processorCounts.map((item) => item[1]), 1);
      bars.innerHTML = processorCounts.map(([processor, count]) =>
        '<div class="payment-bar">' +
          '<span>' + processor + '</span>' +
          '<div class="payment-bar-track"><div class="payment-bar-fill" style="width:' + (count / maxCount * 100) + '%"></div></div>' +
          '<strong>' + count + '</strong>' +
        '</div>'
      ).join("");

      renderPaymentEvolution(payment);

      profiles.innerHTML = payment.brand_profiles.map((profile) => {
        const processors = profile.payment_processors.length
          ? profile.payment_processors.map((item) => '<span class="chip processor">' + item + '</span>').join('')
          : '<span class="chip">Sin PSP identificable</span>';
        const labels = profile.payment_labels.slice(0, 10).map((item) => '<span class="chip">' + item + '</span>').join('');
        const extraLabels = profile.payment_labels.length > 10 ? '<span class="chip">+' + (profile.payment_labels.length - 10) + ' mas</span>' : '';
        const primaryDomain = profile.primary_brand_domain
          ? '<span class="chip primary-domain">Casino en linea ilegal: ' + profile.primary_brand_domain + '</span>'
          : '<span class="chip">Casino en linea ilegal: sin dominio principal identificado</span>';
        const domains = profile.domains.length
          ? profile.domains.map((item) => '<span class="chip domain">' + item + '</span>').join('')
          : '';
        const methods = profile.payment_methods.map((item) => paymentMethodLabel(item)).join(', ');
        return '<div class="payment-profile">' +
          '<div><h4>' + profile.brand_name + '</h4><small>' + profile.processor_count + ' PSP identificables · ' + profile.payment_label_count + ' medios/rotulos · ' + profile.domain_count + ' dominios observados<br>' + methods + '</small></div>' +
          '<div><div class="chip-row">' + primaryDomain + '</div><div class="chip-row" style="margin-top:8px">' + processors + '</div><div class="chip-row" style="margin-top:8px">' + labels + extraLabels + '</div><div class="chip-row" style="margin-top:8px">' + domains + '</div></div>' +
        '</div>';
      }).join("");
    }

    function renderLobbyTable() {
      const lobby = payload.infolobby_lobby;
      const source = document.getElementById("lobbySource");
      const table = document.getElementById("lobbyTable");
      if (!lobby || !lobby.available || !lobby.top_lobbyists || !lobby.top_lobbyists.length) {
        source.textContent = "No hay datos de InfoLobby disponibles para esta publicacion.";
        table.innerHTML = "";
        return;
      }

      source.innerHTML = 'Fuente: <a href="' + escapeHtml(lobby.source_url) + '" target="_blank" rel="noreferrer">' +
        escapeHtml(lobby.source_name) + '</a>. Consulta a la pagina del Consejo para la Transparencia: ' +
        escapeHtml(lobby.source_page_consulted_at) + '. Filtro: ' + escapeHtml(lobby.topic_filter_label) + '.';

      const rows = lobby.top_lobbyists.map((item) => {
        const passives = (item.passive_meetings || [])
          .slice(0, 8)
          .map((passive) =>
            '<span class="chip">' + escapeHtml(passive.display) + ': ' + escapeHtml(passive.meetings_count) + '</span>'
          )
          .join('');
        return '<tr>' +
          '<td>' + escapeHtml(item.rank) + '</td>' +
          '<td><strong>' + escapeHtml(item.lobbyist_display) + '</strong></td>' +
          '<td>' + escapeHtml(item.meeting_count) + '</td>' +
          '<td><div class="chip-row">' + passives + '</div></td>' +
        '</tr>';
      }).join('');

      table.innerHTML =
        '<thead><tr><th>#</th><th>Lobista (a favor de quien)</th><th>Reuniones</th><th>Sujetos pasivos (cargo y ocasiones)</th></tr></thead>' +
        '<tbody>' + rows + '</tbody>';
    }

    function buildPiecesFilters(records) {
      const brandFilter = document.getElementById("brandFilter");
      const mediaFilter = document.getElementById("mediaFilter");
      const brands = Array.from(new Set(records.map((item) => item.brand_name).filter(Boolean))).sort();
      const media = Array.from(new Set(records.map((item) => item.media_type).filter(Boolean))).sort();
      brandFilter.innerHTML = '<option value="">Todas</option>' + brands.map((item) => '<option value="' + item + '">' + item + '</option>').join('');
      mediaFilter.innerHTML = '<option value="">Todos</option>' + media.map((item) => '<option value="' + item + '">' + item + '</option>').join('');
    }

    function aggregatePieceRecords(records) {
      const groups = new Map();
      records.forEach((item) => {
        const key = [
          item.brand_name || '',
          item.media_type || '',
          item.outlet_name || '',
          item.program_name || '',
          item.ad_type || '',
          item.creative_version || '',
          item.evidence_url || ''
        ].join('||');
        if (!groups.has(key)) {
          groups.set(key, {
            brand_name: item.brand_name || '',
            media_type: item.media_type || '',
            outlet_name: item.outlet_name || '',
            program_name: item.program_name || '',
            ad_type: item.ad_type || '',
            creative_version: item.creative_version || '',
            evidence_url: item.evidence_url || '',
            net_investment: 0,
            observations: 0,
            first_seen_at: item.observed_at || '',
            last_seen_at: item.observed_at || ''
          });
        }
        const group = groups.get(key);
        group.net_investment += Number(item.net_investment || 0);
        group.observations += 1;
        if (item.observed_at && (!group.first_seen_at || item.observed_at < group.first_seen_at)) group.first_seen_at = item.observed_at;
        if (item.observed_at && (!group.last_seen_at || item.observed_at > group.last_seen_at)) group.last_seen_at = item.observed_at;
      });
      return Array.from(groups.values());
    }

    function renderPiecesTable() {
      const brandValue = document.getElementById("brandFilter").value;
      const mediaValue = document.getElementById("mediaFilter").value;
      const searchValue = document.getElementById("searchFilter").value.trim().toLowerCase();
      const sortValue = document.getElementById("sortFilter").value;
      const rows = aggregatePieceRecords(pieceRecords)
        .filter((item) => !brandValue || item.brand_name === brandValue)
        .filter((item) => !mediaValue || item.media_type === mediaValue)
        .filter((item) => {
          if (!searchValue) return true;
          return [item.outlet_name, item.program_name, item.creative_version, item.ad_type].join(' ').toLowerCase().includes(searchValue);
        })
        .sort((left, right) => {
          if (sortValue === "observations") return (right.observations || 0) - (left.observations || 0);
          if (sortValue === "recent") return (right.last_seen_at || "").localeCompare(left.last_seen_at || "");
          if (sortValue === "brand") return (left.brand_name || "").localeCompare(right.brand_name || "");
          return (right.net_investment || 0) - (left.net_investment || 0);
        })
        .slice(0, 80);

      const table = document.getElementById("piecesTable");
      table.innerHTML =
        '<thead><tr><th>Periodo</th><th>Marca</th><th>Medio</th><th>Programa</th><th>Pieza</th><th>Apariciones</th><th>Inversion neta</th><th>Evidencia</th></tr></thead>' +
        '<tbody>' +
        rows.map((item) => '<tr>' +
          '<td>' + (item.first_seen_at === item.last_seen_at ? (item.first_seen_at || '') : [item.first_seen_at || '', item.last_seen_at || ''].filter(Boolean).join(' a ')) + '</td>' +
          '<td><strong>' + (item.brand_name || '') + '</strong></td>' +
          '<td>' + (item.media_type ? '<span class="media-badge">' + item.media_type + '</span><br>' : '') + (item.outlet_name || '') + '</td>' +
          '<td>' + (item.program_name || '') + '</td>' +
          '<td>' + [item.ad_type, item.creative_version].filter(Boolean).join(' / ') + '</td>' +
          '<td>' + (item.observations || 0) + '</td>' +
          '<td>' + formatMoney(item.net_investment || 0) + '</td>' +
          '<td>' + (item.evidence_url ? '<a href="' + item.evidence_url + '" target="_blank" rel="noreferrer">abrir</a>' : '') + '</td>' +
          '</tr>').join('') +
        '</tbody>';

      document.getElementById("piecesStatus").textContent = rows.length + " registros visibles" +
        (usingEmbeddedSamples ? " (muestra embebida)" : " (desde JSON cargado)");
    }

    function bindJsonLoader() {
      const loader = document.getElementById("jsonLoader");
      loader.addEventListener("change", async (event) => {
        const file = event.target.files && event.target.files[0];
        if (!file) return;
        const text = await file.text();
        const parsed = JSON.parse(text);
        pieceRecords = parsed.map((item) => ({
          brand_name: item.brand_name,
          observed_at: item.observed_at,
          media_type: item.media_type,
          outlet_name: item.outlet_name,
          program_name: item.program_name,
          ad_type: item.ad_type,
          creative_version: item.creative_version,
          evidence_url: item.evidence_url,
          net_investment: Number(item.net_investment || 0)
        }));
        usingEmbeddedSamples = false;
        buildPiecesFilters(pieceRecords);
        renderPiecesTable();
      });

      ["brandFilter", "mediaFilter", "searchFilter", "sortFilter"].forEach((id) => {
        document.getElementById(id).addEventListener("input", renderPiecesTable);
      });
    }

    async function tryAutoLoadMasterJson() {
      try {
        const response = await fetch("./data/master_investment_detail.json");
        if (!response.ok) throw new Error("master json unavailable");
        const parsed = await response.json();
        pieceRecords = parsed.map((item) => ({
          brand_name: item.brand_name,
          observed_at: item.observed_at,
          media_type: item.media_type,
          outlet_name: item.outlet_name,
          program_name: item.program_name,
          ad_type: item.ad_type,
          creative_version: item.creative_version,
          evidence_url: item.evidence_url,
          net_investment: Number(item.net_investment || 0)
        }));
        usingEmbeddedSamples = false;
        buildPiecesFilters(pieceRecords);
        renderPiecesTable();
      } catch (error) {
        renderPiecesTable();
      }
    }

    setMeta();
    loadVersionManifest();
    renderStackedBars();
    renderHeatmaps();
    renderSummaryTable();
    renderPaymentInfrastructure();
    renderLobbyTable();
    buildPiecesFilters(pieceRecords);
    bindJsonLoader();
    tryAutoLoadMasterJson();
  </script>
</body>
</html>
""".replace("__PAYLOAD__", payload_json)


def normalize_lookup_key(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", normalize_text(value))
    ascii_text = "".join(character for character in normalized if not unicodedata.combining(character))
    return ascii_text.upper()


def default_payment_processor_workbook() -> Path | None:
    candidate_paths = sorted(PAYMENT_PROCESSOR_INPUT_DIR.glob("*.xlsx")) + sorted((ROOT_DIR / "input" / "raw").glob("*.xlsx"))
    workbooks = [path for path in candidate_paths if is_payment_processor_workbook(path)]
    if not workbooks:
        return None
    return max(workbooks, key=payment_processor_workbook_rank)


def default_previous_payment_processor_workbook(current_input: Path) -> Path | None:
    candidate_paths = sorted(PAYMENT_PROCESSOR_INPUT_DIR.glob("*.xlsx")) + sorted((ROOT_DIR / "input" / "raw").glob("*.xlsx"))
    workbooks = [
        path
        for path in candidate_paths
        if path.resolve() != current_input.resolve() and is_payment_processor_workbook(path)
    ]
    if not workbooks:
        return None
    return max(workbooks, key=payment_processor_workbook_rank)


def is_payment_processor_workbook(workbook_path: Path) -> bool:
    try:
        sheet_names = workbook_sheet_names(workbook_path)
        if not sheet_names:
            return False
        rows = parse_worksheet_rows(workbook_path, sheet_names[0])
    except (KeyError, ValueError, ET.ParseError, FileNotFoundError):
        return False

    if not rows:
        return False

    header = rows[0]
    first_column = normalize_lookup_key(header.get("A", ""))
    second_column = normalize_lookup_key(header.get("B", ""))
    return "CASAS DE APUESTA" in first_column and "MEDIOS DE PAGO" in second_column


def payment_processor_workbook_rank(workbook_path: Path) -> tuple[int, int, str, str]:
    sheet_names = workbook_sheet_names(workbook_path)
    rows = parse_worksheet_rows(workbook_path, sheet_names[0]) if sheet_names else []
    header = rows[0] if rows else {}
    ordered_columns = sorted(header, key=excel_column_number)
    has_url_column = any(normalize_lookup_key(header.get(column, "")) == "URL" for column in ordered_columns if column not in {"A", "B"})
    directory_priority = 1 if workbook_path.resolve().parent == PAYMENT_PROCESSOR_INPUT_DIR.resolve() else 0
    return (1 if has_url_column else 0, directory_priority, workbook_coverage_end(workbook_path), workbook_path.name)


def split_payment_processors(payment_label: str) -> list[str]:
    normalized_label = normalize_lookup_key(payment_label)
    processors = [
        processor
        for processor in PAYMENT_PROCESSOR_NAMES
        if re.search(rf"(^|[^A-Z0-9]){re.escape(processor)}([^A-Z0-9]|$)", normalized_label)
    ]
    for alias, canonical_processor in PAYMENT_PROCESSOR_ALIASES.items():
        if re.search(rf"(^|[^A-Z0-9]){re.escape(alias)}([^A-Z0-9]|$)", normalized_label):
            processors.append(canonical_processor)
    return sorted(set(processors))


def classify_payment_method(payment_label: str, processors: list[str]) -> str:
    normalized_label = normalize_lookup_key(payment_label)
    if normalized_label in GENERIC_PAYMENT_METHODS:
        return GENERIC_PAYMENT_METHODS[normalized_label]
    if "CRIPTO" in normalized_label or "BITCOIN" in normalized_label or "BINANCE" in normalized_label:
        return "crypto"
    if "WEBPAY" in processors or "DEBITO" in normalized_label or "CREDITO" in normalized_label:
        return "card"
    if "TRANSFERENCIA" in normalized_label or "KHIPU" in processors or "FINTOC" in processors:
        return "bank_transfer"
    if "EFECTIVO" in normalized_label or "PAGO46" in processors:
        return "cash"
    if processors:
        return "wallet_or_psp"
    return "unknown"


def parse_payment_date_columns(header: dict[str, str]) -> list[dict[str, str]]:
    date_columns: list[dict[str, str]] = []

    for column in sorted(header, key=excel_column_number):
        if column in {"A", "B"}:
            continue

        value = normalize_text(header.get(column, ""))
        if not value:
            continue

        if normalize_lookup_key(value) == "URL":
            if date_columns:
                date_columns[-1]["url_column"] = column
            continue

        try:
            observed_at = excel_serial_to_date(value)
        except ValueError:
            continue

        if observed_at:
            date_columns.append(
                {
                    "status_column": column,
                    "observed_at": observed_at,
                    "url_column": "",
                }
            )

    return date_columns


def normalize_payment_url(value: str) -> str:
    raw = normalize_text(value)
    if not raw or not re.match(r"^https?://", raw, re.IGNORECASE):
        return ""
    return raw


def extract_domain_from_url(value: str) -> str:
    if not value:
        return ""

    parsed = urlparse(value)
    domain = parsed.netloc.lower().strip()
    if domain.startswith("www."):
        domain = domain[4:]
    return domain


def registrable_domain(value: str) -> str:
    domain = normalize_text(value).lower()
    if not domain:
        return ""
    labels = [label for label in domain.split(".") if label]
    if len(labels) <= 2:
        return ".".join(labels)
    if labels[-2] in {"com", "org", "net", "gov"} and len(labels[-1]) == 2:
        return ".".join(labels[-3:])
    return ".".join(labels[-2:])


def brand_domain_tokens(brand_name: str) -> tuple[str, ...]:
    aliases = BRAND_DOMAIN_ALIASES.get(brand_name)
    if aliases:
        return aliases
    normalized = normalize_lookup_key(brand_name)
    compact = "".join(character for character in normalized if character.isalnum())
    return (compact,) if compact else ()


def looks_like_brand_domain(brand_name: str, domain: str) -> bool:
    normalized_domain = normalize_lookup_key(registrable_domain(domain))
    if not normalized_domain:
        return False
    compact_domain = "".join(character for character in normalized_domain if character.isalnum())
    return any(token and token in compact_domain for token in brand_domain_tokens(brand_name))


def primary_brand_domain_for_profile(brand_name: str, brand_records: list[dict[str, str]]) -> str:
    if brand_name in MANUAL_PRIMARY_BRAND_DOMAINS:
        return MANUAL_PRIMARY_BRAND_DOMAINS[brand_name]
    observed_domains = sorted(
        {registrable_domain(record["domain"]) for record in brand_records if looks_like_brand_domain(brand_name, record["domain"])}
    )
    if observed_domains:
        return observed_domains[0]
    return ""


def parse_payment_processor_matrix(input_path: Path) -> tuple[str, list[dict[str, str]]]:
    if not input_path.exists():
        raise FileNotFoundError(f"Payment processor input file not found: {input_path}")
    if input_path.suffix.lower() != ".xlsx":
        raise ValueError(f"Unsupported payment processor input format: {input_path.suffix}. Expected .xlsx")

    sheet_name = workbook_sheet_names(input_path)[0]
    rows = parse_worksheet_rows(input_path, sheet_name)
    if not rows:
        return sheet_name, []

    header = rows[0]
    date_columns = parse_payment_date_columns(header)
    records: list[dict[str, str]] = []
    current_brand = ""

    for row in rows[1:]:
        brand = normalize_text(row.get("A", ""))
        if brand:
            current_brand = brand.upper()

        payment_label = normalize_text(row.get("B", ""))
        if not current_brand or not payment_label:
            continue

        processors = split_payment_processors(payment_label)
        payment_method = classify_payment_method(payment_label, processors)
        processor_values = processors or [""]

        for column_info in date_columns:
            status = normalize_lookup_key(row.get(column_info["status_column"], ""))
            if status not in {"SI", "NO"}:
                continue
            url = normalize_payment_url(row.get(column_info["url_column"], "")) if column_info["url_column"] else ""
            domain = extract_domain_from_url(url)
            for processor in processor_values:
                records.append(
                    {
                        "observed_at": column_info["observed_at"],
                        "brand_name": current_brand,
                        "url": url,
                        "domain": domain,
                        "payment_label": payment_label,
                        "payment_processor": processor,
                        "payment_method": payment_method,
                        "is_available": "true" if status == "SI" else "false",
                        "source_file": input_path.name,
                        "source_sheet": sheet_name,
                    }
                )

    deduplicated: dict[tuple[str, str, str, str, str, str], dict[str, str]] = {}
    for record in records:
        key = (
            record["observed_at"],
            record["brand_name"],
            record["payment_label"],
            record["payment_processor"],
            record["is_available"],
            record["url"],
        )
        deduplicated[key] = record

    return sheet_name, sorted(
        deduplicated.values(),
        key=lambda item: (item["brand_name"], item["payment_label"], item["observed_at"], item["payment_processor"]),
    )


def latest_available_payment_records(records: list[dict[str, str]]) -> list[dict[str, str]]:
    latest_by_brand_label: dict[tuple[str, str, str], dict[str, str]] = {}
    for record in records:
        key = (record["brand_name"], record["payment_label"], record["payment_processor"])
        previous = latest_by_brand_label.get(key)
        if previous is None or record["observed_at"] > previous["observed_at"]:
            latest_by_brand_label[key] = record
    return [record for record in latest_by_brand_label.values() if record["is_available"] == "true"]


def build_binary_matrix(
    rows: list[dict[str, str]],
    row_field: str,
    column_field: str,
    value_field: str = "is_available",
) -> tuple[list[str], list[dict[str, str]]]:
    row_values = sorted({row[row_field] for row in rows if row[row_field]})
    column_values = sorted({row[column_field] for row in rows if row[column_field]})
    seen = {
        (row[row_field], row[column_field])
        for row in rows
        if row[row_field] and row[column_field] and row.get(value_field) == "true"
    }
    matrix_rows = []
    for row_value in row_values:
        matrix_row = {row_field: row_value}
        for column_value in column_values:
            matrix_row[column_value] = "1" if (row_value, column_value) in seen else "0"
        matrix_rows.append(matrix_row)
    return [row_field, *column_values], matrix_rows


def build_payment_summary(
    input_path: Path,
    sheet_name: str,
    records: list[dict[str, str]],
    latest_available_records: list[dict[str, str]],
) -> dict[str, Any]:
    brands = sorted({record["brand_name"] for record in records})
    domains = sorted({record["domain"] for record in latest_available_records if record["domain"]})
    urls = sorted({record["url"] for record in latest_available_records if record["url"]})
    processors = sorted({record["payment_processor"] for record in latest_available_records if record["payment_processor"]})
    labels = sorted({record["payment_label"] for record in latest_available_records})
    periods = sorted({record["observed_at"] for record in records})
    processor_brand_counts = {
        processor: len({record["brand_name"] for record in latest_available_records if record["payment_processor"] == processor})
        for processor in processors
    }
    brand_profiles = []
    for brand in brands:
        brand_records = [record for record in latest_available_records if record["brand_name"] == brand]
        brand_processors = sorted({record["payment_processor"] for record in brand_records if record["payment_processor"]})
        brand_labels = sorted({record["payment_label"] for record in brand_records if record["payment_label"]})
        brand_methods = sorted({record["payment_method"] for record in brand_records if record["payment_method"]})
        brand_domains = sorted({record["domain"] for record in brand_records if record["domain"]})
        brand_urls = sorted({record["url"] for record in brand_records if record["url"]})
        brand_site_domains = sorted(
            {registrable_domain(record["domain"]) for record in brand_records if looks_like_brand_domain(brand, record["domain"])}
        )
        brand_site_urls = sorted(
            {
                record["url"]
                for record in brand_records
                if record["url"] and looks_like_brand_domain(brand, record["domain"])
            }
        )
        primary_brand_domain = primary_brand_domain_for_profile(brand, brand_records)
        brand_profiles.append(
            {
                "brand_name": brand,
                "payment_processors": brand_processors,
                "payment_labels": brand_labels,
                "payment_methods": brand_methods,
                "domains": brand_domains,
                "urls": brand_urls,
                "brand_site_domains": brand_site_domains,
                "brand_site_urls": brand_site_urls,
                "primary_brand_domain": primary_brand_domain,
                "processor_count": len(brand_processors),
                "payment_label_count": len(brand_labels),
                "payment_method_count": len(brand_methods),
                "domain_count": len(brand_domains),
                "url_count": len(brand_urls),
            }
        )
    brand_profiles.sort(key=lambda item: (item["processor_count"], item["payment_label_count"], item["brand_name"]), reverse=True)

    return {
        "title": "Infraestructura digital y procesadores de pago asociados a apuestas online",
        "source_file": input_path.name,
        "source_sheet": sheet_name,
        "periods": periods,
        "brand_count": len(brands),
        "domain_count": len(domains),
        "url_count": len(urls),
        "payment_label_count": len(labels),
        "payment_processor_count": len(processors),
        "observation_count": len(records),
        "latest_available_observation_count": len(latest_available_records),
        "brands": brands,
        "domains": domains,
        "urls": urls,
        "payment_processors": processors,
        "payment_labels": labels,
        "processor_brand_counts": processor_brand_counts,
        "brand_profiles": brand_profiles,
        "methodology_note": (
            "La planilla fuente registra presencia de medios/procesadores de pago por marca y fecha. "
            "El detalle conserva el texto original observado y extrae PSP conocidos cuando el rotulo lo permite."
        ),
    }


def join_csv_values(values: list[str]) -> str:
    return " | ".join(values)


def payment_profile_rows(brand_profiles: list[dict[str, Any]]) -> list[dict[str, str]]:
    rows = []
    for profile in sorted(brand_profiles, key=lambda item: item["brand_name"]):
        rows.append(
            {
                "brand_name": profile["brand_name"],
                "payment_gateways": join_csv_values(profile["payment_processors"]),
                "payment_methods": join_csv_values(profile["payment_labels"]),
                "payment_method_categories": join_csv_values(profile["payment_methods"]),
                "casino_primary_domain": profile["primary_brand_domain"],
                "casino_domains": join_csv_values(profile["brand_site_domains"]),
                "casino_urls": join_csv_values(profile["brand_site_urls"]),
                "observed_payment_domains": join_csv_values(profile["domains"]),
                "observed_payment_urls": join_csv_values(profile["urls"]),
                "payment_gateway_count": str(profile["processor_count"]),
                "payment_method_count": str(profile["payment_label_count"]),
                "casino_url_count": str(len(profile["brand_site_urls"])),
                "observed_payment_url_count": str(profile["url_count"]),
            }
        )
    return rows


def payment_profile_payload(summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "title": "Pasarelas, medios de pago y URLs por casino monitoreado",
        "source_file": summary["source_file"],
        "source_sheet": summary["source_sheet"],
        "periods": summary["periods"],
        "brand_count": summary["brand_count"],
        "profiles": sorted(summary["brand_profiles"], key=lambda item: item["brand_name"]),
        "methodology_note": (
            "payment_gateways corresponde a PSP o pasarelas identificadas desde el rotulo observado; "
            "payment_methods conserva los medios de pago rotulados en la planilla; casino_urls contiene URLs "
            "cuyo dominio coincide con la marca monitoreada cuando existen en el levantamiento."
        ),
    }


def profile_change_items(current_values: set[str], previous_values: set[str]) -> dict[str, list[str]]:
    return {
        "added": sorted(current_values - previous_values),
        "removed": sorted(previous_values - current_values),
    }


def build_payment_profile_changes_report(
    current_summary: dict[str, Any],
    previous_summary: dict[str, Any] | None,
) -> dict[str, Any]:
    if previous_summary is None:
        return {
            "current_input": current_summary["source_file"],
            "previous_input": None,
            "changed_brand_count": 0,
            "changed_brands": [],
            "note": "No previous payment infrastructure workbook available for comparison.",
        }

    current_profiles = {profile["brand_name"]: profile for profile in current_summary["brand_profiles"]}
    previous_profiles = {profile["brand_name"]: profile for profile in previous_summary["brand_profiles"]}
    changed_brands = []

    for brand in sorted(set(current_profiles) | set(previous_profiles)):
        current_profile = current_profiles.get(brand, {})
        previous_profile = previous_profiles.get(brand, {})
        changes = {
            "payment_gateways": profile_change_items(
                set(current_profile.get("payment_processors", [])),
                set(previous_profile.get("payment_processors", [])),
            ),
            "payment_methods": profile_change_items(
                set(current_profile.get("payment_labels", [])),
                set(previous_profile.get("payment_labels", [])),
            ),
            "casino_urls": profile_change_items(
                set(current_profile.get("brand_site_urls", [])),
                set(previous_profile.get("brand_site_urls", [])),
            ),
            "observed_payment_urls": profile_change_items(
                set(current_profile.get("urls", [])),
                set(previous_profile.get("urls", [])),
            ),
        }
        change_count = sum(
            len(section["added"]) + len(section["removed"])
            for section in changes.values()
        )
        if change_count:
            changed_brands.append(
                {
                    "brand_name": brand,
                    "change_count": change_count,
                    **changes,
                }
            )

    changed_brands.sort(key=lambda item: (item["change_count"], item["brand_name"]), reverse=True)
    return {
        "current_input": current_summary["source_file"],
        "previous_input": previous_summary["source_file"],
        "changed_brand_count": len(changed_brands),
        "changed_brands": changed_brands,
    }


def write_payment_processor_products() -> dict[str, Any] | None:
    input_path = default_payment_processor_workbook()
    if input_path is None:
        return None

    sheet_name, records = parse_payment_processor_matrix(input_path)
    latest_records = latest_available_payment_records(records)
    previous_input_path = default_previous_payment_processor_workbook(input_path)
    previous_summary = None
    if previous_input_path is not None:
        previous_sheet_name, previous_records = parse_payment_processor_matrix(previous_input_path)
        previous_latest_records = latest_available_payment_records(previous_records)
        previous_summary = build_payment_summary(
            previous_input_path,
            previous_sheet_name,
            previous_records,
            previous_latest_records,
        )

    write_csv(PAYMENT_PROCESSOR_OUTPUT_DIR / "url_payment_processor_detail.csv", PAYMENT_PROCESSOR_FIELD_ORDER, records)
    write_csv(SITE_PAYMENT_PROCESSOR_OUTPUT_DIR / "url_payment_processor_detail.csv", PAYMENT_PROCESSOR_FIELD_ORDER, records)

    processor_fieldnames, processor_rows = build_binary_matrix(latest_records, "brand_name", "payment_processor")
    if processor_rows:
        write_csv(PAYMENT_PROCESSOR_OUTPUT_DIR / "payment_processors_by_brand.csv", processor_fieldnames, processor_rows)
        write_csv(SITE_PAYMENT_PROCESSOR_OUTPUT_DIR / "payment_processors_by_brand.csv", processor_fieldnames, processor_rows)

    method_fieldnames, method_rows = build_binary_matrix(latest_records, "brand_name", "payment_method")
    if method_rows:
        write_csv(PAYMENT_PROCESSOR_OUTPUT_DIR / "payment_methods_by_brand.csv", method_fieldnames, method_rows)
        write_csv(SITE_PAYMENT_PROCESSOR_OUTPUT_DIR / "payment_methods_by_brand.csv", method_fieldnames, method_rows)

    label_fieldnames, label_rows = build_binary_matrix(latest_records, "brand_name", "payment_label")
    if label_rows:
        write_csv(PAYMENT_PROCESSOR_OUTPUT_DIR / "payment_labels_by_brand.csv", label_fieldnames, label_rows)
        write_csv(SITE_PAYMENT_PROCESSOR_OUTPUT_DIR / "payment_labels_by_brand.csv", label_fieldnames, label_rows)

    domains_by_brand = sorted(
        {
            (record["brand_name"], record["domain"], record["url"])
            for record in latest_records
            if record["domain"] or record["url"]
        }
    )
    write_csv(
        PAYMENT_PROCESSOR_OUTPUT_DIR / "domains_by_brand.csv",
        ["brand_name", "domain", "url"],
        [{"brand_name": brand_name, "domain": domain, "url": url} for brand_name, domain, url in domains_by_brand],
    )
    write_csv(
        SITE_PAYMENT_PROCESSOR_OUTPUT_DIR / "domains_by_brand.csv",
        ["brand_name", "domain", "url"],
        [{"brand_name": brand_name, "domain": domain, "url": url} for brand_name, domain, url in domains_by_brand],
    )

    network_edges = []
    seen_edges: set[tuple[str, str, str]] = set()
    for record in latest_records:
        target = record["payment_processor"] or record["payment_label"]
        edge = (record["brand_name"], target, record["payment_method"])
        if edge in seen_edges:
            continue
        seen_edges.add(edge)
        network_edges.append(
            {
                "source": record["brand_name"],
                "target": target,
                "relationship": "uses_payment_infrastructure",
                "payment_method": record["payment_method"],
            }
        )
    write_csv(
        PAYMENT_PROCESSOR_OUTPUT_DIR / "network_edges.csv",
        ["source", "target", "relationship", "payment_method"],
        network_edges,
    )
    write_csv(
        SITE_PAYMENT_PROCESSOR_OUTPUT_DIR / "network_edges.csv",
        ["source", "target", "relationship", "payment_method"],
        network_edges,
    )

    summary = build_payment_summary(input_path, sheet_name, records, latest_records)
    profile_payload = payment_profile_payload(summary)
    profile_rows = payment_profile_rows(summary["brand_profiles"])
    profile_fieldnames = [
        "brand_name",
        "payment_gateways",
        "payment_methods",
        "payment_method_categories",
        "casino_primary_domain",
        "casino_domains",
        "casino_urls",
        "observed_payment_domains",
        "observed_payment_urls",
        "payment_gateway_count",
        "payment_method_count",
        "casino_url_count",
        "observed_payment_url_count",
    ]
    write_csv(PAYMENT_PROCESSOR_OUTPUT_DIR / "payment_infrastructure_by_casino.csv", profile_fieldnames, profile_rows)
    write_csv(SITE_PAYMENT_PROCESSOR_OUTPUT_DIR / "payment_infrastructure_by_casino.csv", profile_fieldnames, profile_rows)
    write_json(PAYMENT_PROCESSOR_OUTPUT_DIR / "payment_infrastructure_by_casino.json", profile_payload)
    write_json(SITE_PAYMENT_PROCESSOR_OUTPUT_DIR / "payment_infrastructure_by_casino.json", profile_payload)
    changes_report = build_payment_profile_changes_report(summary, previous_summary)
    summary["payment_infrastructure_changes_report"] = changes_report
    write_json(PAYMENT_PROCESSOR_OUTPUT_DIR / "payment_infrastructure_changes_report.json", changes_report)
    write_json(SITE_PAYMENT_PROCESSOR_OUTPUT_DIR / "payment_infrastructure_changes_report.json", changes_report)
    write_json(PAYMENT_PROCESSOR_OUTPUT_DIR / "summary.json", summary)
    write_json(SITE_PAYMENT_PROCESSOR_OUTPUT_DIR / "summary.json", summary)
    return summary


def clean_infolobby_value(value: str | None) -> str:
    return " ".join((value or "").replace("\t", "").strip().split())


def normalize_infolobby_lookup(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", clean_infolobby_value(value))
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    ascii_value = re.sub(r"[^A-Za-z0-9 ]+", " ", ascii_value).upper()
    return " ".join(ascii_value.split())


def canonical_lobbyist_name(value: str | None) -> str:
    cleaned = clean_infolobby_value(value)
    lookup = normalize_infolobby_lookup(cleaned)
    if "CARLOS" in lookup and "BAEZA" in lookup:
        return "Carlos Baeza / Carlos Baeza Guíñez"
    if "NICOLE" in lookup and "MORANDE" in lookup:
        return "Nicole Morandé Pizarro"
    return cleaned.title() if cleaned.isupper() else cleaned


def normalize_beneficiary_name(value: str) -> str:
    cleaned = clean_infolobby_value(value)
    return cleaned.title() if cleaned.isupper() and len(cleaned) > 4 else cleaned


def valid_infolobby_beneficiary(value: str) -> bool:
    cleaned = normalize_infolobby_lookup(value)
    return bool(cleaned) and cleaned not in {"S I", "SI", "N A", "NA", "N APLICA", "NO APLICA", "NINGUNO"}


def infolobby_catalog_path(filename: str) -> Path:
    local_path = INFOLOBBY_INPUT_DIR / filename
    if local_path.exists():
        return local_path

    cached_path = INFOLOBBY_CACHE_DIR / filename
    if cached_path.exists():
        return cached_path

    if os.environ.get("INFOLOBBY_REFRESH") != "1":
        raise FileNotFoundError(
            f"{filename} not found in {INFOLOBBY_INPUT_DIR} or {INFOLOBBY_CACHE_DIR}. "
            "Set INFOLOBBY_REFRESH=1 to download InfoLobby catalogs."
        )

    INFOLOBBY_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    request = Request(INFOLOBBY_CATALOGS[filename], headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(request, timeout=180, context=ssl._create_unverified_context()) as response:
        cached_path.write_bytes(response.read())
    return cached_path


def iter_infolobby_rows(filename: str):
    path = infolobby_catalog_path(filename)
    with path.open("r", encoding="utf-16", newline="") as handle:
        yield from csv.DictReader(handle)


def compact_counted_labels(counter: dict[str, int] | defaultdict[str, int], limit: int = 4) -> str:
    items = sorted(counter.items(), key=lambda item: (-item[1], item[0]))[:limit]
    labels = [f"{label} ({count})" for label, count in items]
    remaining = max(len(counter) - limit, 0)
    if remaining:
        labels.append(f"+{remaining} más")
    return "; ".join(labels)


def build_infolobby_lobby_product() -> dict[str, Any] | None:
    required_files = {
        "activos.csv",
        "datosAudiencia.csv",
        "asistenciasPasivos.csv",
        "representaciones.csv",
        "trabajaPara.csv",
    }
    try:
        for filename in required_files:
            infolobby_catalog_path(filename)
    except Exception as error:
        existing_summary_path = INFOLOBBY_OUTPUT_DIR / "summary.json"
        if existing_summary_path.exists():
            existing_summary = json.loads(existing_summary_path.read_text(encoding="utf-8"))
            if INFOLOBBY_OUTPUT_DIR.exists():
                shutil.copytree(INFOLOBBY_OUTPUT_DIR, SITE_INFOLOBBY_OUTPUT_DIR, dirs_exist_ok=True)
            return existing_summary
        summary = {
            "available": False,
            "error": str(error),
            "source_name": "InfoLobby - Consejo para la Transparencia",
            "source_url": INFOLOBBY_CATALOG_URL,
            "source_page_consulted_at": datetime.now().date().isoformat(),
            "topic_filter": INFOLOBBY_TOPIC_PATTERN.pattern,
            "top_lobbyists": [],
        }
        write_json(INFOLOBBY_OUTPUT_DIR / "summary.json", summary)
        write_json(SITE_INFOLOBBY_OUTPUT_DIR / "summary.json", summary)
        return summary

    matched_uri_to_code: dict[str, str] = {}
    matched_code_to_meta: dict[str, dict[str, str]] = {}
    for row in iter_infolobby_rows("datosAudiencia.csv"):
        topic_text = " ".join(row.get(field, "") or "" for field in ("observaciones", "descripcion", "materia"))
        if not INFOLOBBY_TOPIC_PATTERN.search(topic_text):
            continue
        code = clean_infolobby_value(row.get("CodigoURI")).lower()
        uri = clean_infolobby_value(row.get("uriAudiencia"))
        if code and uri:
            matched_uri_to_code[uri] = code
            matched_code_to_meta[code] = row

    matched_codes = set(matched_code_to_meta)
    passives_by_code: dict[str, set[tuple[str, str, str]]] = defaultdict(set)
    for row in iter_infolobby_rows("asistenciasPasivos.csv"):
        code = clean_infolobby_value(row.get("codigoAudiencia")).lower()
        if code not in matched_codes:
            continue
        passive_name = clean_infolobby_value(row.get("pasivo"))
        passive_role = clean_infolobby_value(row.get("cargo"))
        passive_organization = clean_infolobby_value(row.get("organismo"))
        if passive_name:
            passives_by_code[code].add((passive_name, passive_role, passive_organization))

    represented_by_code: dict[str, set[str]] = defaultdict(set)
    for row in iter_infolobby_rows("representaciones.csv"):
        code = clean_infolobby_value(row.get("codigoAudiencia")).lower()
        represented = clean_infolobby_value(row.get("representado"))
        if code in matched_codes and valid_infolobby_beneficiary(represented):
            represented_by_code[code].add(normalize_beneficiary_name(represented))

    employer_by_code: dict[str, set[str]] = defaultdict(set)
    for row in iter_infolobby_rows("trabajaPara.csv"):
        code = clean_infolobby_value(row.get("codigoAudiencia")).lower()
        employer = clean_infolobby_value(row.get("empresaLobby"))
        if code in matched_codes and valid_infolobby_beneficiary(employer):
            employer_by_code[code].add(normalize_beneficiary_name(employer))

    lobbyist_counts: dict[str, int] = defaultdict(int)
    lobbyist_audiences: dict[str, set[str]] = defaultdict(set)
    lobbyist_beneficiaries: dict[str, defaultdict[str, int]] = defaultdict(lambda: defaultdict(int))
    lobbyist_passives: dict[str, defaultdict[tuple[str, str, str], int]] = defaultdict(lambda: defaultdict(int))
    for row in iter_infolobby_rows("activos.csv"):
        code = matched_uri_to_code.get(clean_infolobby_value(row.get("uriAudiencia")))
        if not code:
            continue
        lobbyist = canonical_lobbyist_name(row.get("nombreActivo") or row.get("nombre"))
        if not lobbyist:
            continue
        lobbyist_counts[lobbyist] += 1
        lobbyist_audiences[lobbyist].add(code)

        beneficiaries = represented_by_code.get(code) or employer_by_code.get(code) or {"Sin representado/empleador identificado"}
        for beneficiary in beneficiaries:
            lobbyist_beneficiaries[lobbyist][beneficiary] += 1

        passives = passives_by_code.get(code) or {("Sin sujeto pasivo identificado", "", "")}
        for passive in passives:
            lobbyist_passives[lobbyist][passive] += 1

    top_lobbyist_names = sorted(lobbyist_counts, key=lambda name: (-lobbyist_counts[name], name))[:5]
    top_rows: list[dict[str, Any]] = []
    detail_rows: list[dict[str, Any]] = []

    for rank, lobbyist in enumerate(top_lobbyist_names, start=1):
        beneficiary_summary = compact_counted_labels(lobbyist_beneficiaries[lobbyist], limit=3)
        passive_items = sorted(lobbyist_passives[lobbyist].items(), key=lambda item: (-item[1], item[0][0]))[:10]
        passive_meetings = [
            {
                "passive_name": passive_name,
                "passive_role": passive_role,
                "passive_organization": passive_organization,
                "meetings_count": count,
                "display": f"{passive_name} ({passive_role})" if passive_role else passive_name,
            }
            for (passive_name, passive_role, passive_organization), count in passive_items
        ]
        top_rows.append(
            {
                "rank": rank,
                "lobbyist_name": lobbyist,
                "beneficiary_summary": beneficiary_summary,
                "lobbyist_display": f"{lobbyist} ({beneficiary_summary})" if beneficiary_summary else lobbyist,
                "meeting_count": lobbyist_counts[lobbyist],
                "unique_audience_count": len(lobbyist_audiences[lobbyist]),
                "passive_meetings": passive_meetings,
            }
        )
        for (passive_name, passive_role, passive_organization), count in sorted(
            lobbyist_passives[lobbyist].items(), key=lambda item: (-item[1], item[0][0])
        ):
            detail_rows.append(
                {
                    "rank": rank,
                    "lobbyist_name": lobbyist,
                    "beneficiary_summary": beneficiary_summary,
                    "passive_name": passive_name,
                    "passive_role": passive_role,
                    "passive_organization": passive_organization,
                    "meetings_count": count,
                }
            )

    summary = {
        "available": True,
        "source_name": "InfoLobby - Consejo para la Transparencia",
        "source_url": INFOLOBBY_CATALOG_URL,
        "source_page_consulted_at": datetime.now().date().isoformat(),
        "topic_filter_label": "ley de casinos, apuestas online, plataformas de apuestas y casas de apuestas",
        "matched_audience_count": len(matched_codes),
        "distinct_lobbyist_count": len(lobbyist_counts),
        "top_lobbyists": top_rows,
    }

    top_fieldnames = [
        "rank",
        "lobbyist_name",
        "beneficiary_summary",
        "lobbyist_display",
        "meeting_count",
        "unique_audience_count",
        "passive_meetings_summary",
    ]
    top_csv_rows = [
        {
            **{key: row[key] for key in top_fieldnames if key != "passive_meetings_summary"},
            "passive_meetings_summary": "; ".join(
                f"{item['display']}: {item['meetings_count']}" for item in row["passive_meetings"]
            ),
        }
        for row in top_rows
    ]
    detail_fieldnames = [
        "rank",
        "lobbyist_name",
        "beneficiary_summary",
        "passive_name",
        "passive_role",
        "passive_organization",
        "meetings_count",
    ]

    write_csv(INFOLOBBY_OUTPUT_DIR / "top_lobbyists.csv", top_fieldnames, top_csv_rows)
    write_csv(SITE_INFOLOBBY_OUTPUT_DIR / "top_lobbyists.csv", top_fieldnames, top_csv_rows)
    write_csv(INFOLOBBY_OUTPUT_DIR / "lobbyist_passive_meetings.csv", detail_fieldnames, detail_rows)
    write_csv(SITE_INFOLOBBY_OUTPUT_DIR / "lobbyist_passive_meetings.csv", detail_fieldnames, detail_rows)
    write_json(INFOLOBBY_OUTPUT_DIR / "summary.json", summary)
    write_json(SITE_INFOLOBBY_OUTPUT_DIR / "summary.json", summary)
    return summary


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=True, indent=2)


def load_site_versions(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    versions = payload.get("versions", [])
    return [item for item in versions if isinstance(item, dict) and item.get("id")]


def update_site_versions_manifest(current_version: dict[str, str]) -> list[dict[str, str]]:
    current_id = current_version["id"]
    versions = [current_version]

    for entry in load_site_versions(SITE_VERSIONS_OUTPUT):
        if entry.get("id") == current_id:
            continue
        archive_path = entry.get("archive_path") or f"versiones/{entry['id']}/"
        normalized = {
            "id": entry["id"],
            "label": entry.get("label", entry["id"]),
            "coverage_end": entry.get("coverage_end", ""),
            "source_file": entry.get("source_file", ""),
            "path": archive_path,
            "archive_path": archive_path,
        }
        versions.append(normalized)

    versions.sort(key=lambda item: item.get("coverage_end", item["id"]), reverse=True)
    write_json(
        SITE_VERSIONS_OUTPUT,
        {
            "generated_from": current_version["label"],
            "versions": versions,
        },
    )
    return versions


def write_site_version_snapshot(
    version_entry: dict[str, str],
    site_html: str,
    site_payload: dict[str, Any],
    public_records: list[dict[str, str]],
) -> None:
    snapshot_dir = SITE_OUTPUT_DIR / version_entry["archive_path"]
    snapshot_data_dir = snapshot_dir / "data"

    write_text(snapshot_dir / "index.html", site_html)
    write_json(snapshot_data_dir / "inversion_semanal_por_casino_ilegal_summary.json", site_payload)
    write_json(snapshot_data_dir / "master_investment_detail.json", public_records)

    if SITE_PAYMENT_PROCESSOR_OUTPUT_DIR.exists():
        shutil.copytree(
            SITE_PAYMENT_PROCESSOR_OUTPUT_DIR,
            snapshot_data_dir / "infraestructura_pagos_urls",
            dirs_exist_ok=True,
        )
    if SITE_INFOLOBBY_OUTPUT_DIR.exists():
        shutil.copytree(
            SITE_INFOLOBBY_OUTPUT_DIR,
            snapshot_data_dir / "lobby_casas_apuesta",
            dirs_exist_ok=True,
        )


def compare_aggregations(
    current_aggregations: dict[str, dict[str, dict[str, float]]],
    previous_aggregations: dict[str, dict[str, dict[str, float]]],
    brands: list[str],
    periods: list[str],
) -> dict[str, dict[str, dict[str, float]]]:
    scopes = sorted(set(current_aggregations) | set(previous_aggregations))
    deltas: dict[str, dict[str, dict[str, float]]] = defaultdict(lambda: defaultdict(dict))

    for scope in scopes:
        for brand in brands:
            for period in periods:
                current_value = current_aggregations.get(scope, {}).get(brand, {}).get(period, 0.0)
                previous_value = previous_aggregations.get(scope, {}).get(brand, {}).get(period, 0.0)
                deltas[scope][brand][period] = round(current_value - previous_value, 2)

    return deltas


def build_changes_report(
    current_input: Path,
    previous_input: Path | None,
    delta_aggregations: dict[str, dict[str, dict[str, float]]],
) -> dict[str, Any]:
    changed_brands: list[dict[str, Any]] = []
    total_scope = delta_aggregations.get("total", {})

    for brand in sorted(total_scope):
        total_change = round(sum(total_scope[brand].values()), 2)
        if total_change != 0:
            changed_brands.append({"brand_name": brand, "total_change": total_change})

    changed_brands.sort(key=lambda item: abs(item["total_change"]), reverse=True)
    return {
        "current_input": format_cut_label(current_input),
        "previous_input": format_cut_label(previous_input) if previous_input else None,
        "changed_brand_count": len(changed_brands),
        "changed_brands": changed_brands,
    }


def build_validation_report(
    input_path: Path,
    worksheet_name: str | None,
    records: list[dict[str, str]],
    product_brands: list[str],
    product_periods: list[str],
    table_names: list[str],
    previous_input_path: Path | None,
    qa_passed: bool,
    errors: list[str],
) -> dict[str, Any]:
    return {
        "input_file": format_cut_label(input_path),
        "previous_input_file": format_cut_label(previous_input_path) if previous_input_path else None,
        "worksheet_name": worksheet_name,
        "raw_record_count": len(records),
        "product_record_count": sum(1 for record in records if not is_excluded_product_brand(record["brand_name"])),
        "product_brands": product_brands,
        "excluded_product_scope": "marcas reguladas en Chile y registros fuera del universo publico validado en CRUCES",
        "excluded_product_brand_count": len({record["brand_name"] for record in records if is_excluded_product_brand(record["brand_name"])}),
        "period_granularity": "week",
        "periods": product_periods,
        "tables_generated": table_names,
        "qa_passed": qa_passed,
        "error_count": len(errors),
        "errors": errors,
    }


def main() -> int:
    args = parse_args()
    previous_input = args.previous_input or default_previous_workbook(args.input)
    raw_sheet_name = resolve_available_sheet_name(args.input, RAW_SHEET_CANDIDATES)
    records = load_records(args.input)
    public_records = published_records(records)
    errors = validate_records(records)

    if errors:
        write_json(
            VALIDATION_OUTPUT,
            build_validation_report(
                input_path=args.input,
                worksheet_name=raw_sheet_name,
                records=records,
                product_brands=[],
                product_periods=[],
                table_names=[],
                previous_input_path=previous_input,
                qa_passed=False,
                errors=errors,
            ),
        )
        raise SystemExit("Validation failed. See output/master/validation_report.json for details.")

    write_csv(PROCESSED_DETAIL_OUTPUT, list(CANONICAL_FIELD_ORDER), public_records)
    write_csv(MASTER_CSV_OUTPUT, list(CANONICAL_FIELD_ORDER), public_records)
    write_json(MASTER_JSON_OUTPUT, public_records)

    periods, brands, aggregations = aggregate_period_tables(records, "week_ending")
    monthly_periods, _, monthly_aggregations = aggregate_period_tables(records, "month")
    summary_fieldnames = ["brand_name", *periods, "total"]
    table_names: list[str] = []

    for table_name, values_by_brand in sorted(aggregations.items()):
        output_path = PRODUCT_OUTPUT_DIR / f"{table_name}.csv"
        summary_rows = build_summary_rows(periods, brands, values_by_brand)
        write_csv(output_path, summary_fieldnames, summary_rows)
        table_names.append(f"{table_name}.csv")

    previous_records = load_records(previous_input) if previous_input else []
    previous_periods, previous_brands, previous_aggregations = aggregate_period_tables(previous_records, "week_ending") if previous_records else ([], [], {})
    delta_periods = sort_periods(set(periods) | set(previous_periods))
    delta_brands = sorted(set(brands) | set(previous_brands))
    delta_aggregations = compare_aggregations(aggregations, previous_aggregations, delta_brands, delta_periods)

    for table_name, values_by_brand in sorted(delta_aggregations.items()):
        output_path = CHANGES_OUTPUT_DIR / f"{table_name}.csv"
        summary_rows = build_summary_rows(delta_periods, delta_brands, values_by_brand)
        write_csv(output_path, ["brand_name", *delta_periods, "total"], summary_rows)

    write_json(CHANGES_OUTPUT_DIR / "changes_report.json", build_changes_report(args.input, previous_input, delta_aggregations))

    qa_report = run_qa(args.input, monthly_periods, brands, monthly_aggregations, periods, aggregations)
    write_json(QA_OUTPUT, qa_report)
    if not qa_report["passed"]:
        raise SystemExit("QA failed. See output/master/qa_report.json for details.")

    payment_summary = write_payment_processor_products()
    infolobby_lobby_summary = build_infolobby_lobby_product()
    visualization_payload = build_visualization_payload(
        args.input,
        raw_sheet_name,
        public_records,
        periods,
        brands,
        aggregations,
        qa_report,
        payment_summary,
        infolobby_lobby_summary,
    )
    write_json(VISUALIZATION_DATA_OUTPUT, visualization_payload)
    current_site_version = build_site_version_entry(
        args.input,
        path="/",
        archive_path=f"versiones/{version_id_for_input(args.input)}/",
    )
    update_site_versions_manifest(current_site_version)

    visualization_page_payload = with_site_version_context(
        visualization_payload,
        current_site_version,
        "../site/versiones.json",
    )
    site_page_payload = with_site_version_context(
        visualization_payload,
        current_site_version,
        "./versiones.json",
    )
    snapshot_page_payload = with_site_version_context(
        visualization_payload,
        current_site_version,
        "../../versiones.json",
    )

    visualization_html = build_visualization_html(visualization_page_payload)
    site_html = build_visualization_html(site_page_payload)
    snapshot_html = build_visualization_html(snapshot_page_payload)
    write_text(VISUALIZATION_HTML_OUTPUT, visualization_html)
    write_text(STACKED_SVG_OUTPUT, build_stacked_bars_svg(visualization_payload))
    write_text(HEATMAP_SVG_OUTPUT, build_lines_svg(visualization_payload))
    write_text(SITE_INDEX_OUTPUT, site_html)
    write_json(SITE_SUMMARY_OUTPUT, site_page_payload)
    write_json(SITE_MASTER_OUTPUT, public_records)
    write_site_version_snapshot(current_site_version, snapshot_html, snapshot_page_payload, public_records)

    write_json(
        VALIDATION_OUTPUT,
        build_validation_report(
            input_path=args.input,
            worksheet_name=raw_sheet_name,
            records=records,
            product_brands=brands,
            product_periods=periods,
            table_names=table_names + ["changes_report.json"]
            + (
                [
                    "infraestructura_pagos_urls/summary.json",
                    "infraestructura_pagos_urls/payment_infrastructure_by_casino.csv",
                    "infraestructura_pagos_urls/payment_infrastructure_by_casino.json",
                    "infraestructura_pagos_urls/payment_infrastructure_changes_report.json",
                ]
                if payment_summary
                else []
            )
            + (
                [
                    "lobby_casas_apuesta/summary.json",
                    "lobby_casas_apuesta/top_lobbyists.csv",
                    "lobby_casas_apuesta/lobbyist_passive_meetings.csv",
                ]
                if infolobby_lobby_summary
                else []
            ),
            previous_input_path=previous_input,
            qa_passed=qa_report["passed"],
            errors=[],
        ),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
