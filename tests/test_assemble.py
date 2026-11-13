"""scripts/assemble.py: builds the edition HTML and the newsstand index from edition.json."""
import re

import pytest


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
    assert "https://tech.example.com/a1" in entry["links"]
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


def test_existing_newsstand_publishes_only_the_edition(assembler):
    old = {"newspaper": "Morning Newspaper", "founded": "2026-11-10",
           "editions": [{"date": "2026-11-12", "number": 3, "headline": "Old", "links": []}]}
    proc = ok(assembler.run(index=old))
    assert not (proc.archive / "index.html").exists()
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
                   "titles": ["Um", "Dois"], "links": ["https://old.example/1"],
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
    assert not (proc.archive / "index.html").exists()
    eds = assembler.new_index()["editions"]
    assert [e["number"] for e in eds] == [3, 2, 1]
    assert eds[2]["headline"] == "Old keys" and eds[2]["file"] == "edicoes/2026-11-11.html"
    legacy_keys = {"data", "numero", "manchete", "arquivo", "titulos", "resumo", "tipo", "dia_semana"}
    assert not any(legacy_keys & set(e) for e in eds)


def test_with_page_republishes_the_newsstand_page(assembler):
    old = {"founded": "2026-11-10", "editions": [{"date": "2026-11-12", "number": 1}]}
    proc = ok(assembler.run("--with-page", index=old))
    assert (proc.archive / "index.html").exists()
    assert "  index.html -> " in proc.stdout
    assert not (proc.archive / "config.json").exists()


def test_missing_agenda_key_hides_the_box(assembler):
    del assembler.edition["agenda"]
    ok(assembler.run())
    assert "Today's Column" not in assembler.page()


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


TRACEBACK_BUG = pytest.mark.xfail(
    reason="known bug: assemble.py crashes with a KeyError traceback instead of printing ERROR")


@pytest.mark.parametrize("case", [
    pytest.param(c, marks=TRACEBACK_BUG) if c in ("unknown ref", "missing outlet") else c
    for c in sorted(REFUSALS)])
def test_refuses_bad_edition(assembler, case):
    REFUSALS[case](assembler.edition)
    refused(assembler.run())


def test_refuses_more_stories_than_the_maximum(assembler):
    assembler.config["total_news"]["max"] = 3
    refused(assembler.run())


# ---------------------------------------------------------------- known bugs (remove the mark once fixed)
# xfail_strict is on: when a bug is fixed, its test starts passing and the suite fails until
# the @pytest.mark.xfail line is removed.

@pytest.mark.xfail(reason="known bug: the classifieds rule \\d{4,} refuses years such as 2026")
def test_classified_may_mention_a_year(assembler):
    assembler.edition["classifieds"][0]["text"] = "Ana asked about the 2026 plan."
    ok(assembler.run())


@pytest.mark.xfail(reason="known bug: the 15-word quote check ignores single curly quotes ‘…’")
def test_refuses_long_quote_in_single_quotes(assembler):
    assembler.edition["sections"]["tech"][0]["text"] = f"He said ‘{LONG}’ today."
    refused(assembler.run())


@pytest.mark.xfail(reason="known bug: text containing '{{ ... }}' is mistaken for a template leftover")
def test_story_about_templates_is_accepted(assembler):
    assembler.edition["sections"]["tech"][0]["text"] = "Jinja uses {{ name }} for variables."
    ok(assembler.run())
    assert "{{ name }}" in assembler.page()


@pytest.mark.xfail(reason="known bug: '{{MOTTO}}' in reader text is replaced by template data")
def test_template_markers_in_text_stay_literal(assembler):
    assembler.edition["agenda"][0]["event"] = "Write about {{MOTTO}}"
    ok(assembler.run())
    assert "Write about {{MOTTO}}" in assembler.page()
