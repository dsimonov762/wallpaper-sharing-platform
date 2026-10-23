"""Business logic for wallpapers. No HTTP and no MongoDB in here."""

from dataclasses import dataclass, field

from catalog.domain.exceptions import NotFoundException, PreconditionFailedException
from catalog.domain.models import CreateWallpaper, Wallpaper, WallpaperChanges, WallpaperStatus
from catalog.domain.ports import AuthorDirectory, PageRequest, WallpaperFilter, WallpaperStore
from catalog.util.clock import Clock, utc_now
from catalog.util.ids import IdFactory, new_wallpaper_id


@dataclass(slots=True)
class WallpaperService:
    store: WallpaperStore
    authors: AuthorDirectory
    clock: Clock = field(default=utc_now)
    new_id: IdFactory = field(default=new_wallpaper_id)

    async def create(self, command: CreateWallpaper) -> Wallpaper:
        author = await self.authors.get_author(command.author_id)
        now = self.clock()
        wallpaper = Wallpaper(
            id=self.new_id(),
            title=command.title,
            description=command.description,
            tags=list(command.tags),
            category=command.category,
            # README 4.1 step 6: stays PENDING_MEDIA until media.asset.processed arrives (C7).
            status=WallpaperStatus.PENDING_MEDIA,
            asset_id=command.asset_id,
            author=author,
            created_at=now,
            updated_at=now,
            version=1,
        )
        await self.store.insert(wallpaper)
        return wallpaper

    async def get(self, wallpaper_id: str) -> Wallpaper:
        wallpaper = await self.store.get(wallpaper_id)
        if wallpaper is None:
            raise NotFoundException("Wallpaper not found.")
        return wallpaper

    async def list(self, flt: WallpaperFilter, page: PageRequest) -> tuple[list[Wallpaper], int]:
        return await self.store.list(flt, page)

    async def update(
        self, wallpaper_id: str, changes: WallpaperChanges, expected_version: int | None
    ) -> Wallpaper:
        """expected_version None means If-Match: * (any version, but still race-safe)."""
        current = await self.get(wallpaper_id)
        if expected_version is not None and current.version != expected_version:
            raise PreconditionFailedException("The wallpaper was changed by someone else.")
        fields: dict[str, object] = {}
        if changes.title is not None:
            fields["title"] = changes.title
        if changes.description is not None:
            fields["description"] = changes.description
        if changes.tags is not None:
            fields["tags"] = list(changes.tags)
        if changes.category is not None:
            fields["category"] = changes.category.value
        updated = await self.store.update_if_version(
            wallpaper_id, current.version, fields, self.clock()
        )
        if updated is None:
            # Saved by someone else between our read and write: the atomic filter caught it.
            raise PreconditionFailedException("The wallpaper was changed by someone else.")
        return updated
