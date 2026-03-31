from __future__ import annotations

import argparse
import re
from pathlib import Path
from pprint import pformat
from typing import Any

from app.scripts.kabum_catalog import fetch_kabum_products


KABUM_CATEGORY_URL = "https://www.kabum.com.br/hardware/memoria-ram"
DEFAULT_OUTPUT_PATH = Path("app/data/rams.py")


def parse_kabum_products(products: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rams: list[dict[str, Any]] = []
    seen_skus: set[str] = set()

    for product in products:
        ram = parse_kabum_product(product)
        if ram is None:
            continue
        if ram["sku"] in seen_skus:
            continue
        rams.append(ram)
        seen_skus.add(ram["sku"])

    return sorted(rams, key=lambda item: (item["brand"], item["name"]))


def parse_kabum_product(product: dict[str, Any]) -> dict[str, Any] | None:
    name = _normalize_whitespace(product.get("name") or "")
    if not name:
        return None

    sku = _extract_sku(name)
    generation = _parse_generation(name)
    speed_mhz = _parse_speed_mhz(name)
    capacity_gb = _parse_total_capacity_gb(name)
    if sku is None or generation is None or speed_mhz is None or capacity_gb is None:
        return None

    module_count = _parse_module_count(name) or 1
    capacity_per_module_gb = capacity_gb // module_count if module_count > 0 else None
    form_factor = _parse_form_factor(name)
    device = "notebook" if form_factor == "SODIMM" else "desktop"
    profile = _parse_profile(name)

    return {
        "name": name,
        "sku": sku,
        "brand": _normalize_whitespace((product.get("manufacturer") or {}).get("name") or name.split()[0]),
        "generation": generation,
        "form_factor": form_factor,
        "capacity_gb": capacity_gb,
        "module_count": module_count,
        "capacity_per_module_gb": capacity_per_module_gb,
        "speed_mhz": speed_mhz,
        "cl": _parse_cl(name),
        "rgb": _parse_rgb(name),
        "profile": profile,
        "device": device,
        "compatibility": {
            "desktop": device == "desktop",
            "notebook": device == "notebook",
            "platforms": [generation],
        },
    }


def render_rams_module(rams: list[dict[str, Any]]) -> str:
    return f"RAMS = {pformat(rams, sort_dicts=False, width=100)}\n"


def write_rams_module(rams: list[dict[str, Any]], *, output_path: Path = DEFAULT_OUTPUT_PATH) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_rams_module(rams), encoding="utf-8")


def build_rams(
    *,
    output_path: Path = DEFAULT_OUTPUT_PATH,
    page_limit: int | None = None,
) -> list[dict[str, Any]]:
    products = fetch_kabum_products(category_url=KABUM_CATEGORY_URL, page_limit=page_limit)
    rams = parse_kabum_products(products)
    write_rams_module(rams, output_path=output_path)
    return rams


def main() -> None:
    parser = argparse.ArgumentParser(description="Gera app/data/rams.py a partir do catalogo da KaBuM!.")
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help="Arquivo Python de saida. Padrao: app/data/rams.py",
    )
    parser.add_argument(
        "--page-limit",
        type=int,
        default=None,
        help="Limita a quantidade de paginas do catalogo da KaBuM!. Util para debug.",
    )
    args = parser.parse_args()

    rams = build_rams(output_path=args.output, page_limit=args.page_limit)
    print(f"Gerado {args.output} com {len(rams)} memoria(s).")


def _normalize_whitespace(value: str) -> str:
    return " ".join(value.replace("\xa0", " ").split()).strip()


def _extract_sku(name: str) -> str | None:
    match = re.search(r"-\s*([A-Z0-9][A-Z0-9\-/\.]+)\s*$", name, re.IGNORECASE)
    if match is None:
        return None
    return match.group(1).upper()


def _parse_generation(name: str) -> str | None:
    for generation in ("DDR5", "DDR4"):
        if generation in name.upper():
            return generation
    return None


def _parse_form_factor(name: str) -> str:
    normalized = name.upper()
    if "SODIMM" in normalized or "SO-DIMM" in normalized or "NOTEBOOK" in normalized:
        return "SODIMM"
    return "UDIMM"


def _parse_total_capacity_gb(name: str) -> int | None:
    normalized = name.upper()
    kit_match = re.search(r"(\d+)\s*GB\s*\((\d+)X\s*(\d+)\s*GB\)", normalized)
    if kit_match is not None:
        return int(kit_match.group(1))

    single_match = re.search(r"(\d+)\s*GB", normalized)
    if single_match is None:
        return None
    return int(single_match.group(1))


def _parse_module_count(name: str) -> int | None:
    normalized = name.upper()
    match = re.search(r"\((\d+)X\s*(\d+)\s*GB\)", normalized)
    if match is None:
        return None
    return int(match.group(1))


def _parse_speed_mhz(name: str) -> int | None:
    normalized = name.upper()
    match = re.search(r"(\d{4,5})\s*MHZ", normalized)
    if match is None:
        return None
    return int(match.group(1))


def _parse_cl(name: str) -> int | None:
    match = re.search(r"\bCL\s*([0-9]{1,2})\b", name.upper())
    if match is None:
        return None
    return int(match.group(1))


def _parse_rgb(name: str) -> bool:
    normalized = name.upper()
    return "RGB" in normalized


def _parse_profile(name: str) -> str:
    normalized = name.upper()
    has_xmp = "XMP" in normalized
    has_expo = "EXPO" in normalized
    if has_xmp and has_expo:
        return "XMP/EXPO"
    if has_expo:
        return "EXPO"
    if has_xmp:
        return "XMP"
    return "unknown"


if __name__ == "__main__":
    main()
