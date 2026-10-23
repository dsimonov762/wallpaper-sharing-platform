"""Operational commands. Usage: python -m catalog.cli ensure-indexes"""

import argparse
import asyncio
import sys

from catalog.config.settings import get_settings
from catalog.repository.database import create_mongo_database
from catalog.repository.indexes import ensure_indexes


async def _ensure_indexes() -> int:
    database = create_mongo_database(get_settings())
    try:
        names = await ensure_indexes(database)
    finally:
        await database.close()
    for name in names:
        print(f"index ok: {name}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="catalog.cli")
    parser.add_argument("command", choices=["ensure-indexes"])
    args = parser.parse_args(argv)
    if args.command == "ensure-indexes":
        return asyncio.run(_ensure_indexes())
    return 2


if __name__ == "__main__":
    sys.exit(main())
