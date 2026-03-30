from __future__ import annotations

import argparse
import asyncio
import re
from html.parser import HTMLParser
from pathlib import Path
from pprint import pformat
from typing import Any
from urllib.parse import urljoin

import httpx


TOP_PSU_URL = "https://www.cybenetics.com/index.php?option=psu-performance-database"
PERFORMANCE_TABLE_PATH = "code/performance-in.php"
DEFAULT_OUTPUT_PATH = Path("app/data/psus.py")


class _HtmlTableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._inside_row = False
        self._inside_cell = False
        self._cell_tag: str | None = None
        self._current_row: list[dict[str, Any]] = []
        self._current_cell_text: list[str] = []
        self.rows: list[list[dict[str, Any]]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "tr":
            self._inside_row = True
            self._current_row = []
            return

        if not self._inside_row:
            return

        if tag in {"td", "th"}:
            self._inside_cell = True
            self._cell_tag = tag
            self._current_cell_text = []

    def handle_endtag(self, tag: str) -> None:
        if tag in {"td", "th"} and self._inside_cell and self._cell_tag == tag:
            text = _normalize_whitespace("".join(self._current_cell_text))
            self._current_row.append(
                {
                    "text": text,
                    "tag": self._cell_tag,
                }
            )
            self._inside_cell = False
            self._cell_tag = None
            self._current_cell_text = []
            return

        if tag == "tr" and self._inside_row:
            if self._current_row:
                self.rows.append(self._current_row)
            self._inside_row = False
            self._current_row = []

    def handle_data(self, data: str) -> None:
        if self._inside_cell:
            self._current_cell_text.append(data)


def fetch_performance_database_html(*, url: str = TOP_PSU_URL, timeout: float = 30.0) -> str:
    response = httpx.get(
        url,
        timeout=timeout,
        follow_redirects=True,
        headers={
            "User-Agent": "bestchoicepc-backend/1.0 (+local build script)",
        },
    )
    response.raise_for_status()
    return response.text


def parse_brand_options(html: str) -> list[tuple[str, str]]:
    select_match = re.search(r'<select class="parameters brand">(.*?)</select>', html, re.IGNORECASE | re.DOTALL)
    if select_match is None:
        return []

    options: list[tuple[str, str]] = []
    seen_ids: set[str] = set()

    for value, label in re.findall(r'<option value="([^"]+)">(.*?)</option>', select_match.group(1), re.IGNORECASE | re.DOTALL):
        normalized_value = value.strip()
        normalized_label = _normalize_whitespace(label)
        if normalized_value == "0" or not normalized_value or normalized_value in seen_ids:
            continue
        options.append((normalized_value, normalized_label))
        seen_ids.add(normalized_value)

    return options


async def fetch_performance_table_htmls(
    *,
    page_url: str = TOP_PSU_URL,
    page_html: str,
    volts: int = 1,
    form_factor: int = 0,
    wattage: str = "0,4000",
    atx: int = 0,
    sorting: str = "brand-asc",
    brand_limit: int | None = None,
    concurrency: int = 12,
    timeout: float = 30.0,
) -> list[str]:
    brands = parse_brand_options(page_html)
    if brand_limit is not None:
        brands = brands[:brand_limit]

    if not brands:
        return []

    semaphore = asyncio.Semaphore(concurrency)
    performance_url = urljoin(page_url, PERFORMANCE_TABLE_PATH)

    async with httpx.AsyncClient(
        timeout=timeout,
        follow_redirects=True,
        headers={
            "User-Agent": "bestchoicepc-backend/1.0 (+local build script)",
        },
    ) as client:
        response = await client.get(page_url)
        response.raise_for_status()

        async def _fetch_table(brand_id: str) -> str:
            async with semaphore:
                table_response = await client.get(
                    performance_url,
                    params={
                        "volts": str(volts),
                        "brand": brand_id,
                        "formFactor": str(form_factor),
                        "wattage": wattage,
                        "atx": str(atx),
                        "referenceScore": "0",
                        "sorting": sorting,
                    },
                    headers={
                        "Referer": page_url,
                        "X-Requested-With": "XMLHttpRequest",
                    },
                )
                table_response.raise_for_status()
                return table_response.text

        return await asyncio.gather(*[_fetch_table(brand_id) for brand_id, _brand_name in brands])


def parse_performance_table_html(html: str) -> list[dict[str, Any]]:
    parser = _HtmlTableParser()
    parser.feed(html)

    psus: list[dict[str, Any]] = []
    seen_skus: set[str] = set()

    for row in parser.rows:
        if not _looks_like_performance_row(row):
            continue

        brand = row[0]["text"]
        model = row[1]["text"]
        efficiency_rating = row[2]["text"]
        noise_rating = row[3]["text"]
        score = _parse_float(row[4]["text"])
        if not brand or not model or score is None:
            continue

        name = f"{brand} {model}".strip()
        sku = _slugify(name)
        if sku in seen_skus:
            continue

        psus.append(
            {
                "name": name,
                "sku": sku,
                "brand": brand,
                "wattage_w": _parse_wattage_w(model),
                "form_factor": _parse_form_factor(model),
                "atx_version": _parse_atx_version(model),
                "efficiency_rating": _normalize_optional(efficiency_rating),
                "noise_rating": _normalize_optional(noise_rating),
                "benchmark": {
                    "cybenetics_score": score,
                },
            }
        )
        seen_skus.add(sku)

    return psus


def render_psus_module(psus: list[dict[str, Any]]) -> str:
    return f"PSUS = {pformat(psus, sort_dicts=False, width=100)}\n"


def write_psus_module(psus: list[dict[str, Any]], *, output_path: Path = DEFAULT_OUTPUT_PATH) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_psus_module(psus), encoding="utf-8")


def build_psus_from_table_htmls(
    table_htmls: list[str],
    *,
    output_path: Path = DEFAULT_OUTPUT_PATH,
) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}

    for html in table_htmls:
        for psu in parse_performance_table_html(html):
            existing = merged.get(psu["sku"])
            if existing is None or psu["benchmark"]["cybenetics_score"] > existing["benchmark"]["cybenetics_score"]:
                merged[psu["sku"]] = psu

    psus = sorted(
        merged.values(),
        key=lambda item: item["benchmark"]["cybenetics_score"],
        reverse=True,
    )
    write_psus_module(psus, output_path=output_path)
    return psus


def build_psus(
    *,
    output_path: Path = DEFAULT_OUTPUT_PATH,
    url: str = TOP_PSU_URL,
    volts: int = 1,
    form_factor: int = 0,
    wattage: str = "0,4000",
    atx: int = 0,
    sorting: str = "brand-asc",
    brand_limit: int | None = None,
) -> list[dict[str, Any]]:
    page_html = fetch_performance_database_html(url=url)
    table_htmls = asyncio.run(
        fetch_performance_table_htmls(
            page_url=url,
            page_html=page_html,
            volts=volts,
            form_factor=form_factor,
            wattage=wattage,
            atx=atx,
            sorting=sorting,
            brand_limit=brand_limit,
        )
    )
    return build_psus_from_table_htmls(table_htmls, output_path=output_path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Gera app/data/psus.py a partir do banco da Cybenetics.")
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help="Arquivo Python de saida. Padrao: app/data/psus.py",
    )
    parser.add_argument(
        "--url",
        default=TOP_PSU_URL,
        help=f"URL de origem. Padrao: {TOP_PSU_URL}",
    )
    parser.add_argument(
        "--volts",
        type=int,
        default=1,
        choices=[1, 2],
        help="Entrada de tensao usada no banco da Cybenetics. 1=115V, 2=230V.",
    )
    parser.add_argument(
        "--brand-limit",
        type=int,
        default=None,
        help="Limita a quantidade de fabricantes consultados. Util para debug.",
    )
    args = parser.parse_args()

    psus = build_psus(
        output_path=args.output,
        url=args.url,
        volts=args.volts,
        brand_limit=args.brand_limit,
    )
    print(f"Gerado {args.output} com {len(psus)} PSU(s).")


def _looks_like_performance_row(row: list[dict[str, Any]]) -> bool:
    return len(row) > 4 and row[0]["tag"] == "td" and _parse_float(row[4]["text"]) is not None


def _normalize_whitespace(value: str) -> str:
    return " ".join(value.replace("\xa0", " ").split()).strip()


def _normalize_optional(value: str | None) -> str | None:
    if value is None:
        return None

    normalized = _normalize_whitespace(value)
    return normalized or None


def _parse_float(value: str | None) -> float | None:
    if value is None:
        return None

    normalized = _normalize_whitespace(value).replace(",", "")
    try:
        return float(normalized)
    except ValueError:
        return None


def _parse_wattage_w(model: str) -> int | None:
    match = re.search(r"(\d{3,4})\s*W", model, re.IGNORECASE)
    if match is None:
        return None
    return int(match.group(1))


def _parse_form_factor(model: str) -> str | None:
    normalized = model.upper()
    if "SFX-L" in normalized:
        return "SFX-L"
    if "SFX" in normalized:
        return "SFX"
    if "TFX" in normalized:
        return "TFX"
    if "FLEX ATX" in normalized:
        return "FLEX ATX"
    return None


def _parse_atx_version(model: str) -> str | None:
    match = re.search(r"ATX\s*v?([0-9]+\.[0-9]+)", model, re.IGNORECASE)
    if match is None:
        return None
    return f"ATX{match.group(1)}"


def _slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


if __name__ == "__main__":
    main()
