from pathlib import Path

from app.scripts.build_rams import (
    build_rams,
    parse_kabum_product,
    parse_kabum_products,
    render_rams_module,
)


SAMPLE_PRODUCT_SINGLE = {
    "name": "Memória RAM Kingston Fury Beast, 8GB, 3200MHz, DDR4, CL16, Preto - KF432C16BB/8",
    "manufacturer": {"name": "Kingston"},
}

SAMPLE_PRODUCT_KIT = {
    "name": "Memória RAM Corsair Vengeance RGB, 32GB (2x16GB), 6000MHz, DDR5, CL36, XMP, Branco - CMH32GX5M2D6000C36W",
    "manufacturer": {"name": "Corsair"},
}

SAMPLE_PRODUCT_NOTEBOOK = {
    "name": "Memória RAM para Notebook Kingston Fury Impact, 16GB, 5600MHz, DDR5, CL40, SODIMM - KF556S40IB-16",
    "manufacturer": {"name": "Kingston"},
}


def test_parse_kabum_product_maps_minimal_catalog_fields() -> None:
    result = parse_kabum_product(SAMPLE_PRODUCT_SINGLE)

    assert result == {
        "name": "Memória RAM Kingston Fury Beast, 8GB, 3200MHz, DDR4, CL16, Preto - KF432C16BB/8",
        "sku": "KF432C16BB/8",
        "brand": "Kingston",
        "generation": "DDR4",
        "form_factor": "UDIMM",
        "capacity_gb": 8,
        "module_count": 1,
        "capacity_per_module_gb": 8,
        "speed_mhz": 3200,
        "cl": 16,
        "rgb": False,
        "profile": "unknown",
        "device": "desktop",
        "compatibility": {
            "desktop": True,
            "notebook": False,
            "platforms": ["DDR4"],
        },
    }


def test_parse_kabum_product_supports_kits_and_notebook_modules() -> None:
    kit = parse_kabum_product(SAMPLE_PRODUCT_KIT)
    notebook = parse_kabum_product(SAMPLE_PRODUCT_NOTEBOOK)

    assert kit is not None
    assert kit["capacity_gb"] == 32
    assert kit["module_count"] == 2
    assert kit["capacity_per_module_gb"] == 16
    assert kit["rgb"] is True
    assert kit["profile"] == "XMP"

    assert notebook is not None
    assert notebook["form_factor"] == "SODIMM"
    assert notebook["device"] == "notebook"
    assert notebook["compatibility"]["notebook"] is True


def test_parse_kabum_products_deduplicates_by_sku() -> None:
    result = parse_kabum_products([SAMPLE_PRODUCT_SINGLE, SAMPLE_PRODUCT_SINGLE])

    assert len(result) == 1
    assert result[0]["sku"] == "KF432C16BB/8"


def test_render_rams_module_generates_python_constant() -> None:
    rams = parse_kabum_products([SAMPLE_PRODUCT_SINGLE])

    module_text = render_rams_module(rams)

    assert module_text.startswith("RAMS = [")
    assert "'generation': 'DDR4'" in module_text


def test_build_rams_writes_python_file(monkeypatch) -> None:
    output_path = Path("tests/_tmp_rams_output.py")

    monkeypatch.setattr(
        "app.scripts.build_rams.fetch_kabum_products",
        lambda category_url, page_limit=None: [SAMPLE_PRODUCT_SINGLE, SAMPLE_PRODUCT_KIT],
    )

    try:
        result = build_rams(output_path=output_path, page_limit=1)

        assert len(result) == 2
        assert output_path.read_text(encoding="utf-8").startswith("RAMS = [")
    finally:
        if output_path.exists():
            output_path.unlink()
