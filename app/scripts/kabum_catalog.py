from __future__ import annotations

import json
import math
import re
from typing import Any

import httpx


DEFAULT_TIMEOUT = 30.0
DEFAULT_PAGE_SIZE = 100
DEFAULT_HEADERS = {"User-Agent": "bestchoicepc-backend/1.0 (+local build script)"}


def fetch_kabum_page_payload(
    *,
    category_url: str,
    page_number: int,
    page_size: int = DEFAULT_PAGE_SIZE,
    timeout: float = DEFAULT_TIMEOUT,
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    params = {"page_number": page_number, "page_size": page_size}

    if client is None:
        response = httpx.get(
            category_url,
            params=params,
            timeout=timeout,
            follow_redirects=True,
            headers=DEFAULT_HEADERS,
        )
    else:
        response = client.get(category_url, params=params)

    response.raise_for_status()

    match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', response.text, re.DOTALL)
    if match is None:
        raise ValueError("Nao foi possivel localizar o __NEXT_DATA__ da KaBuM! para a categoria informada.")

    payload = json.loads(match.group(1))
    return json.loads(payload["props"]["pageProps"]["data"])


def fetch_kabum_products(
    *,
    category_url: str,
    page_size: int = DEFAULT_PAGE_SIZE,
    page_limit: int | None = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> list[dict[str, Any]]:
    initial_payload = fetch_kabum_page_payload(
        category_url=category_url,
        page_number=1,
        page_size=page_size,
        timeout=timeout,
    )
    total_items = int(initial_payload["catalogServer"]["meta"]["totalItemsCount"])
    total_pages = max(1, math.ceil(total_items / page_size))

    if page_limit is not None:
        total_pages = min(total_pages, page_limit)

    products: list[dict[str, Any]] = list(initial_payload["catalogServer"].get("data") or [])
    with httpx.Client(
        timeout=timeout,
        follow_redirects=True,
        headers=DEFAULT_HEADERS,
    ) as client:
        for page_number in range(2, total_pages + 1):
            page_payload = fetch_kabum_page_payload(
                category_url=category_url,
                page_number=page_number,
                page_size=page_size,
                timeout=timeout,
                client=client,
            )
            products.extend(page_payload["catalogServer"].get("data") or [])

    return products
