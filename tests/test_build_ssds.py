from pathlib import Path

from app.scripts.build_ssds import build_ssds, parse_top_ssd_html, render_ssds_module


SAMPLE_HTML = """
<html>
  <body>
    <table>
      <tr>
        <th>Score</th>
        <th>Product name</th>
        <th>Image</th>
        <th>Capacity</th>
        <th>NAND</th>
        <th>DRAM</th>
        <th>TBW</th>
        <th>Warranty</th>
        <th>Controller</th>
        <th>Interface</th>
      </tr>
      <tr>
        <td>13183</td>
        <td><a href="western_digital_wd_black_sn8100_2tb.html">Western Digital WD_BLACK SN8100 2TB</a></td>
        <td><img alt="WDS200T1X0M-00CMT0" src="a.jpg"></td>
        <td>2048 GB</td>
        <td>TLC</td>
        <td>&#10003; Yes</td>
        <td>1200 TB</td>
        <td>5 Years</td>
        <td>SanDisk A101-250800-AC</td>
        <td>PCIe 5.0 x4</td>
      </tr>
      <tr>
        <td>12554</td>
        <td><a href="samsung_9100_pro_1tb.html">Samsung 9100 PRO 1TB</a></td>
        <td><img alt="MZ-VAP1T0BW" src="b.jpg"></td>
        <td>1 TB</td>
        <td>TLC</td>
        <td>&#10003; Yes</td>
        <td>600 TB</td>
        <td>5 Years</td>
        <td>Samsung Presto</td>
        <td>PCIe 5.0 x4</td>
      </tr>
    </table>
  </body>
</html>
"""


def test_parse_top_ssd_html_returns_minimal_ssd_payload() -> None:
    result = parse_top_ssd_html(SAMPLE_HTML)

    assert result == [
        {
            "name": "Western Digital WD_BLACK SN8100 2TB",
            "sku": "WDS200T1X0M-00CMT0",
            "brand": "Western Digital",
            "capacity_gb": 2048,
            "interface": "PCIe 5.0 x4",
            "nand": "TLC",
            "dram": True,
            "benchmark": {
                "ssd_tester_score": 13183,
            },
            "source_url": "https://ssd-tester.com/western_digital_wd_black_sn8100_2tb.html",
        },
        {
            "name": "Samsung 9100 PRO 1TB",
            "sku": "MZ-VAP1T0BW",
            "brand": "Samsung",
            "capacity_gb": 1024,
            "interface": "PCIe 5.0 x4",
            "nand": "TLC",
            "dram": True,
            "benchmark": {
                "ssd_tester_score": 12554,
            },
            "source_url": "https://ssd-tester.com/samsung_9100_pro_1tb.html",
        },
    ]


def test_render_ssds_module_generates_python_constant() -> None:
    ssds = parse_top_ssd_html(SAMPLE_HTML)

    module_text = render_ssds_module(ssds)

    assert module_text.startswith("SSDS = [")
    assert '"ssd_tester_score": 13183' not in module_text
    assert "'ssd_tester_score': 13183" in module_text


def test_build_ssds_writes_python_file() -> None:
    output_path = Path("tests/_tmp_ssds_output.py")

    try:
        result = build_ssds(html=SAMPLE_HTML, output_path=output_path)

        assert len(result) == 2
        assert output_path.read_text(encoding="utf-8").startswith("SSDS = [")
    finally:
        if output_path.exists():
            output_path.unlink()
