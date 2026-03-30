from pathlib import Path

from app.scripts.build_psus import (
    build_psus_from_table_htmls,
    parse_brand_options,
    parse_performance_table_html,
    render_psus_module,
)


SAMPLE_PAGE_HTML = """
<html>
  <body>
    <select class="parameters brand">
      <option value="0">All</option>
      <option value="108">1st Player</option>
      <option value="13">AcBel</option>
    </select>
  </body>
</html>
"""


SAMPLE_TABLE_HTML = """
<table class="table table-dark table-striped table-hover mytable sub headers1stLine">
  <tr>
    <th class="sm">Manufacturer</th>
    <th class="sm">Model</th>
    <th class="sm">Efficiency Rating</th>
    <th class="sm">Noise Rating</th>
    <th class="sm">Total Score</th>
  </tr>
  <tr>
    <td>1st Player</td>
    <td>NGDP 1000W (ATX v3.0)</td>
    <td>PLATINUM</td>
    <td>Standard++</td>
    <td>87.0974</td>
  </tr>
  <tr>
    <td>1st Player</td>
    <td>ACK 750W Gold</td>
    <td>GOLD</td>
    <td>Standard+</td>
    <td>82.5645</td>
  </tr>
</table>
"""


def test_parse_brand_options_returns_ids_from_performance_page() -> None:
    result = parse_brand_options(SAMPLE_PAGE_HTML)

    assert result == [
        ("108", "1st Player"),
        ("13", "AcBel"),
    ]


def test_parse_performance_table_html_returns_minimal_psu_payload() -> None:
    result = parse_performance_table_html(SAMPLE_TABLE_HTML)

    assert result == [
        {
            "name": "1st Player NGDP 1000W (ATX v3.0)",
            "sku": "1st-player-ngdp-1000w-atx-v3-0",
            "brand": "1st Player",
            "wattage_w": 1000,
            "form_factor": None,
            "atx_version": "ATX3.0",
            "efficiency_rating": "PLATINUM",
            "noise_rating": "Standard++",
            "benchmark": {
                "cybenetics_score": 87.0974,
            },
        },
        {
            "name": "1st Player ACK 750W Gold",
            "sku": "1st-player-ack-750w-gold",
            "brand": "1st Player",
            "wattage_w": 750,
            "form_factor": None,
            "atx_version": None,
            "efficiency_rating": "GOLD",
            "noise_rating": "Standard+",
            "benchmark": {
                "cybenetics_score": 82.5645,
            },
        },
    ]


def test_render_psus_module_generates_python_constant() -> None:
    psus = parse_performance_table_html(SAMPLE_TABLE_HTML)

    module_text = render_psus_module(psus)

    assert module_text.startswith("PSUS = [")
    assert '"cybenetics_score": 87.0974' not in module_text
    assert "'cybenetics_score': 87.0974" in module_text


def test_build_psus_from_table_htmls_writes_python_file() -> None:
    output_path = Path("tests/_tmp_psus_output.py")

    try:
        result = build_psus_from_table_htmls([SAMPLE_TABLE_HTML], output_path=output_path)

        assert len(result) == 2
        assert output_path.read_text(encoding="utf-8").startswith("PSUS = [")
    finally:
        if output_path.exists():
            output_path.unlink()
