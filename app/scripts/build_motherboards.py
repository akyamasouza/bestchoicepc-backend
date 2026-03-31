from __future__ import annotations

import argparse
import re
from pathlib import Path
from pprint import pformat
from typing import Any

from app.scripts.kabum_catalog import fetch_kabum_products


KABUM_CATEGORY_URL = "https://www.kabum.com.br/hardware/placas-mae"
DEFAULT_OUTPUT_PATH = Path("app/data/motherboards.py")
SKIP_NAME_TOKENS = (
    "NOTEBOOK",
    "PARA NOTEBOOK",
    "THINKPAD",
    "THINKCENTRE",
    "MACBOOK",
    "LAPTOP",
    "TINY",
    "ALL IN ONE",
    "AIO",
    "NM-",
    "OEM",
    "COM CELERON",
    "DUAL-CORE",
)
GENERIC_SKUS = {
    "ATX",
    "MATX",
    "MATX-",
    "WIFI",
    "WIFI 6",
    "WIFI 7",
    "FI",
    "FI 6",
    "FI 7",
    "PRO",
    "OEM",
    "CORE",
    "HVS",
    "HDV",
}
KNOWN_SOCKETS = (
    "LGA 1851",
    "LGA1851",
    "LGA 1700",
    "LGA1700",
    "LGA 1200",
    "LGA1200",
    "LGA 1151",
    "LGA1151",
    "LGA 1155",
    "LGA1155",
    "LGA 2011",
    "LGA2011",
    "LGA 2066",
    "LGA2066",
    "AM5",
    "AM4",
    "AM3+",
    "AM3",
    "TR5",
    "STR5",
    "TRX4",
)
KNOWN_CHIPSETS = (
    "X870E",
    "X870",
    "B860",
    "Z890",
    "H810",
    "B850",
    "X670E",
    "X670",
    "B650E",
    "B650",
    "A620",
    "Z790",
    "H770",
    "B760",
    "H610",
    "Z690",
    "H670",
    "B660",
    "H510",
    "H470",
    "B560",
    "B460",
    "H410",
    "B450",
    "A520",
    "B550",
    "A320",
    "H81",
    "H61",
    "X570",
    "TRX50",
    "TRX40",
    "WRX90",
    "WRX80",
)


def parse_kabum_products(products: list[dict[str, Any]]) -> list[dict[str, Any]]:
    motherboards: list[dict[str, Any]] = []
    seen_skus: set[str] = set()

    for product in products:
        motherboard = parse_kabum_product(product)
        if motherboard is None:
            continue
        if motherboard["sku"] in seen_skus:
            continue
        motherboards.append(motherboard)
        seen_skus.add(motherboard["sku"])

    return sorted(motherboards, key=lambda item: (item["brand"], item["name"]))


def parse_kabum_product(product: dict[str, Any]) -> dict[str, Any] | None:
    name = _normalize_whitespace(product.get("name") or "")
    if not name:
        return None
    if _should_skip_product(name):
        return None

    socket = _parse_socket(name)
    memory_generation = _parse_memory_generation(name)
    cpu_brand = _parse_cpu_brand(name, socket)
    chipset = _parse_chipset(name)
    form_factor = _parse_form_factor(name)
    if cpu_brand is None and socket is None and chipset is None:
        return None
    sku = _resolve_sku(name, product, socket)
    if sku is None:
        return None

    return {
        "name": name,
        "sku": sku,
        "brand": _normalize_whitespace((product.get("manufacturer") or {}).get("name") or name.split()[0]),
        "cpu_brand": cpu_brand,
        "socket": socket,
        "chipset": chipset,
        "form_factor": form_factor,
        "memory_generation": memory_generation,
        "wifi": _has_token(name, "WI-FI", "WIFI"),
        "bluetooth": _has_token(name, "BLUETOOTH"),
        "compatibility": {
            "desktop": True,
            "cpu_brands": [cpu_brand] if cpu_brand is not None else [],
            "sockets": [socket] if socket is not None else [],
            "memory_generations": [memory_generation] if memory_generation is not None else [],
        },
    }


def render_motherboards_module(motherboards: list[dict[str, Any]]) -> str:
    return f"MOTHERBOARDS = {pformat(motherboards, sort_dicts=False, width=100)}\n"


def write_motherboards_module(
    motherboards: list[dict[str, Any]],
    *,
    output_path: Path = DEFAULT_OUTPUT_PATH,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_motherboards_module(motherboards), encoding="utf-8")


def build_motherboards(
    *,
    output_path: Path = DEFAULT_OUTPUT_PATH,
    page_limit: int | None = None,
) -> list[dict[str, Any]]:
    products = fetch_kabum_products(category_url=KABUM_CATEGORY_URL, page_limit=page_limit)
    motherboards = parse_kabum_products(products)
    write_motherboards_module(motherboards, output_path=output_path)
    return motherboards


def main() -> None:
    parser = argparse.ArgumentParser(description="Gera app/data/motherboards.py a partir do catalogo da KaBuM!.")
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help="Arquivo Python de saida. Padrao: app/data/motherboards.py",
    )
    parser.add_argument(
        "--page-limit",
        type=int,
        default=None,
        help="Limita a quantidade de paginas do catalogo da KaBuM!. Util para debug.",
    )
    args = parser.parse_args()

    motherboards = build_motherboards(output_path=args.output, page_limit=args.page_limit)
    print(f"Gerado {args.output} com {len(motherboards)} placa(s)-mae.")


def _normalize_whitespace(value: str) -> str:
    normalized = " ".join(value.replace("\xa0", " ").split()).strip()
    return _fix_mojibake(normalized)


def _extract_sku(name: str) -> str | None:
    match = re.search(r"-\s*([A-Z0-9][A-Z0-9\-/\. ]+)\s*$", name, re.IGNORECASE)
    if match is None:
        return None
    return match.group(1).upper().strip()


def _resolve_sku(name: str, product: dict[str, Any], socket: str | None) -> str | None:
    candidate = _extract_sku(name)
    if candidate is not None and not _is_invalid_sku(candidate, socket):
        return candidate

    code = product.get("code")
    if code is None:
        return candidate
    return str(code)


def _parse_socket(name: str) -> str | None:
    normalized = name.upper()
    for socket in KNOWN_SOCKETS:
        if socket in normalized:
            return socket.replace("LGA", "LGA ").replace("  ", " ").strip()
    for intel_socket in ("1851", "1700", "1200", "1155", "1151", "2066", "2011"):
        if re.search(rf"(?<!\d){intel_socket}(?!\d)", normalized):
            return f"LGA {intel_socket}"
    return None


def _parse_chipset(name: str) -> str | None:
    normalized = name.upper()
    for chipset in KNOWN_CHIPSETS:
        if chipset in normalized:
            return chipset
    match = re.search(r"\b((?:A|B|H|Q|X|Z|WRX|TRX)\d{2,4}[A-Z]?)\b", normalized)
    if match is None:
        return None
    token = match.group(1)
    if re.fullmatch(r"(?:A|B|H|Q|X|Z)\d{2,4}M", token):
        return token[:-1]
    return token


def _parse_form_factor(name: str) -> str | None:
    normalized = name.upper()
    if "MICRO ATX" in normalized or "MICRO-ATX" in normalized or "M-ATX" in normalized or "MATX" in normalized:
        return "Micro ATX"
    if "MINI ITX" in normalized or "MINI-ITX" in normalized:
        return "Mini ITX"
    if "E-ATX" in normalized or "EXTENDED ATX" in normalized:
        return "E-ATX"
    if re.search(r"\b(?:A|B|H|Q|X|Z)\d{2,4}M(?:\b|[-/])", normalized):
        return "Micro ATX"
    if re.search(r"\b(?:A|B|H|Q|X|Z)\d{2,4}I(?:\b|[-/])", normalized):
        return "Mini ITX"
    if re.search(r"(?<![A-Z])ATX(?![A-Z])", normalized):
        return "ATX"
    return None


def _parse_memory_generation(name: str) -> str | None:
    for generation in ("DDR5", "DDR4", "DDR3"):
        if generation in name.upper():
            return generation
    return None


def _parse_cpu_brand(name: str, socket: str | None) -> str | None:
    normalized = name.upper()
    if "AMD" in normalized or (socket is not None and socket.startswith(("AM", "TR", "STR"))):
        return "AMD"
    if "INTEL" in normalized or (socket is not None and socket.startswith("LGA")):
        return "Intel"
    return None


def _has_token(name: str, *tokens: str) -> bool:
    normalized = name.upper()
    return any(token in normalized for token in tokens)


def _is_invalid_sku(value: str, socket: str | None) -> bool:
    normalized = value.upper()
    if socket is not None and socket in normalized:
        return True
    if len(normalized) <= 4:
        return True
    if normalized in GENERIC_SKUS:
        return True
    return any(token in normalized for token in ("LGA", "DDR", "AMD", "INTEL"))


def _should_skip_product(name: str) -> bool:
    normalized = name.upper()
    return any(token in normalized for token in SKIP_NAME_TOKENS)


def _fix_mojibake(value: str) -> str:
    if not any(token in value for token in ("Ã", "Â", "¢", "Õ")):
        return value
    try:
        fixed = value.encode("latin-1").decode("utf-8")
    except UnicodeError:
        return value
    return fixed


if __name__ == "__main__":
    main()
