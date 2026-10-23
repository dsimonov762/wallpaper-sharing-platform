"""The paged-list envelope: { items, page, size, totalItems, totalPages }."""

from account.dto.base import ApiModel


class Page[T](ApiModel):
    items: list[T]
    page: int
    size: int
    total_items: int
    total_pages: int
