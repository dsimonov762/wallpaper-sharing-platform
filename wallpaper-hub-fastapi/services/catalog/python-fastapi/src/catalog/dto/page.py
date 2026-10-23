"""Paged response envelope (README 5.2)."""

from catalog.dto.base import ApiModel


class Page[T](ApiModel):
    items: list[T]
    page: int
    size: int
    total_items: int
    total_pages: int
