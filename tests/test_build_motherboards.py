from pathlib import Path

from app.scripts.build_motherboards import (
    build_motherboards,
    parse_kabum_product,
    parse_kabum_products,
    render_motherboards_module,
)


SAMPLE_PRODUCT_AMD = {
    "name": "Placa-Mãe ASUS TUF Gaming B650M-E, WIFI, AMD AM5, B650, DDR5, Preto - 90MB1FV0-M0EAY0",
    "manufacturer": {"name": "ASUS"},
    "code": 12345,
}

SAMPLE_PRODUCT_INTEL = {
    "name": "Placa-Mãe MSI PRO B760M-P, Intel LGA 1700, mATX, DDR4, Preto - PRO B760M-P DDR4",
    "manufacturer": {"name": "MSI"},
    "code": 67890,
}

SAMPLE_PRODUCT_WIFI_BT = {
    "name": "Placa Mãe Gigabyte B550M DS3H AC R2, AMD AM4, Micro ATX, DDR4, RGB, Wi-Fi, Bluetooth, Preto - B550M DS3H AC R2",
    "manufacturer": {"name": "Gigabyte"},
    "code": 98765,
}

SAMPLE_PRODUCT_INTEL_NUMERIC_SOCKET = {
    "name": "Placa Mae Asrock H810m-h LGA 1851",
    "manufacturer": {"name": "ASRock"},
    "code": 1015437,
}

SAMPLE_PRODUCT_NOTEBOOK = {
    "name": "Placa Mãe Para Notebook Lenovo Thinkpad T440s Nm-a052",
    "manufacturer": {"name": "Lenovo"},
    "code": 112233,
}


def test_parse_kabum_product_maps_minimal_catalog_fields() -> None:
    result = parse_kabum_product(SAMPLE_PRODUCT_AMD)

    assert result == {
        "name": "Placa-Mãe ASUS TUF Gaming B650M-E, WIFI, AMD AM5, B650, DDR5, Preto - 90MB1FV0-M0EAY0",
        "sku": "90MB1FV0-M0EAY0",
        "brand": "ASUS",
        "cpu_brand": "AMD",
        "socket": "AM5",
        "chipset": "B650",
        "form_factor": "Micro ATX",
        "memory_generation": "DDR5",
        "wifi": True,
        "bluetooth": False,
        "compatibility": {
            "desktop": True,
            "cpu_brands": ["AMD"],
            "sockets": ["AM5"],
            "memory_generations": ["DDR5"],
        },
    }


def test_parse_kabum_product_supports_intel_and_connectivity() -> None:
    intel = parse_kabum_product(SAMPLE_PRODUCT_INTEL)
    wifi_bt = parse_kabum_product(SAMPLE_PRODUCT_WIFI_BT)

    assert intel is not None
    assert intel["cpu_brand"] == "Intel"
    assert intel["socket"] == "LGA 1700"
    assert intel["chipset"] == "B760"
    assert intel["form_factor"] == "Micro ATX"
    assert intel["memory_generation"] == "DDR4"

    assert wifi_bt is not None
    assert wifi_bt["wifi"] is True
    assert wifi_bt["bluetooth"] is True
    assert wifi_bt["form_factor"] == "Micro ATX"


def test_parse_kabum_product_uses_code_when_sku_in_name_is_unreliable() -> None:
    result = parse_kabum_product(SAMPLE_PRODUCT_INTEL_NUMERIC_SOCKET)

    assert result is not None
    assert result["sku"] == "1015437"
    assert result["socket"] == "LGA 1851"
    assert result["cpu_brand"] == "Intel"


def test_parse_kabum_product_skips_notebook_and_oem_like_items() -> None:
    result = parse_kabum_product(SAMPLE_PRODUCT_NOTEBOOK)

    assert result is None


def test_parse_kabum_products_deduplicates_by_sku() -> None:
    result = parse_kabum_products([SAMPLE_PRODUCT_AMD, SAMPLE_PRODUCT_AMD])

    assert len(result) == 1
    assert result[0]["sku"] == "90MB1FV0-M0EAY0"


def test_render_motherboards_module_generates_python_constant() -> None:
    motherboards = parse_kabum_products([SAMPLE_PRODUCT_AMD])

    module_text = render_motherboards_module(motherboards)

    assert module_text.startswith("MOTHERBOARDS = [")
    assert "'socket': 'AM5'" in module_text


def test_build_motherboards_writes_python_file(monkeypatch) -> None:
    output_path = Path("tests/_tmp_motherboards_output.py")

    monkeypatch.setattr(
        "app.scripts.build_motherboards.fetch_kabum_products",
        lambda category_url, page_limit=None: [SAMPLE_PRODUCT_AMD, SAMPLE_PRODUCT_INTEL],
    )

    try:
        result = build_motherboards(output_path=output_path, page_limit=1)

        assert len(result) == 2
        assert output_path.read_text(encoding="utf-8").startswith("MOTHERBOARDS = [")
    finally:
        if output_path.exists():
            output_path.unlink()
