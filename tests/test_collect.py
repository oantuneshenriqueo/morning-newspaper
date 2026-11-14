"""scripts/collect.py, fully offline: every network call is answered by a fixture."""
import datetime as dt
import email.utils
import json
import pathlib
import subprocess
import sys

import pytest

from conftest import ROOT

UTC = dt.timezone.utc
NOW = dt.datetime(2026, 11, 13, 9, 0, tzinfo=UTC)


def rss(*items):
    """Builds an RSS 2.0 feed. Each item: (title, link, hours_ago or None, outlet or None)."""
    body = []
    for title, link, ago, outlet in items:
        pub = f"<pubDate>{email.utils.format_datetime(NOW - dt.timedelta(hours=ago))}</pubDate>" if ago is not None else ""
        src = f"<source url='https://x'>{outlet}</source>" if outlet else ""
        body.append(f"<item><title>{title}</title><link>{link}</link>{pub}{src}"
                    f"<description>{title}</description></item>")
    return f"<?xml version='1.0'?><rss version='2.0'><channel>{''.join(body)}</channel></rss>"


# ---------------------------------------------------------------- pure helpers

def test_clean_strips_html_and_cuts_at_a_word(collect_module):
    assert collect_module.clean("<b>Hello</b> &amp;   world") == "Hello & world"
    cut = collect_module.clean("alpha beta gamma delta", limit=12)
    assert cut == "alpha beta…"


@pytest.mark.parametrize("a, b, same", [
    ("Central bank holds interest rates steady", "Interest rates held steady by central bank", True),
    ("Central bank holds interest rates steady", "Farming sim gets big winter update", False),
    ("", "anything", False),
])
def test_same_story(collect_module, a, b, same):
    assert collect_module.same_story(a, b) is same


@pytest.mark.parametrize("text, icon", [
    ("Thunderstorm", "storm"), ("Chuva forte", "rain"), ("Partly cloudy", "sun-cloud"),
    ("Nublado", "cloud"), ("Sunny", "sun"), ("Light drizzle", "rain"), ("Neblina", "cloud"),
])
def test_icon_from_text(collect_module, text, icon):
    assert collect_module.icon_from_text(text) == icon


def test_section_prefixes_skip_h(collect_module):
    sections = [{"id": str(i)} for i in range(8)]
    assert "h" not in collect_module.prefixes(sections).values()


# ---------------------------------------------------------------- RSS

def test_read_rss(collect_module, offline):
    offline["feed.example"] = rss(
        ("Big news - Example Outlet", "https://news.example/1", 2, "Example Outlet"),
        ("No source tag", "https://www.site.example/2", 3, None),
        ("Insecure link", "http://site.example/3", 1, None))
    items = collect_module.read_rss("https://feed.example/rss")
    assert [i["title"] for i in items] == ["Big news", "No source tag"]
    assert items[0]["outlet"] == "Example Outlet"
    assert items[1]["outlet"] == "site.example"
    assert items[0]["date"] == NOW - dt.timedelta(hours=2)
    assert items[0]["summary"] == ""  # description repeating the title is dropped


@pytest.mark.xfail(reason="known bug: Atom feeds (<entry>) come back empty without a FAILURES line")
def test_read_atom_feed(collect_module, offline):
    offline["atom.example"] = (
        "<?xml version='1.0'?><feed xmlns='http://www.w3.org/2005/Atom'><entry><title>Atom story</title>"
        "<link href='https://atom.example/1'/><updated>2026-11-13T08:00:00Z</updated></entry></feed>")
    assert collect_module.read_rss("https://atom.example/feed")


def test_collect_news_filters_window_repeats_and_duplicates(collect_module, offline, config):
    offline["news.google.com"] = rss(
        ("Fresh story about rockets", "https://n.example/1", 1, "A"),
        ("Fresh story about rockets again", "https://n.example/2", 2, "B"),   # same story as #1
        ("Too old to print", "https://n.example/3", 60, "C"),                 # outside 48 h
        ("Already printed yesterday", "https://n.example/4", 3, "D"),         # link used before
        ("Previous headline about volcanoes", "https://n.example/5", 4, "E"), # title used before
        ("Undated story", "https://n.example/6", None, "F"),                  # no date
        ("Second good story on databases", "https://n.example/7", 5, "G"))
    config["sections"] = config["sections"][:1]
    news, failures = collect_module.collect_news(
        config, 48, NOW, {"https://n.example/4"}, ["Previous headline about volcanoes"], UTC)
    titles = [n["title"] for n in news["tech"]]
    assert failures == []
    assert titles[0] == "Fresh story about rockets"
    assert "Second good story on databases" in titles
    for gone in ("Fresh story about rockets again", "Too old to print", "Already printed yesterday",
                 "Previous headline about volcanoes", "Undated story"):
        assert gone not in titles
    assert [n["id"] for n in news["tech"]] == [f"a{i}" for i in range(1, len(titles) + 1)]


def test_collect_news_reports_failed_feeds(collect_module, offline, config):
    config["sections"] = config["sections"][:1]
    news, failures = collect_module.collect_news(config, 48, NOW, set(), [], UTC)  # nothing registered
    assert news["tech"] == []
    assert failures and failures[0].startswith("tech:")


def test_max_candidates(collect_module, offline, config):
    offline["news.google.com"] = rss(*[(t, f"https://n.example/{i}", i, "A") for i, t in enumerate(
        ["Rocket launch delayed", "Database release ships", "Browser update lands",
         "Chip factory opens", "Satellite reaches orbit"], 1)])
    config["sections"] = [dict(config["sections"][0], max_candidates=2)]
    news, _ = collect_module.collect_news(config, 48, NOW, set(), [], UTC)
    assert len(news["tech"]) == 2


def test_searches_take_turns(collect_module, offline, config):
    """A busy search must not fill every slot: each search contributes its newest stories in turn."""
    busy = ["Rocket launch delayed", "Database release ships", "Browser update lands", "Chip factory opens",
            "Satellite reaches orbit", "Compiler gains speed", "Keyboard maker expands", "Router flaw patched",
            "Telescope spots comet", "Printer driver recalled", "Tablet sales climb", "Drone rules change"]
    offline["q=busy"] = rss(*[(t, f"https://busy.example/{i}", 0.1 * i, "Busy") for i, t in enumerate(busy, 1)])
    offline["q=quiet"] = rss(("Library opens archive", "https://quiet.example/1", 30, "Quiet"),
                             ("Museum restores piano", "https://quiet.example/2", 40, "Quiet"))
    config["sections"] = [dict(config["sections"][0], queries=["busy", "quiet"], max_candidates=6)]
    news, failures = collect_module.collect_news(config, 48, NOW, set(), [], UTC)
    assert failures == []
    outlets = [n["outlet"] for n in news["tech"]]
    assert len(outlets) == 6
    assert outlets.count("Quiet") == 2, "the quiet search lost its place to the busy one"
    dates = [n["date"] for n in news["tech"]]
    assert dates == sorted(dates, reverse=True)


# ---------------------------------------------------------------- repeats: only the last 14 editions

def test_old_headlines_stop_blocking_recurring_news(collect_module):
    editions = [{"date": f"2026-10-{d:02d}", "number": d, "headline": f"Headline {d}",
                 "titles": [f"Title {d}"], "source_titles": [f"Collected {d}"],
                 "links": [f"https://x.example/{d}"]} for d in range(1, 21)]
    editions.append({"date": "2026-11-13", "number": 21, "headline": "Today", "links": ["https://x.example/today"]})
    previous, links, titles = collect_module.past_editions({"editions": editions}, dt.date(2026, 11, 13))
    assert len(previous) == 20 and previous[0]["date"] == "2026-10-20"
    assert "Headline 20" in titles and "Title 7" in titles and "Collected 7" in titles
    assert "Headline 6" not in titles and "Title 6" not in titles, "editions older than 14 must not block"
    assert "https://x.example/7" in links and "https://x.example/6" not in links
    assert "Today" not in titles and "https://x.example/today" not in links  # a reissue may reuse its own stories


def test_past_editions_understands_legacy_keys(collect_module):
    idx = {"edicoes": [{"data": "2026-11-12", "numero": 1, "manchete": "Copom mantém Selic", "titulos": ["Outro"]}]}
    _, _, titles = collect_module.past_editions(idx, dt.date(2026, 11, 13))
    assert titles == ["Copom mantém Selic", "Outro"]


def test_recent_story_is_still_dropped(collect_module, offline, config):
    offline["news.google.com"] = rss(("Central bank holds rates steady again", "https://n.example/1", 1, "A"))
    config["sections"] = config["sections"][:1]
    _, _, titles = collect_module.past_editions(
        {"editions": [{"date": "2026-11-12", "source_titles": ["Central bank holds rates steady"]}]},
        dt.date(2026, 11, 13))
    news, _ = collect_module.collect_news(config, 48, NOW, set(), titles, UTC)
    assert news["tech"] == []


# ---------------------------------------------------------------- the reader's "avoid" list

@pytest.mark.parametrize("text, avoid, hit", [
    ("New software and hardware win an award", ["war"], False),
    ("Case studies on Battlefield executives in Bombay", ["dies", "battle", "execu", "bomb"], False),
    ("The war ended in 1945", ["war"], True),
    ("A GUERRA terminou", ["guerra"], True),
    ("Eleição municipal é adiada", ["eleicao"], True),
    ("Real Madrid wins again", ["real madrid"], True),
    ("A real story from Madrid", ["real madrid"], False),
    ("Anything at all", [], False),
])
def test_avoid_matches_whole_words(collect_module, text, avoid, hit):
    assert collect_module.avoided(text, collect_module.phrases(avoid)) is hit


def test_avoid_list_filters_news(collect_module, offline, config):
    offline["news.google.com"] = rss(
        ("Software update fixes award page", "https://n.example/1", 1, "A"),
        ("Trade war escalates overnight", "https://n.example/2", 2, "B"),
        ("Football club signs striker", "https://n.example/3", 3, "C"))
    config["avoid"] = ["war"]
    config["sections"] = [dict(config["sections"][0], avoid=["football"])]
    news, _ = collect_module.collect_news(config, 48, NOW, set(), [], UTC)
    assert [n["title"] for n in news["tech"]] == ["Software update fixes award page"]


HISTORY_EVENTS = {"events": [
    {"year": 1945, "text": "The war ends with a peace treaty.", "pages": []},
    {"year": 1985, "text": "A software company releases its first hardware.", "pages": []}]}


def test_history_filters_nothing_by_default(collect_module, offline, config):
    offline["wikipedia.org"] = json.dumps(HISTORY_EVENTS)
    hist = collect_module.collect_history(dt.date(2026, 11, 13), config, [])
    assert len(hist) == 2


def test_history_respects_the_avoid_list(collect_module, offline, config):
    offline["wikipedia.org"] = json.dumps(HISTORY_EVENTS)
    config["avoid"] = ["war"]
    hist = collect_module.collect_history(dt.date(2026, 11, 13), config, [])
    assert [h["year"] for h in hist] == [1985]


def test_no_built_in_filter_list(collect_module):
    assert not hasattr(collect_module, "AVOID_HISTORY")


# ---------------------------------------------------------------- weather

WTTR = {"weather": [{"maxtempC": "27", "mintempC": "17", "hourly": [
    {"chanceofrain": "10", "weatherDesc": [{"value": "Sunny"}]},
    {"chanceofrain": "40", "weatherDesc": [{"value": "Light rain"}], "lang_pt": [{"value": "Chuva fraca"}]}]}]}


def test_weather_from_wttr(collect_module, offline, config):
    offline["wttr.in"] = json.dumps(WTTR)
    w, errors = collect_module.collect_weather(config)
    assert errors == []
    assert (w["max"], w["min"], w["rain_chance"], w["icon"]) == (27, 17, 40, "rain")
    assert w["url"].startswith("https://")


def test_weather_falls_back_to_open_meteo(collect_module, offline, config):
    offline["wttr.in"] = OSError("down")
    offline["open-meteo.com"] = json.dumps({"daily": {
        "temperature_2m_max": [26.6], "temperature_2m_min": [15.2], "weathercode": [3],
        "precipitation_probability_max": [5]}})
    w, errors = collect_module.collect_weather(config)
    assert len(errors) == 1 and "wttr.in" in errors[0]
    assert (w["max"], w["min"], w["icon"]) == (27, 15, "cloud")


def test_no_city_is_not_a_failure(collect_module, config):
    config.pop("city")
    assert collect_module.collect_weather(config) == (None, [])


# ---------------------------------------------------------------- on this day

def test_history_prefers_keywords_and_skips_used(collect_module, offline, config):
    page = {"content_urls": {"desktop": {"page": "https://en.wikipedia.org/wiki/X"}}}
    offline["wikipedia.org"] = json.dumps({"events": [
        {"year": 1950, "text": "A bridge opens to traffic.", "pages": [page]},
        {"year": 1971, "text": "The first email is sent between two computers.", "pages": [page]},
        {"year": 1999, "text": "A famous painting is restored.", "pages": [page]}]})
    hist = collect_module.collect_history(dt.date(2026, 11, 13), config, ["A famous painting is restored."])
    assert hist[0]["text"].startswith("The first email")  # matches "computer" keyword
    assert all("painting" not in h["text"] for h in hist)
    assert [h["id"] for h in hist] == [f"h{i}" for i in range(1, len(hist) + 1)]


# ---------------------------------------------------------------- whole run

def test_main_writes_collected_json(tmp_path, config):
    """Runs the real script in a subprocess with the network switched off inside it."""
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps(config), encoding="utf-8")
    runner = tmp_path / "run.py"
    runner.write_text(
        "import runpy, sys, urllib.request\n"
        "def no_net(*a, **k): raise OSError('offline test')\n"
        "urllib.request.urlopen = no_net\n"
        f"sys.argv = ['collect.py', '--config', {str(cfg)!r}, '--work', {str(tmp_path / 'work')!r}, '--date', '2026-11-13']\n"
        f"runpy.run_path({str(ROOT / 'morning-newspaper' / 'scripts' / 'collect.py')!r}, run_name='__main__')\n",
        encoding="utf-8")
    proc = subprocess.run([sys.executable, str(runner)], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    out = json.loads((tmp_path / "work" / "collected.json").read_text(encoding="utf-8"))
    assert out["date"] == "2026-11-13"
    assert out["window_hours"] == 48
    assert set(out["news"]) == {s["id"] for s in config["sections"]}
    assert out["failures"], "offline run must record its failures"
    assert "NETWORK BLOCKED" in proc.stdout  # nothing reachable: one clear line instead of the list


def run_collect(tmp_path, config, net_code):
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps(config), encoding="utf-8")
    runner = tmp_path / "run.py"
    runner.write_text(
        "import runpy, sys, urllib.request, urllib.error\n" + net_code +
        f"sys.argv = ['collect.py', '--config', {str(cfg)!r}, '--work', {str(tmp_path / 'work')!r}, '--date', '2026-11-13']\n"
        f"runpy.run_path({str(ROOT / 'morning-newspaper' / 'scripts' / 'collect.py')!r}, run_name='__main__')\n",
        encoding="utf-8")
    proc = subprocess.run([sys.executable, str(runner)], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    return proc, json.loads((tmp_path / "work" / "collected.json").read_text(encoding="utf-8"))


def test_blocked_network_is_reported_in_one_line(tmp_path, config):
    proc, out = run_collect(tmp_path, config,
                            "def no_net(*a, **k): raise urllib.error.URLError('blocked')\n"
                            "urllib.request.urlopen = no_net\n")
    assert "NETWORK BLOCKED" in proc.stdout
    assert "FAILURES:" not in proc.stdout
    assert out["network_blocked"] is True


def test_partial_failure_is_not_a_blocked_network(tmp_path, config):
    """Only Wikipedia answers: the other failures are listed and the edition goes on normally."""
    wiki = json.dumps({"events": [{"year": 1990, "text": "A web page goes online.", "pages": []}]})
    proc, out = run_collect(tmp_path, config,
                            "import io\n"
                            f"BODY = {wiki!r}.encode()\n"
                            "class R(io.BytesIO):\n"
                            "    def __enter__(self): return self\n"
                            "    def __exit__(self, *a): pass\n"
                            "def net(req, timeout=None):\n"
                            "    if 'wikipedia.org' in req.full_url: return R(BODY)\n"
                            "    raise urllib.error.URLError('down')\n"
                            "urllib.request.urlopen = net\n")
    assert "NETWORK BLOCKED" not in proc.stdout
    assert "FAILURES:" in proc.stdout
    assert out["network_blocked"] is False and out["history"]


# ---------------------------------------------------------------- hints for the model (v1.3)

@pytest.mark.parametrize("a, b, hint", [
    ("Paralisação de voos nos EUA deixa milhares sem embarque", "Estados Unidos suspendem voos após pane", True),
    ("Galípolo: baixar juros é um desafio pedagógico",
     "Presidente do BC, Galípolo resiste à pressão por cortes de juros", True),
    ("Google lança Gemini 4 Hydrogen, IA gratuita", "Google lança Pixel 11 com nova câmera", False),
    ("Copom mantém Selic em 15%", "Caixa estuda subir juros da casa própria", False),
])
def test_related_marks_the_same_fact_in_other_words(collect_module, a, b, hint):
    assert collect_module.related(a, b) is hint


@pytest.mark.parametrize("title, outlet, junk", [
    ("- Jornal Panorama", "Jornal Panorama Minas", True),
    ("Jornal Panorama", "Jornal Panorama", True),
    ("", "Any", True),
    ("Prefeitura abre vagas na saúde", "Jornal Panorama", False),
])
def test_junk_titles(collect_module, title, outlet, junk):
    assert collect_module.junk_title(title, outlet) is junk


@pytest.mark.parametrize("title, flagged", [
    ("IPCA: inflação oficial fecha junho com índice de 0,16%", True),
    ("Inflação de outubro surpreende", False),
    ("Feira volta em dezembro", False),
    ("May sales rise", False),          # "May" is too common an English word to count
    ("Prices fell in March", True),
])
def test_other_month(collect_module, title, flagged):
    assert collect_module.other_month(title, dt.date(2026, 11, 13)) is flagged


def test_feed_drops_junk_and_trailing_dash(collect_module, offline):
    offline["feed.example"] = rss(("- Jornal Panorama", "https://n.example/1", 1, "Jornal Panorama Minas"),
                                  ("Ponte reaberta no centro -", "https://n.example/2", 1, None))
    assert [i["title"] for i in collect_module.read_rss("https://feed.example/rss")] == ["Ponte reaberta no centro"]


def test_collect_news_flags_twins_old_months_and_the_city(collect_module, offline, config):
    config["city"]["name"] = "Lagoa da Prata"
    config["sections"] = [dict(config["sections"][1], queries=['"Lagoa da Prata"'])]
    offline["news.google.com"] = rss(
        ("Festa em Divinópolis reúne milhares", "https://n.example/1", 1, "A"),
        ("Oito foragidos presos no Centro-Oeste de Minas", "https://n.example/2", 2, "B"),
        ("Polícia captura foragidos no Centro-Oeste mineiro", "https://n.example/3", 3, "C"),
        ("IPCA fecha junho em alta", "https://n.example/4", 4, "D"),
        ("TJMG visita Cejusc de Lagoa da Prata", "https://n.example/5", 5, "E"))
    news, _ = collect_module.collect_news(config, 48, NOW, set(), [], UTC)
    items = news["local"]
    assert items[0]["title"] == "TJMG visita Cejusc de Lagoa da Prata"  # names the city: listed first
    assert "city" in items[0]["flags"]
    by_title = {n["title"]: n for n in items}
    first = by_title["Oito foragidos presos no Centro-Oeste de Minas"]["id"]
    assert by_title["Polícia captura foragidos no Centro-Oeste mineiro"]["same_as"] == first
    assert "old month?" in by_title["IPCA fecha junho em alta"]["flags"]


def test_history_flags_flattened_numbers(collect_module, offline, config):
    offline["wikipedia.org"] = json.dumps({"events": [
        {"year": 1996, "text": "Descoberto o primo de Mersenne 21398269−1.", "pages": []}]})
    assert collect_module.collect_history(dt.date(2026, 11, 13), config, [])[0]["check_numbers"] is True


def test_reissue_does_not_repeat_the_morning_extras(tmp_path, collect_module, config, offline, monkeypatch):
    """The morning's own "On this day" is skipped by an evening reissue of the same date."""
    index = {"editions": [{"date": "2026-11-13", "number": 3,
                           "extras": {"history": "Em 1996, o GIMPS achou um primo de Mersenne.", "did_you_know": "hello"}}]}
    offline["wikipedia.org"] = json.dumps({"events": [
        {"year": 1996, "text": "Em 1996, o GIMPS achou um primo de Mersenne.", "pages": []},
        {"year": 1971, "text": "Lançada a sonda Mariner 9.", "pages": []}]})
    offline["news.google.com"] = rss()
    offline["wttr.in"] = OSError("offline")
    cfg = tmp_path / "config.json"
    config["city"] = {}
    cfg.write_text(json.dumps(config), encoding="utf-8")
    idx = tmp_path / "index.json"
    idx.write_text(json.dumps(index), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["collect.py", "--config", str(cfg), "--work", str(tmp_path / "w"),
                                      "--index", str(idx), "--date", "2026-11-13"])
    collect_module.main()
    out = json.loads((tmp_path / "w" / "collected.json").read_text(encoding="utf-8"))
    assert out["reissue"] and out["number"] == 3
    assert [h["text"] for h in out["history"]] == ["Lançada a sonda Mariner 9."]
    assert out["did_you_know_used"] == ["hello"]


def test_unwritable_work_folder_is_a_clear_error(tmp_path, config):
    blocker = tmp_path / "file"
    blocker.write_text("x")
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps(config), encoding="utf-8")
    proc = subprocess.run([sys.executable, str(ROOT / "morning-newspaper" / "scripts" / "collect.py"),
                           "--config", str(cfg), "--work", str(blocker / "work")],
                          capture_output=True, text=True)
    assert proc.returncode == 2 and "ERROR: cannot write" in proc.stdout and "Traceback" not in proc.stderr
