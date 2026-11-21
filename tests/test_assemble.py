"""scripts/assemble.py: builds the edition HTML and the newsstand index from edition.json."""
import hashlib
import html
import json
import re
import subprocess
import sys

import pytest

from conftest import SCRIPTS


def link_id(url):
    return hashlib.sha1(url.encode("utf-8")).hexdigest()[:12]


def ok(proc):
    assert proc.returncode == 0, proc.stdout + proc.stderr
    return proc


def refused(proc):
    """The script must refuse cleanly: exit 1, an ERROR line, no traceback, nothing written."""
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "ERROR:" in proc.stdout
    assert "Traceback" not in proc.stderr
    assert not proc.archive.exists()
    return proc


# ---------------------------------------------------------------- happy path

def test_new_newsstand_builds_every_file(assembler):
    proc = ok(assembler.run())
    files = {p.relative_to(proc.archive).as_posix() for p in proc.archive.rglob("*") if p.is_file()}
    assert files == {"index.html", "config.json", "editions/index.json", "editions/2026-11-13.html"}
    assert "NEW NEWSSTAND" in proc.stdout
    for name in files:
        assert f"  {name} -> " in proc.stdout, f"{name} missing from the PUBLISH list"


def test_page_has_no_template_leftovers(assembler):
    ok(assembler.run())
    page = assembler.page()
    assert not re.search(r"\{\{\{?\w+\}\}", page)  # CSS legitimately contains "}}"
    assert not re.search(r"<!--/?(IF|EACH):", page)


def test_page_language_title_and_content(assembler):
    ok(assembler.run())
    page = assembler.page()
    assert '<html lang="en">' in page
    assert "<title>Morning Newspaper · Nov. 13, 2026</title>" in page
    assert "Browser patches a flaw already under attack" in page
    assert "Friday, Nov. 13, 2026" in page


def test_refs_are_resolved_to_collected_links(assembler):
    ok(assembler.run())
    page = assembler.page()
    for url, outlet in [("https://tech.example.com/a1", "Example Tech"),
                        ("https://ai.example.com/a2", "Example AI"),
                        ("https://local.example.com/b1", "Springfield Daily"),
                        ("https://money.example.com/c1", "Example Money"),
                        ("https://games.example.com/d1", "Example Games"),
                        ("https://en.wikipedia.org/wiki/World_Wide_Web", None)]:
        assert f'href="{url}"' in page
        if outlet:
            assert outlet in page


def test_every_link_is_https(assembler):
    ok(assembler.run())
    for href in re.findall(r'href="([^"]*)"', assembler.page()):
        assert href.startswith("https://") or href == "../index.html", href


def test_index_entry(assembler):
    ok(assembler.run())
    idx = assembler.new_index()
    assert idx["newspaper"] == "Morning Newspaper"
    assert idx["founded"] == "2026-11-13"
    (entry,) = idx["editions"]
    assert entry["date"] == "2026-11-13"
    assert entry["number"] == 1
    assert entry["type"] == "morning"
    assert entry["file"] == "editions/2026-11-13.html"
    assert entry["headline"] == "Browser patches a flaw already under attack"
    assert "links" not in entry  # fingerprints only: Google News links are long
    assert link_id("https://tech.example.com/a1") in entry["link_ids"]
    assert len(entry["titles"]) == 4


def test_portuguese_labels_and_default_name(assembler):
    assembler.config["language"] = "pt-BR"
    del assembler.config["newspaper"]["name"]
    ok(assembler.run())
    page = assembler.page()
    assert '<html lang="pt-BR">' in page
    assert "O Jornal Matinal" in page


# ---------------------------------------------------------------- special modes

def test_sample_edition(assembler):
    proc = ok(assembler.run("--sample"))
    assert not (proc.archive / "config.json").exists()
    assert "config.json" not in proc.stdout
    assert assembler.new_index()["editions"][0]["type"] == "sample"
    assert "This newspaper has not been set up yet" in assembler.page()


def test_existing_newsstand_publishes_the_edition_and_the_page(assembler):
    old = {"newspaper": "Morning Newspaper", "founded": "2026-11-10",
           "editions": [{"date": "2026-11-12", "number": 3, "headline": "Old", "links": []}]}
    proc = ok(assembler.run(index=old))
    # The publishing tool needs the main page in every publish: it is always listed, first.
    listed = re.findall(r"^  (\S+) -> ", proc.stdout, flags=re.M)
    assert listed == ["index.html", "editions/2026-11-13.html", "editions/index.json"]
    assert not (proc.archive / "config.json").exists()
    idx = assembler.new_index()
    assert [e["number"] for e in idx["editions"]] == [4, 3]
    assert idx["founded"] == "2026-11-10"


def test_with_config_adds_config_to_existing_newsstand(assembler):
    old = {"founded": "2026-11-10", "editions": [{"date": "2026-11-12", "number": 1}]}
    proc = ok(assembler.run("--with-config", index=old))
    assert (proc.archive / "config.json").exists()


def test_reissue_keeps_number_and_does_not_duplicate(assembler):
    old = {"founded": "2026-11-10", "editions": [{"date": "2026-11-13", "number": 2},
                                                 {"date": "2026-11-12", "number": 1}]}
    proc = ok(assembler.run(index=old))
    assert "REISSUE" in proc.stdout
    idx = assembler.new_index()
    assert [e["date"] for e in idx["editions"]] == ["2026-11-13", "2026-11-12"]
    assert idx["editions"][0]["number"] == 2


def test_dedup_data_kept_only_for_last_14_editions(assembler):
    old = {"founded": "2026-10-01", "editions": [
        {"date": f"2026-10-{d:02d}", "number": d, "titles": ["t"], "links": ["https://x.example/"]}
        for d in range(1, 21)]}
    ok(assembler.run(index=old))
    eds = assembler.new_index()["editions"]
    assert len(eds) == 21
    assert all("titles" in e for e in eds[:14])
    assert not any("titles" in e or "links" in e or "source_titles" in e for e in eds[14:])


def test_index_keeps_the_collected_titles(assembler, collected):
    """Collection compares new stories with the titles as collected, not the rewritten ones."""
    ok(assembler.run())
    entry = assembler.new_index()["editions"][0]
    assert entry["source_titles"][0] == collected["news"]["tech"][0]["title"]
    assert len(entry["source_titles"]) == 5


# ---------------------------------------------------------------- legacy newsstands

LEGACY_INDEX = {"jornal": "Folha Antiga", "fundado_em": "2026-11-01", "edicoes": [
    {"data": "2026-11-12", "numero": 7, "dia_semana": "quinta-feira", "tipo": "fim de semana",
     "manchete": "Manchete antiga", "resumo": "agenda livre", "arquivo": "edicoes/2026-11-12.html",
     "titulos": ["Um", "Dois"], "links": ["https://old.example/1"],
     "extras": {"historia": "Em 1990...", "voce_sabia": "O mouse..."}}]}


def test_legacy_newsstand_is_migrated(assembler):
    proc = ok(assembler.run(index=LEGACY_INDEX))
    assert "LEGACY NEWSSTAND MIGRATED" in proc.stdout
    assert "edicoes/indice.json" in proc.stdout
    for name in ("index.html", "config.json", "editions/index.json", "editions/2026-11-13.html"):
        assert (proc.archive / name).exists(), name
        assert f"  {name} -> " in proc.stdout, f"{name} missing from the PUBLISH list"
    idx = assembler.new_index()
    assert idx["founded"] == "2026-11-01"
    assert not {"edicoes", "fundado_em", "jornal"} & set(idx)
    new, old = idx["editions"]
    assert new["number"] == 8
    assert old == {"date": "2026-11-12", "number": 7, "weekday": "quinta-feira", "type": "weekend",
                   "headline": "Manchete antiga", "summary": "agenda livre", "file": "edicoes/2026-11-12.html",
                   "titles": ["Um", "Dois"], "link_ids": [link_id("https://old.example/1")],
                   "extras": {"history": "Em 1990...", "did_you_know": "O mouse..."}}


def test_legacy_sample_edition_never_publishes_config(assembler):
    proc = ok(assembler.run("--sample", index=LEGACY_INDEX))
    assert (proc.archive / "index.html").exists()
    assert not (proc.archive / "config.json").exists()


def test_mixed_keys_are_normalized_without_a_migration(assembler):
    mixed = {"founded": "2026-11-01", "editions": [
        {"date": "2026-11-12", "number": 2, "headline": "New keys"},
        {"data": "2026-11-11", "numero": 1, "manchete": "Old keys", "arquivo": "edicoes/2026-11-11.html"}]}
    proc = ok(assembler.run(index=mixed))
    assert "LEGACY" not in proc.stdout
    eds = assembler.new_index()["editions"]
    assert [e["number"] for e in eds] == [3, 2, 1]
    assert eds[2]["headline"] == "Old keys" and eds[2]["file"] == "edicoes/2026-11-11.html"
    legacy_keys = {"data", "numero", "manchete", "arquivo", "titulos", "resumo", "tipo", "dia_semana"}
    assert not any(legacy_keys & set(e) for e in eds)


def test_with_page_is_still_accepted(assembler):
    old = {"founded": "2026-11-10", "editions": [{"date": "2026-11-12", "number": 1}]}
    proc = ok(assembler.run("--with-page", index=old))
    assert (proc.archive / "index.html").exists()
    assert "  index.html -> " in proc.stdout
    assert not (proc.archive / "config.json").exists()


def test_missing_connectors_keep_the_boxes_with_a_notice(assembler):
    del assembler.edition["agenda"]
    del assembler.edition["classifieds"]
    ok(assembler.run())
    page = assembler.page()
    assert 'class="quadro agenda"' in page and 'class="classif"' in page
    assert "Google Calendar is not connected" in page and "Gmail is not connected" in page
    assert "Free agenda today" not in page and "Inbox under control" not in page


def test_share_copy_hides_the_boxes_it_left_out(assembler):
    del assembler.edition["agenda"]
    del assembler.edition["classifieds"]
    ok(assembler.run("--share"))
    page = standalone_page(assembler)
    assert 'class="quadro agenda"' not in page and 'class="classif"' not in page
    assert "not connected" not in page


def test_connected_agenda_has_no_notice(assembler):
    ok(assembler.run())
    assert "not connected" not in assembler.page()


def test_empty_agenda_prints_free_day(assembler):
    assembler.edition["agenda"] = []
    ok(assembler.run())
    assert "Free agenda today" in assembler.page()


def test_long_title_is_only_a_warning(assembler):
    assembler.edition["sections"]["tech"][0]["title"] = " ".join(["word"] * 13)
    proc = ok(assembler.run())
    assert "WARNING:" in proc.stdout


# ---------------------------------------------------------------- refusals

LONG = "one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen"


def _set(path, value):
    def apply(ed):
        target = ed
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = value
    return apply


REFUSALS = {
    "quote with 15+ words": _set(["sections", "tech", 0, "text"], f'He said "{LONG}" today.'),
    "unknown ref": _set(["sections", "tech", 0, "ref"], "z9"),
    "ref used twice": _set(["sections", "tech", 0, "ref"], "a1"),
    "link not https": lambda ed: ed["sections"]["tech"][0].update(ref=None, url="http://x.example/", outlet="X"),
    "missing outlet": lambda ed: ed["sections"]["tech"][0].update(ref=None, url="https://x.example/"),
    "missing deck": _set(["headline", "deck"], ""),
    "missing headline": lambda ed: ed.pop("headline"),
    "unknown section": _set(["sections", "sports"], [{"ref": "a3", "title": "t", "text": "x"}]),
    "classified link outside Gmail": _set(["classifieds", 0, "url"], "https://example.com/mail"),
    "classified with an amount": _set(["classifieds", 0, "text"], "Invoice of R$ 50 is due."),
    "classified with a long code": _set(["classifieds", 0, "text"], "Your code is 123456."),
}


@pytest.mark.parametrize("case", sorted(REFUSALS))
def test_refuses_bad_edition(assembler, case):
    REFUSALS[case](assembler.edition)
    refused(assembler.run())


def test_refuses_more_stories_than_the_maximum(assembler):
    assembler.config["total_news"]["max"] = 3
    refused(assembler.run())


# ---------------------------------------------------------------- known bugs (remove the mark once fixed)
# xfail_strict is on: when a bug is fixed, its test starts passing and the suite fails until
# the @pytest.mark.xfail line is removed.

def test_classified_may_mention_a_year(assembler):
    assembler.edition["classifieds"][0]["text"] = "Ana asked about the 2026 plan."
    ok(assembler.run())


def test_refuses_long_quote_in_single_quotes(assembler):
    assembler.edition["sections"]["tech"][0]["text"] = f"He said ‘{LONG}’ today."
    refused(assembler.run())


def test_story_about_templates_is_accepted(assembler):
    assembler.edition["sections"]["tech"][0]["text"] = "Jinja uses {{ name }} for variables."
    ok(assembler.run())
    assert "{{ name }}" in html.unescape(assembler.page())


def test_template_markers_in_text_stay_literal(assembler):
    assembler.edition["agenda"][0]["event"] = "Write about {{MOTTO}}"
    ok(assembler.run())
    assert "Write about {{MOTTO}}" in html.unescape(assembler.page())


# ---------------------------------------------------------------- copies outside the newsstand (v1.3)

def standalone_page(assembler, date="2026-11-13"):
    return (assembler.tmp / "work" / "standalone" / f"{date}.html").read_text(encoding="utf-8")


@pytest.mark.parametrize("flag", ["--standalone", "--share"])
def test_copy_outside_the_newsstand(assembler, flag):
    old = {"founded": "2026-11-10", "editions": [{"date": "2026-11-13", "number": 4, "headline": "Morning"}]}
    proc = ok(assembler.run(flag, index=old))
    assert "NOT FOR THE NEWSSTAND" in proc.stdout and "PUBLISH" not in proc.stdout
    assert not proc.archive.exists()          # no index that could replace the morning entry
    page = standalone_page(assembler)
    assert "../index.html" not in page        # no button to a newsstand that is not there
    assert "No. 004" in page or "004" in page  # the reissue keeps the number


def test_share_copy_says_what_was_left_out(assembler):
    del assembler.edition["agenda"]
    del assembler.edition["classifieds"]
    ok(assembler.run("--share"))
    page = standalone_page(assembler)
    assert html.escape("Copy to share: the reader's agenda and emails are left out.") in page
    assert "Copy to share" in re.search(r'class="faixa sc">(.*?)<', page).group(1)


def test_share_copy_with_the_agenda_only_mentions_the_emails(assembler):
    del assembler.edition["classifieds"]
    ok(assembler.run("--share"))
    assert html.escape("Copy to share: the reader's emails are left out.") in standalone_page(assembler)


def test_normal_edition_has_no_share_note(assembler):
    ok(assembler.run())
    page = assembler.page()
    assert "aviso-copia\">" not in page and "../index.html" in page


# ---------------------------------------------------------------- footer, title, headline source

def test_footer_editor(assembler):
    ok(assembler.run())
    assert "Reporting, editing and layout: Claude" in assembler.page()
    assembler.config["newspaper"]["editor"] = "Another Assistant"
    ok(assembler.run())
    assert "layout: Another Assistant" in assembler.page()
    assembler.config["newspaper"]["editor"] = ""
    ok(assembler.run())
    assert "Reporting, editing" not in assembler.page() and "Printed at" in assembler.page()


def test_newsstand_page_title_names_the_newspaper(assembler):
    assembler.config["language"] = "pt-BR"
    assembler.config["newspaper"].pop("name")
    proc = ok(assembler.run())
    stand = (proc.archive / "index.html").read_text(encoding="utf-8")
    assert "<title>O Jornal Matinal · Banca</title>" in stand
    assert '<html lang="pt-BR">' in stand
    assert "NEWSSTAND TITLE: O Jornal Matinal · Banca" in proc.stdout


def test_headline_keeps_its_ref_with_the_researched_source(assembler, collected):
    assembler.edition["headline"].update(url="https://blog.example/original", outlet="Original Blog")
    ok(assembler.run())
    page = assembler.page()
    assert 'href="https://blog.example/original"' in page and "Original Blog" in page
    entry = assembler.new_index()["editions"][0]
    first = next(n for lst in collected["news"].values() for n in lst if n["id"] == "a1")
    assert first["title"] in entry["source_titles"]  # the repeat check still knows the story


@pytest.mark.parametrize("value, text", [
    ("the connector did not answer", "Could not read the agenda: the connector did not answer."),
    (True, "Could not read the agenda: the connector failed."),
])
def test_failed_agenda_says_why(assembler, value, text):
    del assembler.edition["agenda"]
    assembler.edition["agenda_error"] = value
    ok(assembler.run())
    page = assembler.page()
    assert text in page
    assert "not connected" not in page.split('class="classif"')[0] and "Free agenda today" not in page


def test_failed_gmail_says_why_even_in_a_share_copy(assembler):
    assembler.edition["classifieds_error"] = "access expired, connect again"
    ok(assembler.run("--share"))
    page = standalone_page(assembler)
    assert "Could not read Gmail: access expired, connect again." in page
    assert "Inbox under control" not in page


# ---------------------------------------------------------------- report of edition No. 004

def test_newsstand_page_title_names_the_newspaper(assembler):
    """B2: the static <title> names the artifact, so it must not stay "Newsstand"."""
    assembler.config["language"] = "pt-BR"
    assembler.config.setdefault("newspaper", {})["name"] = "O Jornal Matinal"
    proc = ok(assembler.run(index={"founded": "2026-11-10", "editions": []}))
    stand = (proc.archive / "index.html").read_text(encoding="utf-8")
    assert "<title>O Jornal Matinal · Banca</title>" in stand
    assert "<title>Newsstand</title>" not in stand
    assert '<html lang="pt-BR">' in stand


def test_classifieds_box_stays_on_weekends(assembler):
    """B1: an empty inbox on a Saturday prints "inbox up to date", like any other day."""
    assembler.edition["date"] = "2026-11-14"
    assembler.edition["classifieds"] = []
    ok(assembler.run())
    page = assembler.page("2026-11-14")
    assert 'class="classif"' in page and "Inbox under control" in page


def test_security_alert_line(assembler):
    """B9: a scheduled run sends no message, so the alert gets one neutral line in the paper."""
    assembler.edition["security_alert"] = True
    ok(assembler.run())
    assert "There are security alerts in your inbox" in assembler.page()


def test_no_security_line_by_default_or_without_gmail(assembler):
    ok(assembler.run())
    assert "security alerts" not in assembler.page()
    assembler.edition["security_alert"] = True
    del assembler.edition["classifieds"]
    ok(assembler.run())
    assert "security alerts" not in assembler.page()


def test_warning_above_the_usual_range(assembler):
    """B6: more stories than the day's usual range warns (the hard maximum still refuses)."""
    assembler.edition["date"] = "2026-11-14"
    assembler.config["total_news"] = {"weekday": [2, 3], "weekend": [2, 3], "max": 10}
    proc = ok(assembler.run())
    assert "WARNING:" in proc.stdout and "above the usual 2-3" in proc.stdout


def test_legacy_matutina_type_is_normalized(assembler):
    """B5: "matutina" was written by early versions and must become "morning"."""
    old = {"founded": "2026-11-10", "editions": [{"date": "2026-11-11", "number": 1, "type": "matutina"}]}
    ok(assembler.run(index=old))
    assert assembler.new_index()["editions"][1]["type"] == "morning"


def test_index_summary_starts_with_a_capital(assembler):
    assembler.config["language"] = "pt-BR"
    assembler.edition["agenda"] = []
    ok(assembler.run())
    assert assembler.new_index()["editions"][0]["summary"].startswith("Agenda livre")


# ---------------------------------------------------------------- medium and low priority fixes

def no_traceback(proc):
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "Traceback" not in proc.stderr and "ERROR:" in proc.stdout
    assert not proc.archive.exists()


def test_headline_as_text_is_an_error(assembler):
    assembler.edition["headline"] = "Just a sentence"
    no_traceback(assembler.run())


def test_section_story_as_text_is_an_error(assembler):
    assembler.edition["sections"]["tech"] = ["Just a sentence"]
    no_traceback(assembler.run())


def test_no_date_anywhere_is_an_error(assembler):
    assembler.collected.pop("date", None)
    assembler.edition.pop("date", None)
    proc = assembler.run()
    no_traceback(proc)
    assert "no valid date" in proc.stdout


def test_index_entry_without_date_is_dropped_with_a_warning(assembler):
    old = {"founded": "2026-11-10", "editions": [{"number": 1, "headline": "No date"},
                                                 {"date": "2026-11-12", "number": 2}]}
    proc = ok(assembler.run(index=old))
    assert "without a valid date" in proc.stdout
    assert [e["number"] for e in assembler.new_index()["editions"]] == [3, 2]


def test_incomplete_custom_labels_are_an_error(assembler):
    assembler.config["labels"] = {"weekdays": ["Mon"]}
    proc = assembler.run()
    no_traceback(proc)
    assert "labels.weekdays" in proc.stdout


@pytest.mark.parametrize("lang", ["pt-PT", "pt", "es-MX"])
def test_regional_language_uses_the_close_labels(assembler, lang):
    assembler.config["language"] = lang
    ok(assembler.run())
    page = assembler.page()
    assert f'<html lang="{lang}">' in page
    assert ("Sexta-feira" in page) if lang.startswith("pt") else ("Viernes" in page or "viernes" in page)


def test_sample_tag_reaches_the_newsstand(assembler):
    proc = ok(assembler.run("--sample"))
    assert assembler.new_index()["labels"]["sample_tag"] == "sample"
    stand = (proc.archive / "index.html").read_text(encoding="utf-8")
    assert "isSample(ed)" in stand


def test_long_words_wrap(assembler):
    proc = ok(assembler.run())
    assert "overflow-wrap:anywhere" in assembler.page()
    assert "overflow-wrap:anywhere" in (proc.archive / "index.html").read_text(encoding="utf-8")


def test_drop_cap_keeps_the_opening_quote_with_the_letter(assembler):
    assembler.edition["headline"]["text"] = "“Atualize já”, disse a empresa. O resto segue."
    ok(assembler.run())
    page = assembler.page()
    assert ">“A<" in page
    assert ">“<" not in page


def test_snow_icon(assembler):
    assembler.collected["weather"]["icon"] = "snow"
    ok(assembler.run())
    assert "M14 31v6M11 34h6" in assembler.page()


def test_history_cannot_use_a_news_ref(assembler):
    assembler.edition["history"] = {"ref": "a2", "text": "In 1990, something."}
    assembler.edition["sections"]["tech"] = []
    proc = assembler.run()
    refused(proc)
    assert "not an 'On this day' candidate" in proc.stdout


def test_did_you_know_needs_its_link(assembler):
    assembler.edition["did_you_know"] = {"text": "A fact."}
    proc = assembler.run()
    refused(proc)
    assert "did_you_know" in proc.stdout


def test_long_quote_in_a_title_is_refused(assembler):
    assembler.edition["sections"]["tech"][0]["title"] = (
        "“one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen”")
    refused(assembler.run())


def test_same_fact_twice_warns(assembler):
    for lst in assembler.collected["news"].values():
        for n in lst:
            if n["id"] == "b1":
                n["same_as"] = "a2"
    proc = ok(assembler.run())
    assert "may tell the same fact" in proc.stdout


def test_date_before_founding_is_refused(assembler):
    proc = assembler.run(index={"founded": "2026-12-01", "editions": []})
    refused(proc)
    assert "before the newsstand was founded" in proc.stdout


def test_warns_about_labels_left_in_english(assembler):
    """v1.4.3: a language with no shipped file and incomplete config.labels says which keys are missing."""
    assembler.config["language"] = "fr"
    assembler.config["labels"] = {"headline": "À la une", "weekdays": ["lundi", "mardi", "mercredi", "jeudi",
                                  "vendredi", "samedi", "dimanche"]}
    proc = ok(assembler.run())
    warn = [l for l in proc.stdout.splitlines() if l.startswith("WARNING:") and "still in English" in l]
    assert warn, proc.stdout
    assert "default_newspaper_name" in warn[0] and "months" in warn[0]
    assert " headline," not in warn[0] and "weekdays," not in warn[0].replace("weekdays_short", "")


@pytest.mark.parametrize("lang", ["pt-BR", "pt-PT", "es-MX", "en"])
def test_no_label_warning_for_shipped_languages(assembler, lang):
    assembler.config["language"] = lang
    proc = ok(assembler.run())
    assert "still in English" not in proc.stdout


def test_full_month_names_in_every_label_file():
    import json
    from conftest import SKILL
    for path in (SKILL / "assets" / "i18n").glob("*.json"):
        months = json.loads(path.read_text(encoding="utf-8"))["months"]
        assert len(months) == 12 and all(m.strip() for m in months), path.name


# ---------------------------------------------------------------- v1.5.0: weather without a link

def test_weather_from_a_tool_needs_no_link(assembler):
    """A forecast from the app's weather tool has no page: no url, an optional source name."""
    assembler.edition["weather"] = {"max": 29, "min": 19, "condition": "Partly sunny", "icon": "sun-cloud",
                                    "source": "app weather tool"}
    proc = assembler.run()
    ok(proc)
    page = assembler.page()
    assert "29° / 19°" in page
    assert "app weather tool" in page


def test_weather_with_a_bad_link_names_the_field_once(assembler):
    assembler.edition["weather"] = {"max": 29, "min": 19, "condition": "Sunny", "url": "http://x.example/"}
    proc = refused(assembler.run())
    errors = [l for l in proc.stdout.splitlines() if l.startswith("ERROR:")]
    assert len(errors) == 1 and "weather.url" in errors[0]


def test_missing_link_is_reported_once(assembler):
    """The page-wide link check no longer repeats an error a field check already named."""
    assembler.edition["sections"]["tech"][0].update(ref=None, outlet="X")
    proc = refused(assembler.run())
    assert "invalid link in page" not in proc.stdout
    assert "tech[0]: missing link" in proc.stdout


# ---------------------------------------------------------------- v1.5.0: single page with state

def single_page(assembler, **kw):
    proc = assembler.run("--single-page", **kw)
    ok(proc)
    assert "SINGLE PAGE" in proc.stdout
    return (assembler.tmp / "work" / "single" / "index.html").read_text(encoding="utf-8"), proc


def state_of(page):
    m = re.search(r'<script type="application/json" id="morning-newspaper-state">(.*?)</script>', page, re.S)
    assert m, "the single page must carry its state"
    return json.loads(m.group(1))


def test_single_page_carries_the_state(assembler):
    page, proc = single_page(assembler)
    state = state_of(page)
    assert state["config"]["city"] == assembler.config["city"]
    entry = state["index"]["editions"][0]
    assert entry["number"] == 1 and "links" not in entry and entry["link_ids"]
    assert "ARTIFACT TITLE:" in proc.stdout
    assert "../index.html" not in page  # no newsstand button
    assert re.search(r"<title>Morning Newspaper</title>", page)
    # The state sits near the top, so reading the first lines of the page is enough.
    assert page.index("morning-newspaper-state") < page.index("<style>")
    assert not (assembler.tmp / "work" / "archive").exists()


def test_single_page_state_cannot_close_its_script(assembler):
    assembler.config["newspaper"]["motto"] = "News </script><b>fresh</b>"
    page, _ = single_page(assembler)
    head = page.split("<style>", 1)[0]
    assert head.count("</script>") == 1
    assert state_of(page)["config"]["newspaper"]["motto"] == "News </script><b>fresh</b>"


def test_unpack_state_round_trip_continues_the_numbering(assembler, tmp_path):
    page, _ = single_page(assembler)
    raw = re.search(r'id="morning-newspaper-state">(.*?)</script>', page).group(1)
    (tmp_path / "state.json").write_text(raw, encoding="utf-8")
    out = tmp_path / "next"
    proc = subprocess.run([sys.executable, str(SCRIPTS / "assemble.py"), "--unpack-state",
                           str(tmp_path / "state.json"), "--work", str(out)], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stdout
    assert "STATE:" in proc.stdout
    assert json.loads((out / "config.json").read_text(encoding="utf-8"))["city"] == assembler.config["city"]
    index = json.loads((out / "index.json").read_text(encoding="utf-8"))
    assembler.edition["date"] = "2026-11-14"
    page2, proc2 = single_page(assembler, index=index)
    assert "No. 002" in proc2.stdout
    assert [e["number"] for e in state_of(page2)["index"]["editions"]] == [2, 1]


def test_unpack_state_accepts_the_whole_page_and_refuses_garbage(assembler, tmp_path):
    page, _ = single_page(assembler)
    (tmp_path / "page.html").write_text(page, encoding="utf-8")
    run = lambda f: subprocess.run([sys.executable, str(SCRIPTS / "assemble.py"), "--unpack-state", str(f),
                                    "--work", str(tmp_path / "w")], capture_output=True, text=True)
    assert run(tmp_path / "page.html").returncode == 0
    (tmp_path / "bad.json").write_text("{not json", encoding="utf-8")
    proc = run(tmp_path / "bad.json")
    assert proc.returncode == 1 and proc.stdout.startswith("ERROR:") and "Traceback" not in proc.stderr


def test_only_one_output_mode(assembler):
    proc = assembler.run("--single-page", "--standalone")
    assert proc.returncode != 0


def test_did_you_know_from_a_collected_candidate(assembler):
    """v1.6.0: a k ref brings its Wikipedia link, so no search or page is needed."""
    assembler.collected["did_you_know"] = [{"id": "k1", "title": "Alpha", "text": "…",
                                            "url": "https://en.wikipedia.org/wiki/Alpha", "lang": "en"}]
    assembler.edition["did_you_know"] = {"ref": "k1", "text": "The first version ran on a single machine."}
    ok(assembler.run())
    assert "https://en.wikipedia.org/wiki/Alpha" in assembler.page()
    import shutil
    shutil.rmtree(assembler.tmp / "work" / "archive")
    assembler.edition["did_you_know"] = {"ref": "a1", "text": "A news ref is not a candidate."}
    assert "not a 'Did you know?' candidate" in refused(assembler.run()).stdout


# ---------------------------------------------------------------- a weaker reissue never replaces the edition

def test_weaker_reissue_keeps_the_published_edition(assembler):
    old = {"founded": "2026-11-10", "editions": [
        {"date": "2026-11-13", "number": 5, "headline": "Fuller morning edition",
         "links": [f"https://x.example/{i}" for i in range(20)]}]}
    proc = assembler.run(index=old)
    assert proc.returncode == 3, proc.stdout + proc.stderr
    assert "KEEP:" in proc.stdout and "Fuller morning edition" in proc.stdout
    assert "Traceback" not in proc.stderr
    assert not proc.archive.exists()
    proc = ok(assembler.run("--replace", index=old))
    assert "REISSUE" in proc.stdout


def test_next_steps_are_printed_after_ok(assembler):
    proc = ok(assembler.run())
    assert "NEXT (mandatory, in order):" in proc.stdout


def test_a_lone_extra_takes_the_full_width(assembler):
    ok(assembler.run())
    assert ".extras>.extra:only-child{grid-column:1/-1}" in assembler.page()


def test_a_day_with_no_story_still_gets_its_edition(assembler):
    """Every story left out by the rules: the paper still comes out, with a note instead of a headline."""
    assembler.edition.pop("headline")
    assembler.edition["sections"] = {}
    proc = ok(assembler.run())
    page = assembler.page()
    assert "No confirmed news today" in page
    assert "Traceback" not in proc.stderr
    assert assembler.new_index()["editions"][0]["headline"] == "No confirmed news today"


# ---------------------------------------------------------------- collection, coverage and run log (v1.8.0)

def test_refuses_without_collected_json(assembler):
    """An edition built without the collection cannot be checked against anything."""
    assembler.collected = None
    proc = refused(assembler.run())
    assert "collected.json not found" in proc.stdout


def test_network_blocked_without_fallback_refuses_stories(assembler):
    assembler.collected["network_blocked"] = True
    proc = refused(assembler.run())
    assert "no-network.md" in proc.stdout


def test_network_blocked_with_fallback_results_is_fine(assembler):
    assembler.collected.update(network_blocked=True, from_results=True)
    ok(assembler.run())


def test_network_blocked_with_no_stories_still_prints_the_edition(assembler):
    assembler.collected["network_blocked"] = True
    assembler.edition.pop("headline")
    assembler.edition.pop("sections")
    proc = ok(assembler.run())
    assert "COVERAGE: 0 stories" in proc.stdout


def test_coverage_names_the_empty_sections(assembler):
    assembler.edition["sections"] = {"local": assembler.edition["sections"]["local"]}
    proc = ok(assembler.run())
    line = next(l for l in proc.stdout.splitlines() if l.startswith("COVERAGE:"))
    assert line.startswith("COVERAGE: 2 stories")
    with_part, empty_part = line.split(" · empty: ")
    titles = {s["id"]: s["title"] for s in assembler.config["sections"]}
    assert titles["local"] in with_part
    for sid in ("money", "games"):
        assert titles[sid] in empty_part
    assert "Missing line" in proc.stdout


def test_coverage_with_every_section_filled(assembler):
    proc = ok(assembler.run())
    assert "· empty: none" in proc.stdout


@pytest.mark.parametrize("mode", ["--standalone", "--share", "--single-page"])
def test_every_mode_prints_coverage_and_next_steps(assembler, mode):
    proc = ok(assembler.run(mode))
    assert "COVERAGE:" in proc.stdout
    assert "6. Check every sentence" in proc.stdout
    assert "8. Reply with the edition summary" in proc.stdout


def test_standalone_next_steps_say_send_not_publish(assembler):
    proc = ok(assembler.run("--standalone"))
    assert "Nothing to publish: send the file" in proc.stdout
    assert "publish exactly" not in proc.stdout


def test_run_log_keeps_the_real_output(assembler):
    proc = ok(assembler.run())
    log = (assembler.tmp / "work" / "run.log").read_text(encoding="utf-8")
    assert "===== assemble.py ·" in log
    assert "--work" in log
    assert proc.stdout.strip().splitlines()[0] in log
    assert "[exit 0]" in log


def test_run_log_appends_runs_including_refusals(assembler):
    assembler.edition["sections"]["nope"] = []
    refused(assembler.run())
    assembler.edition["sections"].pop("nope")
    ok(assembler.run())
    log = (assembler.tmp / "work" / "run.log").read_text(encoding="utf-8")
    assert log.count("===== assemble.py ·") == 2
    assert "[exit 1]" in log and "[exit 0]" in log
    assert "is not in config.json" in log


# ---------------------------------------------------------------- v1.9.0

def test_check_lines_flag_names_numbers_and_dropped_hedges(assembler):
    assembler.collected["news"]["tech"][0]["title"] = "Bank says data of clients was potentially exposed"
    for sid, lst in assembler.edition["sections"].items():
        for n in lst:
            if n.get("ref") == "a1":
                n["title"] = "Bank exposed data of clients"
                n["text"] = "The Mega Bank exposed data of 300 clients."
    if assembler.edition["headline"].get("ref") == "a1":
        h = assembler.edition["headline"]
        h["title"], h["text"] = "Bank exposed data of clients", "The Mega Bank exposed data of 300 clients."
    proc = ok(assembler.run())
    checks = [l for l in proc.stdout.splitlines() if l.startswith("CHECK:") and "a1" in l]
    joined = " ".join(checks)
    assert "Mega" in joined and "300" in joined and "hedges" in joined


def test_a_faithful_story_gets_no_check(collect_module):
    import importlib.util
    spec = importlib.util.spec_from_file_location("assemble_mod", SCRIPTS / "assemble.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    src = "Debian corrige falha no Sympa que expõe e-mails apagados"
    assert mod.unsupported("Debian corrige falha no Sympa. O Debian corrigiu a falha.", src, True) == []
    notes = mod.unsupported("O Debian corrigiu o Sympa, gerenciador de listas de e-mail.", src, True)
    assert any("gerenciador" in n for n in notes)


def test_section_count_excludes_the_headline(assembler):
    sid = next(iter(assembler.edition["sections"]))
    rng = next(s for s in assembler.config["sections"] if s["id"] == sid)["count"]["weekday"]
    assembler.config["sections"] = [dict(s, count={"weekday": [0, 0], "weekend": [0, 0]}) if s["id"] == sid else s
                                    for s in assembler.config["sections"]]
    proc = ok(assembler.run())
    assert f"WARNING: {sid}:" in proc.stdout and "headline does not count" in proc.stdout


def test_summary_says_inbox_up_to_date(assembler):
    assembler.edition["classifieds"] = []
    ok(assembler.run())
    entry = assembler.new_index()["editions"][0]
    assert "inbox up to date" in entry["summary"]


def test_headline_icons_match_the_instructions():
    """Every icon the instructions offer has a drawing, every drawing is offered, and each is valid SVG."""
    import importlib.util
    import xml.dom.minidom
    from conftest import SKILL
    spec = importlib.util.spec_from_file_location("assemble_icons", SCRIPTS / "assemble.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    drawn = set(mod.SVG_ICON)
    skill_line = next(l for l in (SKILL / "SKILL.md").read_text(encoding="utf-8").splitlines() if "`icon`:" in l)
    in_skill = set(re.findall(r"`([a-z-]+)`", skill_line.split("`icon`:", 1)[1].split("(topics", 1)[0]))
    fmt = (SKILL / "references" / "edition-format.md").read_text(encoding="utf-8")
    block = fmt.split("- `icon` (headline illustration)", 1)[1].split("\n- ", 1)[0]
    in_format = set(re.findall(r"`([a-z-]+)` \(", block))
    assert in_skill == drawn, (in_skill ^ drawn)
    assert in_format == drawn, (in_format ^ drawn)
    assert len(drawn) >= 30
    for name, drawing in mod.SVG_ICON.items():
        xml.dom.minidom.parseString(mod.svg(drawing, 56))
        assert "{" not in drawing and "}" not in drawing, name


# ---------------------------------------------------------------- debug of edition 007

def _assemble_mod():
    import importlib.util
    spec = importlib.util.spec_from_file_location("assemble_mod", SCRIPTS / "assemble.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_attribution_to_the_collected_outlet_is_not_a_check():
    """'Segundo o BPMoney, …' names the story's own outlet; it is not a fact from memory."""
    mod = _assemble_mod()
    src = "Hackers invadem software da Luxor e desviam recompensas de mineração de Bitcoin BPMoney"
    assert mod.unsupported(["Segundo o BPMoney, hackers invadiram um software da Luxor."], src, True) == []
    assert mod.unsupported(["Segundo o Valor, hackers invadiram um software da Luxor."], src, True)


def test_country_short_and_full_names_match():
    mod = _assemble_mod()
    src = "Alta de juros nos EUA faz dólar disparar Jornal do Brasil"
    assert mod.unsupported(["A alta de juros nos Estados Unidos fez o dólar disparar."], src, True) == []
    assert mod.unsupported(["Os Estados Unidos usam a soja."], "Soja sobe em Chicago; fala-se de nós", True)


def test_another_tense_of_a_title_word_is_not_a_check():
    mod = _assemble_mod()
    src = "Volta da Preguiça ganha rota de cicloturismo de 12 km na zona rural de Divinópolis"
    assert mod.unsupported(["A Volta da Preguiça, na zona rural de Divinópolis, ganhou uma rota de "
                            "cicloturismo de 12 km."], src, True) == []


def test_weather_condition_is_ignored_when_already_in_the_readers_language(assembler):
    assembler.edition["weather_condition"] = "Mostly sunny with breeze"
    proc = ok(assembler.run())  # the sample's condition is already English, like the config
    page = next((proc.archive / "editions").glob("*.html")).read_text(encoding="utf-8")
    assert "Partly cloudy" in page and "Mostly sunny with breeze" not in page
    assembler.collected["weather"]["condition_lang"] = "es"
    proc = ok(assembler.run())
    page = next((proc.archive / "editions").glob("*.html")).read_text(encoding="utf-8")
    assert "Mostly sunny with breeze" in page


# ---------------------------------------------------------------- v1.11.0

def test_wrong_weekday_next_to_a_date_is_refused(assembler):
    # 2026-11-12 was a Thursday; the edition is dated 2026-11-13.
    assembler.edition["headline"]["text"] = "A browser maker released a fix on Wednesday, Nov. 12. It was exploited."
    proc = refused(assembler.run())
    assert '"wednesday, nov. 12" does not match the calendar: 2026-11-12 is a Thursday' in proc.stdout


@pytest.mark.parametrize("text", [
    "A browser maker released a fix on Thursday, Nov. 12. It was exploited.",
    "A browser maker released a fix on Thursday. It was exploited 12 times.",
    "A browser maker released a fix on Monday, 9:30. It was exploited.",
])
def test_right_or_undated_weekdays_pass(assembler, text):
    assembler.edition["headline"]["text"] = text
    ok(assembler.run())


def test_weekday_check_in_portuguese(assembler):
    assembler.config["language"] = "pt-BR"
    assembler.edition["headline"]["text"] = "A Oracle liberou na quarta-feira, 12, correções. Pela segunda vez, 12 países pediram."
    proc = refused(assembler.run())
    assert "quarta-feira, 12" in proc.stdout and "Quinta-feira" in proc.stdout
    assembler.edition["headline"]["text"] = "A Oracle liberou na quinta-feira, 12, correções. Pela segunda vez, 12 países pediram."
    ok(assembler.run())


def test_dropping_an_attribution_between_runs_warns(assembler):
    story = assembler.edition["sections"]["tech"][0]
    story["text"] = "Outlets report that it beats larger models on the test."
    first = ok(assembler.run())
    assert "attributed this story" not in first.stdout
    story["text"] = "It beats larger models on the test."
    second = ok(assembler.run())
    assert f"WARNING: {story['ref']}: an earlier run attributed this story" in second.stdout


def test_attribution_words_are_not_checks(collect_module):
    import importlib.util
    spec = importlib.util.spec_from_file_location("assemble_mod", SCRIPTS / "assemble.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    src = "Falha crítica no Apache mod_http2 CVE-2026-119618, Singapura alerta ataques"
    notes = mod.unsupported("Veículos relatam que Singapura alerta para ataques à falha crítica no Apache.", src, True)
    assert not any("veiculos" in n or "relatam" in n for n in notes)


def test_researched_headline_reminds_to_credit_the_collected_outlet(assembler, collected):
    first = next(n for lst in collected["news"].values() for n in lst if n["id"] == "a1")
    assembler.edition["headline"].update(url="https://blog.example/original", outlet="Original Blog")
    proc = ok(assembler.run())
    assert f"must be attributed to {first['outlet']}" in proc.stdout
    assembler.edition["headline"]["text"] += f" According to {first['outlet']}, two governments asked for the update."
    proc = ok(assembler.run())
    assert "must be attributed to" not in proc.stdout


# ---------------------------------------------------------------- v1.11.0: keyword self-tuning

def _off_topic_day(assembler):
    """Today: 4 tech candidates, 2 left out as off-topic (enough for one heavy edition)."""
    assembler.collected["news"]["tech"].append(dict(assembler.collected["news"]["tech"][-1], id="a4",
                                                    url="https://tech.example/a4", title="Car maker merges two models"))
    assembler.edition["off_topic"] = ["a3", "a4"]


def _index(*fits, log_dates=()):
    eds = [{"date": f"2026-11-{12 - i:02d}", "number": 10 - i, "headline": "Old", "fit": f}
           for i, f in enumerate(fits)]
    return {"newspaper": "Morning Newspaper", "founded": "2026-11-01", "editions": eds}


PROPOSAL = {"tech": {"add": ["compiler", "linux kernel"], "remove": []}}


def test_keywords_applied_with_enough_ground(assembler):
    _off_topic_day(assembler)
    assembler.edition["keywords_proposal"] = PROPOSAL
    proc = ok(assembler.run(index=_index({"tech": [10, 4]}, {"tech": [10, 3]})))
    assert "KEYWORDS: tech: applied (+compiler, +linux kernel; ground: 3 of 3 editions)" in proc.stdout
    assert "  config.json -> " in proc.stdout
    cfg = json.loads((proc.archive / "config.json").read_text(encoding="utf-8"))
    tech = next(s for s in cfg["sections"] if s["id"] == "tech")
    assert tech["keywords"][-2:] == ["compiler", "linux kernel"]
    assert cfg["keywords_log"][-1]["section"] == "tech" and cfg["keywords_log"][-1]["settled"] is False
    assert "Editor&#x27;s note: the Technology, AI &amp; Security section was adjusted" in assembler.page() \
        or "Editor's note: the Technology, AI &amp; Security section was adjusted" in assembler.page()
    assert assembler.new_index()["editions"][0]["fit"]["tech"] == [4, 2]


def test_keywords_ignored_without_ground(assembler):
    _off_topic_day(assembler)
    assembler.edition["keywords_proposal"] = PROPOSAL
    proc = ok(assembler.run(index=_index({"tech": [10, 0]}, {"tech": [10, 4]})))
    assert "KEYWORDS: tech: proposal ignored: not enough ground" in proc.stdout
    assert "config.json" not in proc.stdout.split("PUBLISH", 1)[1].split("COVERAGE", 1)[0]
    assert "section was adjusted" not in assembler.page()


@pytest.mark.parametrize("change, reason", [
    ({"local": {"add": ["traffic"]}}, "local news keeps no keywords"),
    ({"tech": {"add": ["https://evil.example"]}}, "no links"),
    ({"tech": {"add": ["a", "b", "c", "d", "e"]}}, "add 1-4 short words"),
    ({"tech": {"add": ["compiler"], "remove": ["software security"]}}, "remove only words"),
    ({"tech": {"add": ["compiler"], "remove": ["vulnerability", "hackers"]}}, "remove at most as many"),
    ({"sports": {"add": ["football"]}}, "no such section"),
])
def test_bad_keyword_proposals_are_ignored(assembler, change, reason):
    _off_topic_day(assembler)
    assembler.edition["keywords_proposal"] = change
    proc = ok(assembler.run(index=_index({"tech": [10, 4]}, {"tech": [10, 3]})))
    assert "proposal ignored" in proc.stdout and reason in proc.stdout


def test_one_keyword_change_a_week(assembler):
    _off_topic_day(assembler)
    assembler.config["keywords_log"] = [{"date": "2026-11-09", "section": "tech", "before": [], "after": [],
                                         "settled": True}]
    assembler.edition["keywords_proposal"] = PROPOSAL
    proc = ok(assembler.run(index=_index({"tech": [10, 4]}, {"tech": [10, 3]})))
    assert "already changed on 2026-11-09" in proc.stdout


def test_a_change_that_made_it_worse_is_undone(assembler):
    tech = next(s for s in assembler.config["sections"] if s["id"] == "tech")
    before = list(tech.get("keywords") or [])
    tech["keywords"] = before + ["cars"]
    assembler.config["keywords_log"] = [{"date": "2026-11-09", "section": "tech", "before": before,
                                         "after": tech["keywords"], "before_rate": 0.1, "settled": False}]
    _off_topic_day(assembler)
    proc = ok(assembler.run(index=_index({"tech": [10, 6]}, {"tech": [10, 5]})))
    assert "KEYWORDS: tech: the change of 2026-11-09 made it worse" in proc.stdout
    cfg = json.loads((proc.archive / "config.json").read_text(encoding="utf-8"))
    assert next(s for s in cfg["sections"] if s["id"] == "tech")["keywords"] == before
    assert all(e["settled"] for e in cfg["keywords_log"])
    assert "was undone" in assembler.page()


def test_a_change_that_helped_is_kept_and_settled(assembler):
    tech = next(s for s in assembler.config["sections"] if s["id"] == "tech")
    tech["keywords"] = list(tech.get("keywords") or []) + ["compiler"]
    assembler.config["keywords_log"] = [{"date": "2026-11-09", "section": "tech", "before": [],
                                         "after": tech["keywords"], "before_rate": 0.5, "settled": False}]
    proc = ok(assembler.run(index=_index({"tech": [10, 1]}, {"tech": [10, 0]})))
    cfg = json.loads((proc.archive / "config.json").read_text(encoding="utf-8"))
    assert cfg["keywords_log"][0]["settled"] is True
    assert next(s for s in cfg["sections"] if s["id"] == "tech")["keywords"][-1] == "compiler"
    assert "undone" not in proc.stdout and "Editor" not in assembler.page()


def test_copies_outside_the_newsstand_never_tune_keywords(assembler):
    _off_topic_day(assembler)
    assembler.edition["keywords_proposal"] = PROPOSAL
    proc = ok(assembler.run("--standalone", index=_index({"tech": [10, 4]}, {"tech": [10, 3]})))
    assert "KEYWORDS:" not in proc.stdout
    cfg = json.loads((assembler.tmp / "config.json").read_text(encoding="utf-8"))
    assert "keywords_log" not in cfg


# ---------------------------------------------------------------- edition No. 009 report

def _assemble_module():
    import importlib.util
    spec = importlib.util.spec_from_file_location("assemble_mod", SCRIPTS / "assemble.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_name_opening_a_sentence_is_checked():
    """"Pavel Durov negou…": the first name was added from memory and never flagged, because the
    first word of every sentence was skipped."""
    mod = _assemble_module()
    src = "Widgets do Telegram, Durov nega falha RCE e lança desafio aos hackers"
    notes = mod.unsupported(["Pavel Durov negou a falha nos widgets do Telegram."], src, False)
    assert any("names not in the source" in n and "Pavel" in n for n in notes)
    # An ordinary capitalized first word is still not a name
    assert mod.unsupported(["Durov nega falha RCE e lança desafio aos hackers."], src, False) == []
    assert mod.unsupported(["Widgets do Telegram: Durov nega falha RCE."], src, False) == []


@pytest.mark.parametrize("key,app", [("classifieds", "Gmail"), ("agenda", "Google Calendar")])
def test_missing_connector_key_warns(assembler, key, app):
    del assembler.edition[key]
    proc = ok(assembler.run())
    warn = [l for l in proc.stdout.splitlines() if l.startswith("WARNING:") and f'no "{key}" key' in l]
    assert warn and app in warn[0] and f'"{key}": []' in warn[0]


def test_connector_keys_present_or_failed_do_not_warn(assembler):
    assembler.edition["classifieds"] = []
    del assembler.edition["agenda"]
    assembler.edition["agenda_error"] = True
    proc = ok(assembler.run())
    assert "key: the" not in proc.stdout


@pytest.mark.parametrize("sentence", [
    "Após Durov negar a falha, o Telegram respondeu.",
    "Segundo Durov, não há falha nos widgets.",
    "Também Apple lança iPhone.",
    "Hoje Apple lança iPhone.",
    "Recentemente Durov negou a falha.",
    "After Apple launched the iPhone, Google responded.",
    "Meanwhile Google responded.",
    "Tras Apple lança iPhone.",
    "Nesta segunda, Durov negou a falha.",
])
def test_common_word_opening_a_sentence_is_not_a_name(sentence):
    """The No. 009 fix must not flag an ordinary opening word just because a name follows it."""
    mod = _assemble_module()
    src = "Durov nega falha RCE nos widgets do Telegram e Apple lança iPhone; Google responde"
    assert mod.unsupported([sentence], src, False) == []
