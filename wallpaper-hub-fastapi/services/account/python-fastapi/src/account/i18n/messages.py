"""Message bundles shared by all services: `contracts/i18n/{en,de,es}.json` (README section 5.2).

Each file maps a stable key to a text with `{placeholders}`. Code passes a key and arguments;
this module turns them into text in the caller's language.
"""

import json
import logging
import os
from collections.abc import Mapping
from functools import lru_cache
from pathlib import Path
from typing import Any

from account.i18n.negotiation import DEFAULT_LOCALE, SUPPORTED_LOCALES

logger = logging.getLogger(__name__)

I18N_DIR_ENV = "ACCOUNT_I18N_DIR"


class _KeepUnknown(dict[str, Any]):
    """For `str.format_map`: a placeholder without a value stays visible as `{name}`."""

    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def find_bundle_dir() -> Path:
    """Where the JSON files live: `ACCOUNT_I18N_DIR`, else `contracts/i18n` above this file."""
    configured = os.environ.get(I18N_DIR_ENV)
    if configured:
        return Path(configured)
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "contracts" / "i18n"
        if candidate.is_dir():
            return candidate
    msg = (
        "Cannot find contracts/i18n. "
        f"Set {I18N_DIR_ENV} to the folder that holds en.json, de.json and es.json."
    )
    raise FileNotFoundError(msg)


class MessageBundles:
    def __init__(self, bundles: Mapping[str, Mapping[str, str]]) -> None:
        self._bundles = bundles

    @classmethod
    def load(cls, directory: Path) -> "MessageBundles":
        """Read every supported language; a missing or broken file is a startup error."""
        bundles: dict[str, dict[str, str]] = {}
        for locale in SUPPORTED_LOCALES:
            with (directory / f"{locale}.json").open(encoding="utf-8") as handle:
                bundles[locale] = json.load(handle)
        return cls(bundles)

    def keys(self, locale: str) -> set[str]:
        return set(self._bundles[locale])

    def translate(self, key: str, locale: str, args: Mapping[str, Any] | None = None) -> str:
        """Text for `key` in `locale`; falls back to English, then to the key itself."""
        template = self._bundles.get(locale, {}).get(key)
        if template is None:
            template = self._bundles[DEFAULT_LOCALE].get(key)
        if template is None:
            logger.warning("Missing i18n key %s", key)
            return key
        return template.format_map(_KeepUnknown(args or {}))


@lru_cache(maxsize=1)
def get_bundles() -> MessageBundles:
    """Load once per process (the files do not change while the service runs)."""
    return MessageBundles.load(find_bundle_dir())


def translate(key: str, locale: str, **args: Any) -> str:
    return get_bundles().translate(key, locale, args)
