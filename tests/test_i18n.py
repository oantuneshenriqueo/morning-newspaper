"""assets/i18n: every language file must match en.json key by key."""
import json
import re

import pytest

from conftest import SKILL

I18N = SKILL / "assets" / "i18n"
LANGS = sorted(p.stem for p in I18N.glob("*.json"))
EN = json.loads((I18N / "en.json").read_text(encoding="utf-8"))
LIST_SIZES = {"weekdays": 7, "weekdays_short": 7, "months_short": 12}


def load(lang):
    return json.loads((I18N / f"{lang}.json").read_text(encoding="utf-8"))


def placeholders(text):
    return sorted(set(re.findall(r"\{(\w+)\}", text)))


def test_english_and_the_shipped_languages_exist():
    assert {"en", "pt-BR", "es"} <= set(LANGS)


@pytest.mark.parametrize("lang", LANGS)
def test_same_keys_as_english(lang):
    data = load(lang)
    assert sorted(set(EN) - set(data)) == [], "keys missing"
    assert sorted(set(data) - set(EN)) == [], "keys that English does not have"


@pytest.mark.parametrize("lang", LANGS)
def test_same_placeholders_as_english(lang):
    data = load(lang)
    for key, value in EN.items():
        if isinstance(value, str) and not key.startswith("_"):
            assert placeholders(data[key]) == placeholders(value), key


@pytest.mark.parametrize("lang", LANGS)
def test_list_sizes_and_types(lang):
    data = load(lang)
    for key, size in LIST_SIZES.items():
        assert isinstance(data[key], list) and len(data[key]) == size, key
    for key, value in EN.items():
        assert type(data[key]) is type(value), key
        if isinstance(value, str) and not key.startswith("_"):
            assert data[key].strip(), f"{key} is empty"


@pytest.mark.parametrize("lang", LANGS)
def test_html_lang_matches_file_name(lang):
    assert load(lang)["html_lang"] == lang
