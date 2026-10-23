"""Wallpaper endpoints. Authentication and ownership rules arrive in step C2."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, Path, Query, Response

from catalog.api.http.dependencies import WallpaperServiceDep
from catalog.api.http.etag import make_etag, parse_if_match
from catalog.api.http.pagination import WALLPAPER_SORT_FIELDS, page_params, total_pages
from catalog.domain.models import Category, WallpaperStatus
from catalog.domain.ports import PageRequest, WallpaperFilter
from catalog.dto.page import Page
from catalog.dto.problem import ProblemDetails
from catalog.dto.wallpaper import CreateWallpaperRequest, UpdateWallpaperRequest, WallpaperResponse
from catalog.mapper.wallpaper_mapper import to_changes, to_create_command, to_response

router = APIRouter(prefix="/wallpapers", tags=["wallpapers"])

PROBLEM: dict[str, Any] = {
    "model": ProblemDetails,
    "content": {"application/problem+json": {}},
}
WallpaperId = Annotated[str, Path(pattern=r"^wp_[0-9A-Za-z]{10,40}$")]
PageDep = Annotated[PageRequest, Depends(page_params(WALLPAPER_SORT_FIELDS))]


@router.post(
    "",
    status_code=201,
    responses={400: PROBLEM},
)
async def create_wallpaper(
    body: CreateWallpaperRequest, response: Response, service: WallpaperServiceDep
) -> WallpaperResponse:
    wallpaper = await service.create(to_create_command(body))
    response.headers["Location"] = f"/api/v1/wallpapers/{wallpaper.id}"
    response.headers["ETag"] = make_etag(wallpaper.version)
    return to_response(wallpaper)


@router.get("", responses={400: PROBLEM})
async def list_wallpapers(
    service: WallpaperServiceDep,
    page: PageDep,
    status: Annotated[WallpaperStatus | None, Query()] = None,
    category: Annotated[Category | None, Query()] = None,
    tag: Annotated[str | None, Query(min_length=1, max_length=30)] = None,
    author_id: Annotated[str | None, Query(alias="authorId", min_length=1, max_length=64)] = None,
) -> Page[WallpaperResponse]:
    flt = WallpaperFilter(
        status=status,
        category=category,
        tag=None if tag is None else tag.strip().lower(),
        author_id=author_id,
    )
    items, total = await service.list(flt, page)
    return Page[WallpaperResponse](
        items=[to_response(w) for w in items],
        page=page.page,
        size=page.size,
        total_items=total,
        total_pages=total_pages(total, page.size),
    )


@router.get("/{wallpaper_id}", responses={400: PROBLEM, 404: PROBLEM})
async def get_wallpaper(
    wallpaper_id: WallpaperId, response: Response, service: WallpaperServiceDep
) -> WallpaperResponse:
    wallpaper = await service.get(wallpaper_id)
    response.headers["ETag"] = make_etag(wallpaper.version)
    return to_response(wallpaper)


@router.patch(
    "/{wallpaper_id}",
    responses={400: PROBLEM, 404: PROBLEM, 412: PROBLEM, 428: PROBLEM},
)
async def patch_wallpaper(
    wallpaper_id: WallpaperId,
    body: UpdateWallpaperRequest,
    response: Response,
    service: WallpaperServiceDep,
    if_match: Annotated[str | None, Header()] = None,
) -> WallpaperResponse:
    # Body validation (400) already ran before this line, so it wins over the If-Match checks.
    expected = parse_if_match(if_match)
    wallpaper = await service.update(wallpaper_id, to_changes(body), expected)
    response.headers["ETag"] = make_etag(wallpaper.version)
    return to_response(wallpaper)
