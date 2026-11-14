#!/usr/bin/env python3
"""Automatic news-gathering for the morning-newspaper skill.

In one pass, without spending model tokens, it fetches:
  - candidate stories per section (Google News RSS searches + direct RSS feeds from config.json),
    already filtered by date window, with stories from recent editions removed, taking turns
    between the searches so one busy search cannot crowd out the others;
  - today's weather forecast (wttr.in, with Open-Meteo as a fallback);
  - "On this day" candidates (Wikipedia, in the reader's language when available).

It writes everything to WORK/collected.json (used later by assemble.py) and prints a compact
summary with a short ID per story (a1, b3, ...; h1... for history), which is what the model reads.

Standard library only. Only performs read-only GET requests to the hosts listed in the config
and to wttr.in, api.open-meteo.com and *.wikipedia.org. Only writes inside WORK.

Usage:
  python3 collect.py --config config.json --work WORK_DIR [--index index.json] [--date YYYY-MM-DD]
"""
import argparse
import concurrent.futures as cf
import datetime as dt
import email.utils
import html
import json
import os
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

try:
    from zoneinfo import ZoneInfo
except Exception:  # pragma: no cover
    ZoneInfo = None

UA = "morning-newspaper/1.3.2 (personal newspaper; RSS reader)"
TIMEOUT = 12
MAX_BYTES = 5_000_000
# Stories are only compared against the latest editions: a headline from months ago must not
# block today's news on a recurring subject (same number assemble.py keeps titles/links for).
DEDUP_EDITIONS = 14


# "Did you know?" rotates through one theme per day so the box does not keep landing on the same
# famous trivia. Readers can replace this list with "did_you_know_themes" in config.json.
DYK_THEMES = [
    "origin of a programming language", "how a piece of everyday hardware works inside",
    "history of a file format or protocol", "origin of a computing term (not 'bug')",
    "a curious record in computing", "early video game history", "how the internet's infrastructure works",
    "history of a famous algorithm", "cryptography and codes through history", "space missions and their computers",
    "history of a keyboard key or symbol", "how a common app feature was invented", "storage media history",
    "a programming convention and where it came from", "history of an operating system",
    "how GPS, Wi-Fi or Bluetooth works", "computing in your country's history", "open-source software history",
    "a surprising fact about electricity or batteries", "the science behind a screen technology",
    "history of artificial intelligence before 2000", "a famous software failure and its lesson",
    "units and numbers in computing (bytes, hertz, binary)", "the history of email or the web",
    "an invention that came from a game or a toy", "how data compression works",
    "history of the mouse, touchscreen or another input device", "a curiosity about databases",
    "the origin of a tech company's name", "how undersea cables or satellites carry data",
]


def dyk_theme(cfg, day):
    themes = cfg.get("did_you_know_themes") or DYK_THEMES
    return themes[day.toordinal() % len(themes)]


def tz_of(cfg):
    name = cfg.get("timezone") or "UTC"
    if ZoneInfo:
        try:
            return ZoneInfo(name)
        except Exception:
            pass
    return dt.timezone.utc


def fetch(url, tries=2):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    for n in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                return r.read(MAX_BYTES)
        except urllib.error.HTTPError as e:
            if n + 1 >= tries or e.code not in (429, 500, 502, 503, 504):
                raise
            time.sleep(2 + 2 * n)


def words(txt):
    txt = unicodedata.normalize("NFKD", txt or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9 ]+", " ", txt).split()


def clean(txt, limit=220):
    txt = html.unescape(re.sub(r"<[^>]+>", " ", txt or ""))
    txt = re.sub(r"\s+", " ", txt).strip()
    return txt if len(txt) <= limit else txt[: limit - 1].rsplit(" ", 1)[0] + "…"


def same_story(a, b):
    """Two titles tell the same story if they share most of their meaningful words."""
    pa = {p for p in words(a) if len(p) > 3}
    pb = {p for p in words(b) if len(p) > 3}
    if not pa or not pb:
        return False
    return len(pa & pb) / min(len(pa), len(pb)) >= 0.6


# Names a country goes by in different titles ("EUA", "Estados Unidos", "US"): folded into one
# token before comparing, so the same fact told with a different name is still recognized.
# Full names and unambiguous short forms match in any case:
ALIASES = [(r"\bestados unidos\b|\bunited states\b|\beeuu\b|\bee uu\b|\beua\b", " euaxx "),
           (r"\breino unido\b|\bunited kingdom\b|\buk\b", " ukxxx "),
           (r"\buniao europeia\b|\bunion europea\b|\beuropean union\b", " uexxx ")]
# Short forms that are also everyday words count only in capitals, and never in an all-caps title:
# "usa" (verb in Portuguese and Spanish), "us" (English pronoun), "eu" (Portuguese pronoun), "uê".
# "US$" is the dollar, not the country. In Spanish, "EU" is how Mexican outlets write Estados Unidos.
CAPS_US = r"\bU\.?S\.?(?:A\.?)?(?![\w.$])"
CAPS_EU = r"\bEU\b(?!\$)"
CAPS_UE = r"\bUE\b"
LANG = None  # reader's language (set in main); only changes what "EU" means


def all_caps(txt):
    letters = [ch for ch in txt or "" if ch.isalpha()]
    return len(letters) >= 8 and sum(ch.isupper() for ch in letters) / len(letters) > 0.8


# Words every headline uses, which say nothing about which fact it is.
COMMON = {"para", "apos", "sobre", "como", "mais", "deixa", "anuncia", "lanca", "novo", "nova", "novos", "novas",
          "pode", "podem", "sera", "desde", "durante", "contra", "segundo", "entre", "veja", "after", "with",
          "from", "over", "says", "launches", "announces", "will", "could", "tras", "tiene", "nuevo", "nueva",
          "anuncio", "despues", "este", "esta", "isso", "this", "that", "your", "seus", "suas"}


def stems(txt):
    """Meaningful words cut to their first 5 letters, so "paralisam" and "paralisação" match."""
    txt = txt or ""
    if not all_caps(txt):
        txt = re.sub(CAPS_US, " eua ", txt)
        txt = re.sub(CAPS_EU, " eua " if (LANG or "").startswith("es") else " uniao europeia ", txt)
        txt = re.sub(CAPS_UE, " uniao europeia ", txt)
    n = " " + " ".join(words(txt)) + " "
    for pat, rep in ALIASES:
        n = re.sub(pat, rep, n)
    return {w[:5] for w in n.split() if (len(w) > 3 and w not in COMMON) or w.isdigit()}


def related(a, b):
    """Looser than same_story: two titles that may tell the same fact in different words.
    Only a hint for the model (printed as ≈a1); nothing is dropped because of it."""
    pa, pb = stems(a), stems(b)
    if not pa or not pb:
        return False
    shared = pa & pb
    return len(shared) >= 2 and len(shared) / min(len(pa), len(pb)) >= 0.4


def junk_title(title, outlet):
    """Empty titles, or titles that are only the outlet's name ("- Jornal Panorama")."""
    t = (title or "").strip(" -–—|·:")
    tw = words(t)
    return not tw or set(tw) <= set(words(outlet)) or len(tw) < 2


MONTHS = {  # (lowercase names, accents kept) → month number; English needs a capital (not "May")
    **{m: i for i, m in enumerate(["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto",
                                   "setembro", "outubro", "novembro", "dezembro"], 1)},
    **{m: i for i, m in enumerate(["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
                                   "septiembre", "octubre", "noviembre", "diciembre"], 1)},
}
MONTHS_EN = {m: i for i, m in enumerate(["January", "February", "March", "April", "", "June", "July", "August",
                                         "September", "October", "November", "December"], 1) if m}


def other_month(title, day):
    """True if the title names a month that is not this one or a neighbour ("IPCA fecha junho" in
    November): the story is probably old or republished even though its timestamp is recent."""
    found = [MONTHS[w] for w in re.findall(r"\w+", (title or "").lower()) if w in MONTHS]
    found += [MONTHS_EN[w] for w in re.findall(r"\w+", title or "") if w in MONTHS_EN]
    near = {(day.month - 2) % 12 + 1, day.month, day.month % 12 + 1}
    return any(m not in near for m in found)


def names_city(text, city):
    c = " ".join(words(city))
    return bool(c) and f" {c} " in f" {' '.join(words(text))} "


def phrases(lst):
    """Reader's "avoid" list, normalized (lowercase, no accents) for whole-word matching."""
    return [" ".join(words(p)) for p in lst or [] if words(str(p))]


def avoided(text, avoid):
    """True if any avoided word or phrase appears in the text as whole words
    ("war" matches "the war ended", never "software")."""
    n = f" {' '.join(words(text))} "
    return any(f" {p} " in n for p in avoid)


def past_editions(index, day):
    """What recent editions already printed: (previous editions newest first, links, titles)."""
    editions = index.get("editions") or index.get("edicoes") or []
    previous = sorted((e for e in editions if (e.get("date") or e.get("data")) != day.isoformat()),
                      key=lambda e: e.get("date") or e.get("data") or "", reverse=True)
    recent = previous[:DEDUP_EDITIONS]
    links = {l for e in recent for l in e.get("links", [])}
    titles = [t for e in recent
              for t in [e.get("headline") or e.get("manchete") or "", *(e.get("titles") or e.get("titulos") or []),
                        *(e.get("source_titles") or [])] if t]
    return previous, links, titles


# ---------------------------------------------------------------- news

def google_news_url(query, days, loc):
    return "https://news.google.com/rss/search?" + urllib.parse.urlencode(
        {"q": f"{query} when:{days}d", "hl": loc.get("hl", "en-US"), "gl": loc.get("gl", "US"),
         "ceid": loc.get("ceid", "US:en")})


def read_rss(url):
    root = ET.fromstring(fetch(url))
    items = []
    for it in root.iter("item"):
        title = clean(it.findtext("title"), 300)
        link = (it.findtext("link") or "").strip()
        src = it.find("source")
        outlet = (src.text or "").strip() if src is not None else ""
        if outlet and title.endswith(" - " + outlet):  # Google News appends " - Outlet"
            title = title[: -len(" - " + outlet)]
        if not outlet:
            outlet = urllib.parse.urlparse(link).netloc.replace("www.", "")
        title = re.sub(r"\s+[-–—|]\s*$", "", title).strip()  # a trailing " -" left by the outlet
        if junk_title(title, outlet):
            continue
        when = None
        if it.findtext("pubDate"):
            try:
                when = email.utils.parsedate_to_datetime(it.findtext("pubDate"))
                if when.tzinfo is None:
                    when = when.replace(tzinfo=dt.timezone.utc)
            except Exception:
                when = None
        summary = clean(it.findtext("description"), 160)
        if summary and same_story(summary, title):
            summary = ""  # Google News descriptions usually repeat the title
        if title and link.startswith("https://"):
            items.append({"title": title, "outlet": outlet, "url": link, "date": when, "summary": summary})
    return items


def prefixes(sections):
    letters = [c for c in "abcdefgijklmnopqrstuvwxyz"]  # 'h' is reserved for history
    return {s["id"]: letters[i % len(letters)] for i, s in enumerate(sections)}


def collect_news(cfg, window_h, now, used_links, used_titles, tz):
    days = max(1, round(window_h / 24))
    loc = cfg.get("news_locale") or {}
    tasks = []
    for sec in cfg["sections"]:
        for q in sec.get("queries", []):
            tasks.append((sec["id"], google_news_url(q, days, loc)))
        for f in sec.get("feeds", []):
            if str(f).startswith("https://"):
                tasks.append((sec["id"], f))
    results = [[] for _ in tasks]
    failures = []
    with cf.ThreadPoolExecutor(max_workers=8) as ex:
        fut = {ex.submit(read_rss, u): i for i, (_, u) in enumerate(tasks)}
        for f in cf.as_completed(fut):
            sid, u = tasks[fut[f]]
            try:
                results[fut[f]] = f.result()
            except Exception as e:
                failures.append(f"{sid}: {urllib.parse.urlparse(u).netloc} ({type(e).__name__} {getattr(e, 'code', '')})".replace(" )", ")"))
    cutoff = now - dt.timedelta(hours=window_h)
    pre = prefixes(cfg["sections"])
    out = {}
    for sec in cfg["sections"]:
        sid = sec["id"]
        avoid = phrases(list(cfg.get("avoid") or []) + list(sec.get("avoid") or []))
        # One queue per search/feed, newest first, already cleared of old, repeated and avoided stories.
        queues = []
        for i, (task_sid, _) in enumerate(tasks):
            if task_sid != sid:
                continue
            ok = [it for it in results[i]
                  if it["date"] is not None and it["date"] >= cutoff and it["url"] not in used_links
                  and not avoided(f"{it['title']} {it['summary']}", avoid)
                  and not any(same_story(it["title"], t) for t in used_titles)]
            queues.append(sorted(ok, key=lambda x: x["date"], reverse=True))
        # Take turns: the newest story of each search, then the second of each, and so on.
        kept, limit, depth = [], sec.get("max_candidates", 10), 0
        while len(kept) < limit and any(depth < len(q) for q in queues):
            for q in queues:
                if depth < len(q) and len(kept) < limit:
                    it = q[depth]
                    if not any(it["url"] == k["url"] or same_story(it["title"], k["title"]) for k in kept):
                        kept.append(it)
            depth += 1
        kept.sort(key=lambda x: x["date"], reverse=True)
        # Local sections of a small town fill up with the region: the stories that name the city
        # itself come first, so a busy neighbouring town cannot push them out of sight.
        city = (cfg.get("city") or {}).get("name", "")
        if city and any(names_city(q, city) for q in sec.get("queries", [])):
            kept.sort(key=lambda x: not names_city(x["title"], city))
        items = []
        for i, it in enumerate(kept, 1):
            n = {"id": f"{pre[sid]}{i}", "title": it["title"], "outlet": it["outlet"], "url": it["url"],
                 "date": it["date"].astimezone(tz).strftime("%Y-%m-%d %H:%M"), "summary": it["summary"]}
            flags = []
            earlier = [p for lst in out.values() for p in lst] + items  # other sections count too
            twin = next((p["id"] for p in earlier if related(it["title"], p["title"])), None)
            if twin:
                n["same_as"] = twin
                flags.append(f"≈{twin}")
            if other_month(it["title"], now.date()):
                flags.append("old month?")
            if city and names_city(it["title"], city):
                flags.append("city")
            if flags:
                n["flags"] = flags
            items.append(n)
        out[sid] = items
    return out, failures


# ---------------------------------------------------------------- weather

def icon_from_text(t):
    t = " ".join(words(t))
    if any(k in t for k in ("thunder", "trovoad", "tempestade", "tormenta")):
        return "storm"
    if any(k in t for k in ("rain", "drizzle", "shower", "chuv", "garoa", "lluvia", "llovizna")):
        return "rain"
    if any(k in t for k in ("partly", "parcial", "poucas nuvens", "parcialmente")):
        return "sun-cloud"
    if any(k in t for k in ("cloud", "overcast", "fog", "mist", "nubl", "encoberto", "nuvens", "nevoeiro",
                            "neblina", "nublado", "niebla")):
        return "cloud"
    return "sun"


WMO = {0: ("Clear sky", "sun"), 1: ("Mainly clear", "sun-cloud"), 2: ("Partly cloudy", "sun-cloud"),
       3: ("Overcast", "cloud"), 45: ("Fog", "cloud"), 48: ("Fog", "cloud"), 51: ("Drizzle", "rain"),
       53: ("Drizzle", "rain"), 55: ("Heavy drizzle", "rain"), 61: ("Light rain", "rain"), 63: ("Rain", "rain"),
       65: ("Heavy rain", "rain"), 80: ("Rain showers", "rain"), 81: ("Rain showers", "rain"),
       82: ("Heavy showers", "rain"), 95: ("Thunderstorms", "storm"), 96: ("Thunderstorms with hail", "storm"),
       99: ("Thunderstorms with hail", "storm")}


def weather_wttr(city, lang):
    name = urllib.parse.quote(city["name"].replace(" ", "+"), safe="+")
    d = json.loads(fetch(f"https://wttr.in/{name}?format=j1&lang={lang}"))
    today = d["weather"][0]
    noon = today["hourly"][min(4, len(today["hourly"]) - 1)]
    cond = (noon.get(f"lang_{lang}") or [{}])[0].get("value") or noon["weatherDesc"][0]["value"]
    rain = max(int(h.get("chanceofrain", 0)) for h in today["hourly"])
    return {"max": int(today["maxtempC"]), "min": int(today["mintempC"]), "condition": cond.strip().capitalize(),
            "rain_chance": rain, "icon": icon_from_text(cond), "url": "https://wttr.in/" + name,
            "condition_lang": lang if noon.get(f"lang_{lang}") else "en"}


def weather_open_meteo(city, tzname):
    q = urllib.parse.urlencode({"latitude": city["latitude"], "longitude": city["longitude"],
                                "daily": "temperature_2m_max,temperature_2m_min,weathercode,precipitation_probability_max",
                                "timezone": tzname, "forecast_days": 1})
    d = json.loads(fetch("https://api.open-meteo.com/v1/forecast?" + q))["daily"]
    cond, ic = WMO.get(int(d["weathercode"][0]), ("Variable", "sun-cloud"))
    return {"max": round(d["temperature_2m_max"][0]), "min": round(d["temperature_2m_min"][0]), "condition": cond,
            "rain_chance": d.get("precipitation_probability_max", [None])[0], "icon": ic,
            "url": "https://open-meteo.com/", "condition_lang": "en"}


def collect_weather(cfg):
    city = cfg.get("city") or {}
    if not city.get("name"):
        return None, []  # no city configured (e.g. sample edition): not a failure
    lang = (cfg.get("language") or "en").split("-")[0]
    errors = []
    try:
        return weather_wttr(city, lang), errors
    except Exception as e:
        errors.append(f"weather: wttr.in ({type(e).__name__})")
    if "latitude" in city and "longitude" in city:
        try:
            return weather_open_meteo(city, cfg.get("timezone") or "UTC"), errors
        except Exception as e:
            errors.append(f"weather: open-meteo ({type(e).__name__})")
    return None, errors


# ---------------------------------------------------------------- on this day

def collect_history(day, cfg, used):
    lang = re.sub(r"[^a-z]", "", (cfg.get("wikipedia_lang") or (cfg.get("language") or "en").split("-")[0]).lower()) or "en"
    url = f"https://{lang}.wikipedia.org/api/rest_v1/feed/onthisday/events/{day:%m}/{day:%d}"
    d = json.loads(fetch(url))
    pref = [" ".join(words(p)) for p in cfg.get("history_keywords", [])]
    used_n = [" ".join(words(u)) for u in used if u]
    avoid = phrases(cfg.get("avoid"))  # nothing is filtered unless the reader asked for it
    cands = []
    for ev in d.get("events", []):
        txt = clean(ev.get("text", ""), 260)
        n = " ".join(words(txt))
        if not txt or avoided(txt, avoid):
            continue
        if any(u and (n in u or u in n or same_story(n, u)) for u in used_n):
            continue
        page = (ev.get("pages") or [{}])[0]
        link = ((page.get("content_urls") or {}).get("desktop") or {}).get("page", "")
        c = {"year": ev.get("year"), "text": txt, "url": link, "score": sum(1 for p in pref if p and p in n)}
        if re.search(r"\d{7,}", txt):
            c["check_numbers"] = True  # a flattened exponent or formula (2^1398269−1 → "21398269−1")
        cands.append(c)
    cands.sort(key=lambda c: (-c["score"], -(c["year"] or 0)))
    return [{"id": f"h{i}", **{k: v for k, v in c.items() if k != "score"}} for i, c in enumerate(cands[:6], 1)]


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True, help="reader's config.json")
    ap.add_argument("--work", required=True, help="working folder for this edition")
    ap.add_argument("--index", help="current editions/index.json from the newsstand, if any")
    ap.add_argument("--date", help="YYYY-MM-DD (default: today in the reader's timezone)")
    a = ap.parse_args()

    # Check the working folder before spending a minute on the network.
    try:
        os.makedirs(a.work, exist_ok=True)
        with open(os.path.join(a.work, "collected.json"), "a", encoding="utf-8"):
            pass
    except OSError as e:
        print(f"ERROR: cannot write to the working folder {a.work} ({type(e).__name__}). "
              "Use a temporary folder (mktemp -d) as WORK; if none can be written, tell the reader.")
        return 2
    with open(a.config, encoding="utf-8") as f:
        cfg = json.load(f)
    global LANG
    LANG = str(cfg.get("language") or "").lower()
    tz = tz_of(cfg)
    now = dt.datetime.now(tz)
    day = dt.date.fromisoformat(a.date) if a.date else now.date()

    index = {"editions": []}
    if a.index and os.path.exists(a.index):
        with open(a.index, encoding="utf-8") as f:
            index = json.load(f)
    editions = index.get("editions") or index.get("edicoes") or []
    previous, used_links, used_titles = past_editions(index, day)
    # Extras of every edition, today's too: a reissue must not repeat the morning's
    # "On this day" or "Did you know?" (its stories may come back; its extras should not).
    extras = [(e.get("extras") or {}) for e in sorted(editions, key=lambda e: e.get("date") or e.get("data") or "",
                                                       reverse=True)]
    used_history = [x.get("history") or x.get("historia") or "" for x in extras]
    used_didyouknow = [x.get("did_you_know") or x.get("voce_sabia") or "" for x in extras]

    weekend = day.weekday() >= 5
    window = 72 if day.weekday() in (0, 5, 6) else 48
    number = max([e.get("number") or e.get("numero") or 0 for e in previous] + [0]) + 1
    reissue = next((e.get("number") or e.get("numero") for e in editions
                    if (e.get("date") or e.get("data")) == day.isoformat()), None)

    news, failures = collect_news(cfg, window, now, used_links, used_titles, tz)
    weather, wf = collect_weather(cfg)
    failures += wf
    try:
        history = collect_history(day, cfg, used_history)
    except Exception as e:
        history = []
        failures.append(f"history: wikipedia ({type(e).__name__} {getattr(e, 'code', '')})".replace(" )", ")"))

    # Nothing at all could be reached (Claude's network access is off or limited): say it in one
    # line so the model switches to the no-network mode instead of reading a dozen failures.
    blocked = bool(failures) and not any(news.values()) and weather is None and not history
    out = {"date": day.isoformat(), "number": reissue or number, "reissue": bool(reissue), "weekend": weekend,
           "window_hours": window, "weather": weather, "news": news, "history": history,
           "did_you_know_theme": dyk_theme(cfg, day),
           "did_you_know_used": [s for s in used_didyouknow if s][:30], "failures": failures,
           "network_blocked": blocked,
           "generated_at": now.isoformat(timespec="minutes")}
    with open(os.path.join(a.work, "collected.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)

    # Compact summary for the model (no long URLs: assemble.py resolves them by ID)
    print(f"# {day.isoformat()} ({day.strftime('%A')}) · issue {out['number']}{' (reissue)' if reissue else ''}"
          f"{' · WEEKEND' if weekend else ''} · window {window}h · language {cfg.get('language', 'en')}")
    if weather:
        print(f"WEATHER: {weather['max']}°/{weather['min']}° {weather['condition']} [{weather['condition_lang']}]"
              f" · rain {weather['rain_chance']}% · icon {weather['icon']}")
    elif not (cfg.get("city") or {}).get("name"):
        print("WEATHER: no city configured (leave the weather out)")
    else:
        print("WEATHER: unavailable")
    if any(n.get("flags") for lst in news.values() for n in lst):
        print("FLAGS: ≈a1 = maybe the same fact as a1 (keep one) · old month? = the title names another"
              " month (likely old news) · city = names the reader's city")
    for sec in cfg["sections"]:
        print(f"\n[{sec['id']}] {sec['title']}")
        for n in news.get(sec["id"], []):
            line = f"{n['id']} | {n['date'][5:]} | {n['outlet']} | {n['title']}"
            if n["summary"]:
                line += f" — {n['summary']}"
            if n.get("flags"):
                line += f" [{', '.join(n['flags'])}]"
            print(line)
        if not news.get(sec["id"]):
            print("(nothing new)")
    print("\n[history]")
    for h in history:
        print(f"{h['id']} | {h['year']} | {h['text']}"
              + (" [check the numbers on the linked page]" if h.get("check_numbers") else ""))
    print(f"\n[did_you_know] today's theme: {out['did_you_know_theme']}")
    if out["did_you_know_used"]:
        print("[did_you_know already used] " + " / ".join(out["did_you_know_used"][:15]))
    if blocked:
        print("\nNETWORK BLOCKED: no source could be reached. Follow 'No network' in SKILL.md.")
    elif failures:
        print("\nFAILURES: " + "; ".join(failures))
    return 0


if __name__ == "__main__":
    sys.exit(main())
