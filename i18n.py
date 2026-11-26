"""Translations: one JSON file per language in the "locales" folder."""
import json
from pathlib import Path

LOCALES = Path(__file__).resolve().parent / "locales"
FALLBACK = "en"


class Translator:
    """Files are read again at every language change, so edited texts show up without touching the code."""

    def __init__(self, language=FALLBACK, folder=LOCALES):
        self.folder = Path(folder)
        self.language = FALLBACK
        self.texts = {}
        self.set_language(language)

    def _read(self, code):
        try:
            data = json.loads((self.folder / f"{code}.json").read_text(encoding="utf-8-sig"))
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError) as error:
            print(f"Cannot read locale {code}: {error}")
            return {}

    def available(self):
        """Codes of the language files that can be read."""
        return [f.stem for f in sorted(self.folder.glob("*.json")) if self._read(f.stem)]

    def set_language(self, code):
        languages = self.available()
        if code not in languages:
            code = FALLBACK if FALLBACK in languages else (languages or [FALLBACK])[0]
        self.language = code
        # Missing texts fall back to English.
        self.texts = {**self._read(FALLBACK), **self._read(code)}

    def next_language(self):
        languages = self.available()
        if not languages:
            return self.language
        position = languages.index(self.language) if self.language in languages else -1
        return languages[(position + 1) % len(languages)]

    def has(self, key):
        return key in self.texts

    def __call__(self, key, /, **values):  # positional only: texts may use a {key} placeholder
        text = str(self.texts.get(key, key))
        try:
            return text.format(**values) if values else text
        except (KeyError, IndexError, ValueError):  # a wrong {placeholder} in the file
            return text
