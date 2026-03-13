"""Translation manager for i18n support."""

import json
from pathlib import Path
from typing import Dict, Optional

from loguru import logger

DEFAULT_LANGUAGE = "en"
SUPPORTED_LANGUAGES = ["en", "zh"]

def detect_system_language() -> str:
    """Detect system language and map to supported set."""
    try:
        import locale
        loc = locale.getdefaultlocale()[0] or ""
    except Exception:
        loc = ""
    loc = (loc or "").lower()
    if loc.startswith("zh"):
        return "zh"
    return "en"


class Translator:
    """Translation manager."""

    def __init__(self, language: str = DEFAULT_LANGUAGE):
        """Initialize translator."""
        self.language = language if language in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE
        self.translations: Dict[str, Dict] = {}
        self._load_translations()

    def _load_translations(self) -> None:
        """Load translations from JSON files."""
        i18n_dir = Path(__file__).parent

        for lang in SUPPORTED_LANGUAGES:
            lang_file = i18n_dir / f"{lang}.json"
            if lang_file.exists():
                try:
                    with open(lang_file, 'r', encoding='utf-8') as f:
                        self.translations[lang] = json.load(f)
                except Exception as e:
                    logger.error(f"Failed to load translations for {lang}: {e}")
                    self.translations[lang] = {}
            else:
                logger.warning(f"Translation file not found for {lang}")
                self.translations[lang] = {}

    def translate(self, key: str, **kwargs) -> str:
        """Translate a key with optional placeholders."""
        # Split key into parts (e.g., "cli.onboard.ready" -> ["cli", "onboard", "ready"])
        parts = key.split('.')

        # Get translation for current language
        translation = self.translations.get(self.language, {})

        # Traverse nested dictionaries
        for part in parts:
            if isinstance(translation, dict):
                translation = translation.get(part, key)
            else:
                break

        # If not found in current language, try default language
        if translation == key and self.language != DEFAULT_LANGUAGE:
            translation = self.translations.get(DEFAULT_LANGUAGE, {})
            for part in parts:
                if isinstance(translation, dict):
                    translation = translation.get(part, key)
                else:
                    break

        # Format with kwargs if it's a string
        if isinstance(translation, str) and kwargs:
            try:
                translation = translation.format(**kwargs)
            except KeyError:
                logger.warning(f"Missing placeholders for translation: {key}")

        return translation

    def set_language(self, language: str) -> None:
        """Set the current language."""
        if language in SUPPORTED_LANGUAGES:
            self.language = language
        else:
            logger.warning(f"Unsupported language: {language}, using {DEFAULT_LANGUAGE}")
            self.language = DEFAULT_LANGUAGE

    def get_supported_languages(self) -> list:
        """Get list of supported languages."""
        return SUPPORTED_LANGUAGES


# Global translator instance
_translator: Optional[Translator] = None


def get_translator() -> Translator:
    """Get global translator instance."""
    global _translator
    if _translator is None:
        _translator = Translator()
    return _translator


def translate(key: str, **kwargs) -> str:
    """Shortcut for translator.translate()."""
    return get_translator().translate(key, **kwargs)


def set_language(language: str) -> None:
    """Shortcut for translator.set_language()."""
    get_translator().set_language(language)


def get_supported_languages() -> list:
    """Shortcut for translator.get_supported_languages()."""
    return get_translator().get_supported_languages()
