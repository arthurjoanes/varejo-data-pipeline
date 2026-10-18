import json
import re

from retail_pipeline.report_model import ReportPayload
from retail_pipeline.report_view import _sales_explorer


def test_explorer_embeds_exact_integer_strings_and_cannot_close_its_json_script() -> None:
    payload = ReportPayload(
        snapshot={"publication_id": "published"},
        stores=[
            {
                "business_date": "2026-01-01",
                "store_id": "</script><img src=x>",
                "net_revenue_brl": "90071992547409.93",
                "sales_count": 9007199254740993,
                "units": None,
            }
        ],
    )
    html = _sales_explorer(payload)
    match = re.search(r'id="sales-slice-data">(.*?)</script>', html)
    assert match is not None
    data = json.loads(match[1])
    assert data[0]["sales_count"] == "9007199254740993"
    assert data[0]["net_revenue_brl"] == "90071992547409.93"
    assert data[0]["units"] is None
    assert "<img" not in match[1]


def test_explorer_blocks_truncated_or_unpublished_rows_and_invalid_dates() -> None:
    row = {"business_date": "2026-01-01", "store_id": "S01"}
    assert "Ainda não há publicação" in _sales_explorer(ReportPayload(stores=[row]))
    assert "truncadas" in _sales_explorer(
        ReportPayload(snapshot={"publication_id": "p"}, stores=[row], stores_truncated=True)
    )
    assert "Datas incompletas" in _sales_explorer(
        ReportPayload(snapshot={"publication_id": "p"}, stores=[{**row, "business_date": None}])
    )
