"""分页参数归一与响应组装。

原先在 api_jobs / api_admin_jobs / api_admin_audits 三处逐字重复。
"""

from __future__ import annotations

from math import ceil
from typing import Any

MAX_PAGE_SIZE = 100


def normalize(page: int, page_size: int) -> tuple[int, int]:
    return max(1, page), max(1, min(MAX_PAGE_SIZE, page_size))


def build(items: list[Any], page: int, page_size: int, total: int, **extra: Any) -> dict[str, Any]:
    return {
        "items": items,
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": max(1, ceil(total / page_size)),
        **extra,
    }
