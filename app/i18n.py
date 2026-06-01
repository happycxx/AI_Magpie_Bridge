"""Lightweight JSON-based i18n helper for the AI coder app."""

import json
import os
from copy import deepcopy


DEFAULT_LANGUAGE = "zh_CN"

BUILTIN_LANGUAGES = {
    "zh_CN": "简体中文",
    "en_US": "English",
}

BUILTIN_TRANSLATIONS = {
    "zh_CN": {
        "app.title": "🌉 AI 鹊桥",
    },
    "en_US": {
        "app.title": "🌉 AI Magpie Bridge",
    },
}

LANGUAGES = deepcopy(BUILTIN_LANGUAGES)
TRANSLATIONS = deepcopy(BUILTIN_TRANSLATIONS)

LOCALES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "locales")


def _flatten_translation_dict(data, prefix=""):
    """Flatten nested locale JSON into dot-key translations."""
    flattened = {}

    if not isinstance(data, dict):
        return flattened

    for key, value in data.items():
        if key == "__meta__":
            continue

        full_key = f"{prefix}.{key}" if prefix else str(key)

        if isinstance(value, str):
            flattened[full_key] = value
        elif isinstance(value, dict):
            flattened.update(_flatten_translation_dict(value, full_key))

    return flattened


def _load_external_translations():
    """
    Load translations from app/locales/*.json.

    Supported JSON formats:

    1. Flat:
    {
      "__meta__": {"name": "English"},
      "button.load": "📂 Load"
    }

    2. Nested:
    {
      "__meta__": {"name": "English"},
      "button": {
        "load": "📂 Load"
      }
    }
    """
    if not os.path.isdir(LOCALES_DIR):
        return

    for filename in sorted(os.listdir(LOCALES_DIR)):
        if not filename.lower().endswith(".json"):
            continue

        language = os.path.splitext(filename)[0]
        file_path = os.path.join(LOCALES_DIR, filename)

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                payload = json.load(f)
        except Exception as exc:
            print(f"[i18n] Failed to load locale file {file_path}: {exc}")
            continue

        if not isinstance(payload, dict):
            print(f"[i18n] Locale file ignored because root is not an object: {file_path}")
            continue

        meta = payload.get("__meta__", {})
        if isinstance(meta, dict):
            language_name = meta.get("name") or meta.get("native_name") or language
        else:
            language_name = language

        translations = _flatten_translation_dict(payload)
        if not translations:
            print(f"[i18n] Locale file has no valid string translations: {file_path}")
            continue

        LANGUAGES[language] = language_name
        TRANSLATIONS.setdefault(language, {})
        TRANSLATIONS[language].update(translations)
        print(f"[i18n] Loaded locale {language}: {file_path}")


def reload_external_translations():
    """Reload locale JSON files. Useful for development or future settings UI."""
    LANGUAGES.clear()
    LANGUAGES.update(deepcopy(BUILTIN_LANGUAGES))

    TRANSLATIONS.clear()
    TRANSLATIONS.update(deepcopy(BUILTIN_TRANSLATIONS))

    _load_external_translations()


def get_available_languages():
    """Return a copy of currently available languages."""
    return dict(LANGUAGES)


def normalize_language(language):
    return language if language in LANGUAGES else DEFAULT_LANGUAGE


def translate(key, language=DEFAULT_LANGUAGE, **kwargs):
    language = normalize_language(language)

    text = TRANSLATIONS.get(language, {}).get(key)
    if text is None and language != DEFAULT_LANGUAGE:
        text = TRANSLATIONS.get(DEFAULT_LANGUAGE, {}).get(key)
    if text is None:
        text = key

    if kwargs:
        try:
            return text.format(**kwargs)
        except Exception:
            return text

    return text


_load_external_translations()
