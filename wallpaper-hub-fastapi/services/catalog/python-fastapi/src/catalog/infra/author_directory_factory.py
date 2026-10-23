"""Chooses the AuthorDirectory from settings (same idea as account's identity factory)."""

from catalog.config.settings import Settings
from catalog.domain.ports import AuthorDirectory
from catalog.infra.local_author_directory import LocalAuthorDirectory


def create_author_directory(settings: Settings) -> AuthorDirectory:
    # Step C5 adds: if settings.author_directory == "grpc": return GrpcAuthorDirectory(...)
    _ = settings.author_directory
    return LocalAuthorDirectory()
