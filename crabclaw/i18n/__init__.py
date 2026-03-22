"""Internationalization (i18n) module."""

from crabclaw.i18n.translator import (
    translate,
    set_language,
    get_translator,
    get_supported_languages,
    detect_system_language,
)

__all__ = [
    "translate",
    "set_language",
    "get_translator",
    "get_supported_languages",
    "detect_system_language",
]
