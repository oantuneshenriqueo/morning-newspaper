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
    assert out["failures"], "offline run must report its failures"
    assert "FAILURES:" in proc.stdout
