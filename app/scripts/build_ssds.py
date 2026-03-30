from __future__ import annotations

import argparse
from html.parser import HTMLParser
from pathlib import Path
from pprint import pformat
from typing import Any
from urllib.parse import urljoin

import httpx


TOP_SSD_URL = "https://ssd-tester.com/top_ssd.php"
DEFAULT_OUTPUT_PATH = Path("app/data/ssds.py")


class _TopSsdTableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._inside_row = False
        self._inside_cell = False
        self._cell_tag: str | None = None
        self._current_row: list[dict[str, Any]] = []
        self._current_cell_text: list[str] = []
        self._current_link_href: str | None = None
        self._current_image_alt: str | None = None
        self.rows: list[list[dict[str, Any]]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)

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
            self._current_link_href = None
            self._current_image_alt = None
            return

        if not self._inside_cell:
            return

        if tag == "a":
            href = attributes.get("href")
            if href:
                self._current_link_href = href
            return

        if tag == "img":
            alt = attributes.get("alt")
            if alt:
                self._current_image_alt = alt.strip()

    def handle_endtag(self, tag: str) -> None:
        if tag in {"td", "th"} and self._inside_cell and self._cell_tag == tag:
            text = _normalize_whitespace("".join(self._current_cell_text))
            self._current_row.append(
                {
                    "text": text,
                    "href": self._current_link_href,
                    "image_alt": self._current_image_alt,
                    "tag": self._cell_tag,
                }
            )
            self._inside_cell = False
            self._cell_tag = None
            self._current_cell_text = []
            self._current_link_href = None
            self._current_image_alt = None
            return

        if tag == "tr" and self._inside_row:
            if self._current_row:
                self.rows.append(self._current_row)
            self._inside_row = False
            self._current_row = []

    def handle_data(self, data: str) -> None:
        if self._inside_cell:
            self._current_cell_text.append(data)


def fetch_top_ssd_html(*, url: str = TOP_SSD_URL, timeout: float = 30.0) -> str:
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


def parse_top_ssd_html(html: str, *, base_url: str = TOP_SSD_URL) -> list[dict[str, Any]]:
    parser = _TopSsdTableParser()
    parser.feed(html)

    ssds: list[dict[str, Any]] = []
    seen_skus: set[str] = set()

    for row in parser.rows:
        if not _looks_like_data_row(row):
            continue

        score_text = row[0]["text"]
        name_text = row[1]["text"]
        image_alt = row[2]["image_alt"] or row[2]["text"]
        capacity_text = row[3]["text"]
        nand_text = row[4]["text"]
        dram_text = row[5]["text"]
        interface_text = row[9]["text"] if len(row) > 9 else ""
        href = row[1]["href"]

        sku = _normalize_sku(image_alt, name_text)
        if not sku or sku in seen_skus:
            continue

        score = _parse_int(score_text)
        capacity_gb = _parse_capacity_gb(capacity_text)
        if score is None or capacity_gb is None:
            continue

        ssd = {
            "name": name_text,
            "sku": sku,
            "brand": _detect_brand(name_text),
            "capacity_gb": capacity_gb,
            "interface": interface_text or None,
            "nand": nand_text or None,
            "dram": _parse_dram(dram_text),
            "benchmark": {
                "ssd_tester_score": score,
            },
        }
        if href:
            ssd["source_url"] = urljoin(base_url, href)

        ssds.append(ssd)
        seen_skus.add(sku)

    return sorted(ssds, key=lambda item: item["benchmark"]["ssd_tester_score"], reverse=True)


def render_ssds_module(ssds: list[dict[str, Any]]) -> str:
    return f"SSDS = {pformat(ssds, sort_dicts=False, width=100)}\n"


def write_ssds_module(ssds: list[dict[str, Any]], *, output_path: Path = DEFAULT_OUTPUT_PATH) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_ssds_module(ssds), encoding="utf-8")


def build_ssds(*, html: str, output_path: Path = DEFAULT_OUTPUT_PATH) -> list[dict[str, Any]]:
    ssds = parse_top_ssd_html(html)
    write_ssds_module(ssds, output_path=output_path)
    return ssds


def main() -> None:
    parser = argparse.ArgumentParser(description="Gera app/data/ssds.py a partir do ranking do SSD Tester.")
    parser.add_argument(
        "--input-html",
        type=Path,
        help="Arquivo HTML salvo localmente. Use esta opcao se estiver sem acesso de rede.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help="Arquivo Python de saida. Padrao: app/data/ssds.py",
    )
    parser.add_argument(
        "--url",
        default=TOP_SSD_URL,
        help=f"URL de origem. Padrao: {TOP_SSD_URL}",
    )
    args = parser.parse_args()

    if args.input_html is not None:
        html = args.input_html.read_text(encoding="utf-8")
    else:
        html = fetch_top_ssd_html(url=args.url)

    ssds = build_ssds(html=html, output_path=args.output)
    print(f"Gerado {args.output} com {len(ssds)} SSD(s).")


def _looks_like_data_row(row: list[dict[str, Any]]) -> bool:
    return len(row) > 9 and row[0]["tag"] == "td" and _parse_int(row[0]["text"]) is not None


def _normalize_whitespace(value: str) -> str:
    return " ".join(value.replace("\xa0", " ").split()).strip()


def _normalize_sku(raw_sku: str | None, fallback_name: str) -> str:
    if raw_sku:
        normalized = raw_sku.replace("Image:", "").strip()
        if normalized:
            return normalized

    return fallback_name.lower().replace("/", "-")


def _parse_int(value: str | None) -> int | None:
    if value is None:
        return None

    digits = "".join(character for character in value if character.isdigit())
    if not digits:
        return None

    return int(digits)


def _parse_capacity_gb(value: str) -> int | None:
    normalized = _normalize_whitespace(value).upper()
    number_text = normalized.split()[0] if normalized else ""
    digits = "".join(character for character in number_text if character.isdigit())
    if not digits:
        return None

    number = int(digits)
    if "TB" in normalized:
        return number * 1024
    return number


def _parse_dram(value: str) -> bool | None:
    normalized = _normalize_whitespace(value).lower()
    if "yes" in normalized:
        return True
    if "no" in normalized:
        return False
    return None


def _detect_brand(name: str) -> str:
    brand_prefixes = (
        "Western Digital",
        "TeamGroup",
        "SK hynix",
        "Kingston",
        "Samsung",
        "Crucial",
        "Seagate",
        "Corsair",
        "Gigabyte",
        "Patriot",
        "SanDisk",
        "Verbatim",
        "KIOXIA",
        "Apacer",
        "Acer",
        "Transcend",
        "Lexar",
        "ADATA",
        "Sabrent",
        "Biwin",
        "PNY",
        "MSI",
        "HP",
        "OWC",
        "Intel",
    )

    for prefix in brand_prefixes:
        if name.startswith(prefix):
            return prefix

    return name.split()[0]


if __name__ == "__main__":
    main()
