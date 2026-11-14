#!/usr/bin/env python3
"""Builds an edition of the morning newspaper from a short JSON written by the model.

Inputs: WORK/edition.json (format in references/edition-format.md), WORK/collected.json
(from collect.py) and the reader's config.json. Stories can point at collected items by ID
("ref": "a3"); the script fills in URL, outlet and date by itself.

Output, if every check passes:
  WORK/archive/editions/YYYY-MM-DD.html
  WORK/archive/editions/index.json     (previous index + the new entry on top)
  WORK/archive/index.html              (when the newsstand is new or legacy, or with --with-page)
  WORK/archive/config.json             (when the newsstand is new or legacy, or with --with-config)
and the list of files to publish. With --standalone (a test or a copy that is not going to the
newsstand) or --share (a copy to show other people) it writes only WORK/standalone/YYYY-MM-DD.html:
no newsstand button, and the index is left untouched.
If anything fails it prints the errors, writes nothing and exits 1.

Standard library only. No network access.
Usage:
  python3 assemble.py --skill SKILL_DIR --config config.json --work WORK_DIR [--index index.json]
                      [--with-config] [--with-page] [--sample] [--standalone | --share]
"""
import argparse
import datetime as dt
import html
import json
import os
import re
import shutil
import sys

try:
    from zoneinfo import ZoneInfo
except Exception:  # pragma: no cover
    ZoneInfo = None

_S = 'stroke="#1E1B16" stroke-width="1.5" fill="none" stroke-linecap="round" stroke-linejoin="round"'
SVG_WEATHER = {
    "sun": f'<circle cx="22" cy="22" r="9" fill="#C8901E" stroke="#1E1B16" stroke-width="1.5"/><path d="M22 4v5M22 35v5M4 22h5M35 22h5M9 9l3.5 3.5M31.5 31.5L35 35M9 35l3.5-3.5M31.5 12.5L35 9" {_S}/>',
    "sun-cloud": '<circle cx="17" cy="16" r="9" fill="#C8901E" stroke="#1E1B16" stroke-width="1.5"/><path d="M12 34h22a7 7 0 0 0 0-14 9 9 0 0 0-17 3 6 6 0 0 0-5 11z" fill="#FBF6EC" stroke="#1E1B16" stroke-width="1.5"/>',
    "cloud": '<path d="M9 32h25a8 8 0 0 0 0-16 10 10 0 0 0-19 3 7 7 0 0 0-6 13z" fill="#FBF6EC" stroke="#1E1B16" stroke-width="1.5"/>',
    "rain": f'<path d="M9 26h25a8 8 0 0 0 0-16 10 10 0 0 0-19 3 7 7 0 0 0-6 13z" fill="#FBF6EC" stroke="#1E1B16" stroke-width="1.5"/><path d="M14 31l-2 6M22 31l-2 6M30 31l-2 6" {_S}/>',
    "storm": f'<path d="M9 26h25a8 8 0 0 0 0-16 10 10 0 0 0-19 3 7 7 0 0 0-6 13z" fill="#FBF6EC" stroke="#1E1B16" stroke-width="1.5"/><path d="M23 28l-4 7h5l-3 7" {_S}/>',
}
SVG_ICON = {
    "lock": f'<rect x="14" y="26" width="28" height="22" {_S}/><path d="M19 26v-7a9 9 0 0 1 18 0v7M28 34v6" {_S}/>',
    "chip": f'<rect x="16" y="16" width="24" height="24" {_S}/><rect x="22" y="22" width="12" height="12" {_S}/><path d="M22 10v6M28 10v6M34 10v6M22 40v6M28 40v6M34 40v6M10 22h6M10 28h6M10 34h6M40 22h6M40 28h6M40 34h6" {_S}/>',
    "coin": f'<circle cx="28" cy="28" r="17" {_S}/><circle cx="28" cy="28" r="12" {_S}/><path d="M32 22h-6a3 3 0 0 0 0 6h4a3 3 0 0 1 0 6h-6M28 19v3M28 34v3" {_S}/>',
    "chart": f'<path d="M10 46h36M10 46V10" {_S}/><path d="M14 38l9-10 7 6 12-15" {_S}/><path d="M36 19h6v6" {_S}/>',
    "gamepad": f'<path d="M14 22h28a8 8 0 0 1 8 8l-2 10a5 5 0 0 1-9 2l-3-5H20l-3 5a5 5 0 0 1-9-2L6 30a8 8 0 0 1 8-8z" {_S}/><path d="M16 29v6M13 32h6" {_S}/><circle cx="38" cy="30" r="1.5" fill="#1E1B16"/><circle cx="42" cy="34" r="1.5" fill="#1E1B16"/>',
    "city": f'<path d="M8 46h40M12 46V24h10v22M22 46V14h12v32M34 46V28h10v18" {_S}/><path d="M16 29h2M16 35h2M26 19h4M26 25h4M26 31h4M38 33h2M38 39h2" {_S}/>',
    "robot": f'<rect x="14" y="20" width="28" height="22" {_S}/><path d="M28 12v8M10 28v8M46 28v8M22 36h12" {_S}/><circle cx="28" cy="11" r="2" {_S}/><circle cx="22" cy="29" r="2.5" {_S}/><circle cx="34" cy="29" r="2.5" {_S}/>',
    "newspaper": f'<rect x="10" y="12" width="36" height="32" {_S}/><path d="M16 20h24M16 26h10M16 32h10M16 38h10M30 26h10v12H30z" {_S}/>',
}


# Older newsstands wrote the index in Portuguese (edicoes/indice.json). Entries are always
# rewritten with the current keys, so an index never mixes the two spellings.
LEGACY_INDEX_KEYS = ("edicoes", "fundado_em", "jornal")
LEGACY_KEYS = {"data": "date", "numero": "number", "dia_semana": "weekday", "tipo": "type", "manchete": "headline",
               "resumo": "summary", "arquivo": "file", "titulos": "titles"}
LEGACY_EXTRAS = {"historia": "history", "voce_sabia": "did_you_know"}
LEGACY_TYPES = {"fim de semana": "weekend", "manhã": "morning", "manha": "morning", "amostra": "sample"}
DEDUP_EDITIONS = 14  # titles/links only exist to avoid repeats: kept for the latest editions only


def _renamed(d, table):
    out = {table[k]: v for k, v in d.items() if k in table}
    out.update({k: v for k, v in d.items() if k not in table})  # a current key wins over its legacy twin
    return out


def normalize_entry(e):
    out = _renamed(e, LEGACY_KEYS)
    if isinstance(out.get("extras"), dict):
        out["extras"] = _renamed(out["extras"], LEGACY_EXTRAS)
    if out.get("type") in LEGACY_TYPES:
        out["type"] = LEGACY_TYPES[out["type"]]
    return out


def svg(drawing, size):
    return f'<svg width="{size}" height="{size}" viewBox="0 0 {size} {size}" aria-hidden="true">{drawing}</svg>'


def roman(n):
    out = ""
    for v, s in ((1000, "M"), (900, "CM"), (500, "D"), (400, "CD"), (100, "C"), (90, "XC"),
                 (50, "L"), (40, "XL"), (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")):
        while n >= v:
            out += s
            n -= v
    return out


def esc(v):
    return html.escape(str(v), quote=True)


def word_count(t):
    return len(re.findall(r"\w+", t or ""))


def long_quotes(t):
    return [c for c in re.findall(r"[\"“«]([^\"”»]+)[\"”»]", t or "") if word_count(c) >= 15]


def load_labels(skill, cfg):
    lang = cfg.get("language") or "en"
    folder = os.path.join(skill, "assets", "i18n")
    with open(os.path.join(folder, "en.json"), encoding="utf-8") as f:
        labels = json.load(f)
    for cand in (lang.split("-")[0], lang):
        p = os.path.join(folder, f"{cand}.json")
        if os.path.exists(p):
            with open(p, encoding="utf-8") as f:
                labels.update(json.load(f))
    labels.update(cfg.get("labels") or {})
    labels.setdefault("html_lang", lang)
    return labels


def render(template, ctx, lists):
    template = re.sub(r"<!-- Template filled.*?-->\n", "", template, flags=re.S)

    def each(m):
        name, inner = m.group(1), m.group(2)
        parts = []
        for item in lists.get(name, []):
            block = re.sub(r"<!--IF:(\w+)-->(.*?)<!--/IF:\1-->",
                           lambda s: s.group(2) if item.get(s.group(1)) else "", inner, flags=re.S)
            block = re.sub(r"\{\{(\w+)\}\}", lambda p: esc(item.get(p.group(1), "")), block)
            parts.append(block)
        return "".join(parts)

    out = re.sub(r"<!--EACH:(\w+)-->(.*?)<!--/EACH:\1-->", each, template, flags=re.S)
    for _ in range(3):
        out = re.sub(r"<!--IF:(\w+)-->(.*?)<!--/IF:\1-->",
                     lambda s: s.group(2) if ctx.get(s.group(1)) else "", out, flags=re.S)
    out = re.sub(r"\{\{\{(\w+)\}\}\}", lambda p: str(ctx.get(p.group(1), "")), out)
    out = re.sub(r"\{\{(\w+)\}\}", lambda p: esc(ctx.get(p.group(1), "")), out)
    return re.sub(r"\n{3,}", "\n\n", out)


def story_html(n, L, tag):
    return (f'<{tag} class="display">{esc(n["title"])}</{tag}>\n'
            f'<p>{esc(n["text"])} <a href="{esc(n["url"])}" target="_blank" rel="noopener">'
            f'{esc(L["source"])}: {esc(n["outlet"])}</a></p>\n')


def sections_html(cfg, sections, L):
    """Renders configured sections in order: 'main' = wide two-column grid, 'half' = paired
    side by side with the next 'half', 'single' (or an unpaired half) = full-width box."""
    out, pending_half = [], None

    def single(sec, items):
        body = "".join(story_html(n, L, "h3") for n in items)
        return f'<section class="solo">\n<div class="sub-titulo sc">{esc(sec["title"])}</div>\n{body}</section>\n'

    def flush():
        nonlocal pending_half
        if pending_half:
            out.append(single(*pending_half))
            pending_half = None

    for sec in cfg["sections"]:
        items = sections.get(sec["id"]) or []
        if not items:
            continue
        layout = sec.get("layout", "single")
        if layout == "main":
            flush()
            arts = "".join(f'<article class="noticia">\n{story_html(n, L, "h2")}</article>\n' for n in items)
            out.append(f'<section>\n<div class="secao-titulo sc">{esc(sec["title"])}</div>\n'
                       f'<div class="noticias">\n{arts}</div>\n</section>\n')
        elif layout == "half":
            if pending_half:
                a_sec, a_items = pending_half
                cols = ""
                for s, its in ((a_sec, a_items), (sec, items)):
                    cols += (f'<div>\n<div class="sub-titulo sc">{esc(s["title"])}</div>\n'
                             + "".join(story_html(n, L, "h3") for n in its) + '</div>\n')
                out.append(f'<div class="par">\n{cols}</div>\n')
                pending_half = None
            else:
                pending_half = (sec, items)
        else:
            flush()
            out.append(single(sec, items))
    flush()
    return "".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skill", required=True)
    ap.add_argument("--config", required=True)
    ap.add_argument("--work", required=True)
    ap.add_argument("--index", help="current index.json of the newsstand; omit if it does not exist yet")
    ap.add_argument("--with-config", action="store_true", help="also write config.json into the output to publish")
    ap.add_argument("--with-page", action="store_true", help="also write index.html (the newsstand page) into the output to publish")
    ap.add_argument("--sample", action="store_true",
                    help="sample edition for a reader with no setup yet: adds the setup notice and never publishes config.json")
    ap.add_argument("--standalone", action="store_true",
                    help="a single page that is not added to the newsstand (test or 'don't publish')")
    ap.add_argument("--share", action="store_true",
                    help="like --standalone, for showing other people: says on the page what was left out")
    a = ap.parse_args()
    standalone = a.standalone or a.share

    errors, warnings = [], []
    with open(a.config, encoding="utf-8") as f:
        cfg = json.load(f)
    with open(os.path.join(a.work, "edition.json"), encoding="utf-8") as f:
        ed = json.load(f)
    collected = {}
    cpath = os.path.join(a.work, "collected.json")
    if os.path.exists(cpath):
        with open(cpath, encoding="utf-8") as f:
            collected = json.load(f)
    refs = {n["id"]: n for lst in (collected.get("news") or {}).values() for n in lst}
    refs.update({h["id"]: h for h in collected.get("history") or []})
    L = load_labels(a.skill, cfg)
    tz = dt.timezone.utc
    if ZoneInfo:
        try:
            tz = ZoneInfo(cfg.get("timezone") or "UTC")
        except Exception:
            pass

    index = None
    if a.index and os.path.exists(a.index):
        with open(a.index, encoding="utf-8") as f:
            index = json.load(f)
    legacy = bool(index) and any(k in index for k in LEGACY_INDEX_KEYS)
    old = [normalize_entry(e) for e in (index or {}).get("editions") or (index or {}).get("edicoes") or []]

    def d_of(e):
        return e.get("date")

    day = dt.date.fromisoformat(ed.get("date") or collected.get("date"))
    previous = [e for e in old if d_of(e) != day.isoformat()]
    existing = next((e for e in old if d_of(e) == day.isoformat()), None)
    number = existing.get("number") if existing and existing.get("number") else \
        max([e.get("number") or 0 for e in previous] + [0]) + 1
    founded = dt.date.fromisoformat((index or {}).get("founded") or (index or {}).get("fundado_em") or day.isoformat())
    year_n = (day.year - founded.year) - ((day.month, day.day) < (founded.month, founded.day)) + 1
    weekend = day.weekday() >= 5
    section_ids = [s["id"] for s in cfg["sections"]]
    titles = {s["id"]: s["title"] for s in cfg["sections"]}
    used = set()

    def resolve(item, where):
        r = dict(item)
        if r.get("ref"):
            base = refs.get(r["ref"])
            if not base:
                errors.append(f"{where}: ref {r['ref']} is not in collected.json")
                return r
            if r["ref"] in used:
                errors.append(f"{where}: ref {r['ref']} used twice")
            used.add(r["ref"])
            r.setdefault("url", base.get("url", ""))
            r.setdefault("outlet", base.get("outlet", ""))
        if not str(r.get("url", "")).startswith("https://"):
            errors.append(f"{where}: missing link or not https")
        if not r.get("outlet"):
            errors.append(f"{where}: missing outlet (source name)")
        for field in ("title", "text"):
            if not (r.get(field) or "").strip():
                errors.append(f"{where}: missing {field}")
        for q in long_quotes(r.get("text", "")) + long_quotes(r.get("deck", "")):
            errors.append(f"{where}: quote with 15+ words: “{q[:50]}…”")
        return r

    h = ed.get("headline")
    if not h:
        errors.append("missing headline")
        h = {}
    else:
        h = resolve(h, "headline")
        if word_count(h.get("title")) > 14:
            warnings.append("headline has more than 14 words")
        if not h.get("deck"):
            errors.append("headline: missing deck")
    h_section = h.get("section") or ""
    if not h_section and h.get("ref"):
        sid = next((sid for sid, lst in (collected.get("news") or {}).items()
                    if any(n["id"] == h["ref"] for n in lst)), None)
        h_section = titles.get(sid, "")

    sections = {}
    for sid, items in (ed.get("sections") or {}).items():
        if sid not in section_ids:
            errors.append(f"section '{sid}' is not in config.json")
            continue
        sections[sid] = [resolve(n, f"{sid}[{i}]") for i, n in enumerate(items or [])]
        for n in sections[sid]:
            if word_count(n.get("title")) > 12:
                warnings.append(f"{sid}: title over 12 words: {n.get('title', '')[:40]}")
    total = (1 if h else 0) + sum(len(v) for v in sections.values())
    limits = cfg.get("total_news") or {}
    if total > limits.get("max", 10):
        errors.append(f"{total} stories: the maximum is {limits.get('max', 10)}")
    lo = (limits.get("weekend" if weekend else "weekday") or [0])[0]
    if total < lo:
        warnings.append(f"only {total} stories (usual minimum {lo}); fine if it is a slow day")

    # A list means the connector was read (empty = free day / inbox up to date). A missing key means
    # it is not connected: the box stays, saying so, instead of claiming a free day or an empty inbox.
    # A copy to share (--share) leaves out what was not included, and says so at the top instead.
    # "agenda_error" / "classifieds_error": connected, but the calls failed twice. The box stays and
    # says it could not be read, with the reason (true = no reason known).
    def failure(key, label):
        why = ed.get(key)
        if not why:
            return ""
        why = (why if isinstance(why, str) else L["connector_failed"]).strip().rstrip(".")[:120]
        return L[label].format(reason=why)
    agenda_failed = failure("agenda_error", "agenda_failed")
    mail_failed = failure("classifieds_error", "mail_failed")
    has_agenda = isinstance(ed.get("agenda"), list) and not agenda_failed
    has_mail = isinstance(ed.get("classifieds"), list) and not mail_failed
    agenda = ed.get("agenda") if has_agenda else []
    classifieds = []
    for i, c in enumerate(ed.get("classifieds") if has_mail else []):
        c = dict(c)
        if c.get("url") and not str(c["url"]).startswith("https://mail.google.com/"):
            errors.append(f"classifieds[{i}]: link must be https://mail.google.com/...")
        if re.search(r"\d{4,}|[$€£¥]|R\$", c.get("text", "")):
            errors.append(f"classifieds[{i}]: looks like it contains an amount or a code; remove it")
        c.setdefault("tag", L["wanted_reply"])
        c["in_gmail"] = L["in_gmail"]
        classifieds.append(c)

    weather = collected.get("weather") if ed.get("weather", True) else None
    if isinstance(ed.get("weather"), dict):
        weather = ed["weather"]
    if weather and not str(weather.get("url", "")).startswith("https://"):
        errors.append("weather: source without https link")
    if weather and ed.get("weather_condition"):
        weather = dict(weather, condition=ed["weather_condition"])

    hist = ed.get("history") or {}
    dyk = ed.get("did_you_know") or {}
    hist = {"text": hist} if isinstance(hist, str) else dict(hist)
    dyk = {"text": dyk} if isinstance(dyk, str) else dict(dyk)
    if hist.get("ref"):
        base = refs.get(hist["ref"])
        if base:
            hist.setdefault("url", base.get("url", ""))
        else:
            errors.append(f"history: ref {hist['ref']} is not in collected.json")
    week = [{"text": t} for t in (ed.get("week") or [])]
    if week and day.weekday() != 6:
        warnings.append("'week in a cup' is meant for Sundays")

    def plural(n, one, many):
        return f"{n} {L[one] if n == 1 else L[many]}"

    sample = a.sample or bool(ed.get("sample"))
    now = dt.datetime.now(tz)
    # An edition printed in the afternoon (an interactive run or a reissue) is not a morning one.
    evening = not weekend and day == now.date() and now.hour >= 12
    kind = L["edition_sample"] if sample else (L["edition_weekend"] if weekend else
                                               L["edition_evening"] if evening else L["edition_morning"])
    band = ed.get("band") or " · ".join(filter(None, [
        kind, L["shared_band"] if a.share else "",
        (plural(len(agenda), "appointment", "appointments") if agenda else L["free_agenda"]) if has_agenda else "",
        plural(len(classifieds), "classified", "classifieds") if classifieds else "",
        f"{total} {L['news_items']}"]))
    summary_line = band.split(" · ", 1)[1] if " · " in band else band
    shared_note = ""
    if a.share and not (has_agenda or has_mail):
        shared_note = L["shared_note_both"]
    elif a.share and not has_agenda:
        shared_note = L["shared_note_agenda"]
    elif a.share and not has_mail:
        shared_note = L["shared_note_mail"]

    def fmt_date(fmt):
        return fmt.format(weekday=L["weekdays"][day.weekday()], day=day.day,
                          month=L["months_short"][day.month - 1], year=day.year)

    text_h = (h.get("text") or "").strip()
    news_name = (cfg.get("newspaper") or {}).get("name") or L["default_newspaper_name"]
    # Who wrote it: "Claude" by default; newspaper.editor names another assistant, "" leaves it out.
    editor = (cfg.get("newspaper") or {}).get("editor", L["default_editor"])
    printed = L["time_format"].format(h=f"{now.hour:02d}", m=f"{now.minute:02d}")
    footer = (L["footer_credits"].format(editor=editor, time=printed) if editor
              else L["footer_printed"].format(time=printed))
    ctx = {
        "HTML_LANG": L["html_lang"], "NEWSPAPER": news_name, "MOTTO": (cfg.get("newspaper") or {}).get("motto", ""),
        "YEAR_ROMAN": roman(year_n), "NUMBER_3": f"{number:03d}", "DATE_LONG": fmt_date(L["date_format"]),
        "DATE_SHORT": fmt_date(L["date_short_format"]), "BAND": band,
        "weather": bool(weather),
        "SVG_WEATHER": svg(SVG_WEATHER.get((weather or {}).get("icon"), SVG_WEATHER["sun-cloud"]), 44),
        "WEATHER_TITLE": L["weather_in"].format(city=(cfg.get("city") or {}).get("name", "")),
        "MAX": (weather or {}).get("max", ""), "MIN": (weather or {}).get("min", ""),
        "CONDITION": (weather or {}).get("condition", ""), "URL_WEATHER": (weather or {}).get("url", ""),
        "headline": bool(h), "HEADLINE_SECTION": h_section, "HEADLINE_TITLE": h.get("title", ""),
        "HEADLINE_DECK": h.get("deck", ""),
        "SVG_HEADLINE": svg(SVG_ICON.get(h.get("icon"), SVG_ICON["newspaper"]), 56),
        "FIRST_LETTER": text_h[:1], "HEADLINE_REST": text_h[1:],
        "URL_HEADLINE": h.get("url", ""), "OUTLET_HEADLINE": h.get("outlet", ""),
        "agenda_block": has_agenda or bool(agenda_failed) or not a.share, "agenda_free": has_agenda and not agenda,
        "agenda_off": not (has_agenda or agenda_failed or a.share),
        "mail_off": not (has_mail or mail_failed or a.share),
        "agenda_failed": bool(agenda_failed), "AGENDA_FAILED": agenda_failed,
        "mail_failed": bool(mail_failed), "MAIL_FAILED": mail_failed,
        "prep": bool(ed.get("prep_note")), "PREP_NOTE": ed.get("prep_note", ""),
        "classifieds_block": (has_mail and (bool(classifieds) or not weekend)) or bool(mail_failed)
                             or (not has_mail and not a.share),
        "classifieds_empty": has_mail and not classifieds,
        "SECTIONS_HTML": sections_html(cfg, sections, L), "week": bool(week),
        "extras": bool(hist.get("text") or dyk.get("text")),
        "history": bool(hist.get("text")), "HISTORY": hist.get("text", ""),
        "url_history": str(hist.get("url", "")).startswith("https://"), "URL_HISTORY": hist.get("url", ""),
        "didyouknow": bool(dyk.get("text")), "DIDYOUKNOW": dyk.get("text", ""),
        "url_didyouknow": str(dyk.get("url", "")).startswith("https://"), "URL_DIDYOUKNOW": dyk.get("url", ""),
        "FOOTER_CREDITS": footer,
        "shared_note": bool(shared_note), "SHARED_NOTE": shared_note, "newsstand_button": not standalone,
    }
    for k, v in L.items():
        if isinstance(v, str):
            ctx[f"L_{k}"] = v
    stext = L["sample_text"].split("{command}")
    srest = esc(stext[0][1:]) + (f'<b class="cmd">"{esc(L["sample_command"])}"</b>' + esc(stext[1]) if len(stext) > 1 else "")
    ctx.update({"sample": sample, "SAMPLE_FIRST": stext[0][:1], "SAMPLE_REST_HTML": srest})
    lists = {"agenda": agenda, "classifieds": classifieds, "week": week}

    with open(os.path.join(a.skill, "assets", "edition.html"), encoding="utf-8") as f:
        page = render(f.read(), ctx, lists)

    body = page.split("<body>", 1)[-1]
    if re.search(r"\{\{|<!--/?(IF|EACH):", body):
        errors.append("a template marker was left in the page")
    for href in re.findall(r'href="([^"]*)"', page):
        if not (href.startswith("https://") or (href == "../index.html" and not standalone)):
            errors.append(f"invalid link in page: {href[:60]}")
    for tag in ("section", "div", "article", "p"):
        if len(re.findall(rf"<{tag}[\s>]", page)) != page.count(f"</{tag}>"):
            errors.append(f"unbalanced <{tag}> tags in page")

    for w in warnings:
        print("WARNING:", w)
    if errors:
        for e in errors:
            print("ERROR:", e)
        print("Nothing was written. Fix edition.json and run again.")
        return 1

    if standalone:
        # Nothing goes to the newsstand: no index is written, so a copy can never replace the
        # morning entry by mistake if someone publishes WORK/archive later.
        out_dir = os.path.join(a.work, "standalone")
        os.makedirs(out_dir, exist_ok=True)
        path = os.path.join(out_dir, f"{day.isoformat()}.html")
        with open(path, "w", encoding="utf-8") as f:
            f.write(page)
        print(f"OK: {L['issue_label']} {number:03d} · {day.isoformat()} · {total} stories · "
              f"{'SHARE COPY' if a.share else 'STANDALONE'}")
        print("HEADLINE:", h.get("title", ""))
        print(f"NOT FOR THE NEWSSTAND: send this file to the reader: {os.path.abspath(path)}")
        return 0

    stories = ([h] if h else []) + [n for v in sections.values() for n in v]
    entry = {
        "date": day.isoformat(), "number": number, "weekday": L["weekdays"][day.weekday()],
        "type": "sample" if sample else ("weekend" if weekend else "morning"), "headline": h.get("title", ""), "summary": summary_line,
        "file": f"editions/{day.isoformat()}.html",
        "extras": {"history": hist.get("summary") or hist.get("text", "")[:140],
                   "did_you_know": dyk.get("summary") or dyk.get("text", "")[:140]},
        "titles": [n.get("title", "") for n in stories[1:]],
        # The titles as collected (before rewriting): what the next collections are compared against.
        "source_titles": [refs[n["ref"]].get("title", "") for n in stories if n.get("ref") in refs],
        "links": [n.get("url", "") for n in stories],
    }
    archive_labels = {k: L[k] for k in ("html_lang", "archive_title", "archive_kicker", "archive_subtitle",
                                        "latest_edition", "previous_editions", "archive_empty", "archive_error",
                                        "weekend_tag", "issue_label", "months_short", "date_short_format")}
    new = {"newspaper": news_name, "founded": (index or {}).get("founded") or (index or {}).get("fundado_em")
           or day.isoformat(), "labels": archive_labels, "editions": [entry] + previous}
    new["editions"].sort(key=d_of, reverse=True)
    for e in new["editions"][DEDUP_EDITIONS:]:
        for k in ("titles", "source_titles", "links"):
            e.pop(k, None)

    stand_title = f"{news_name} · {L['archive_title']}"
    dest = os.path.join(a.work, "archive")
    os.makedirs(os.path.join(dest, "editions"), exist_ok=True)
    with open(os.path.join(dest, "editions", f"{day.isoformat()}.html"), "w", encoding="utf-8") as f:
        f.write(page)
    with open(os.path.join(dest, "editions", "index.json"), "w", encoding="utf-8") as f:
        json.dump(new, f, ensure_ascii=False, indent=1)
    publish = [f"editions/{day.isoformat()}.html", "editions/index.json"]
    if index is None or legacy or a.with_page:
        with open(os.path.join(a.skill, "assets", "archive.html"), encoding="utf-8") as f:
            stand = f.read()
        # The page title is what the artifact list shows: "<newspaper> · <newsstand label>".
        stand = re.sub(r"<title>.*?</title>", f"<title>{esc(stand_title)}</title>", stand, count=1)
        stand = re.sub(r'<html lang="[^"]*">', f'<html lang="{esc(L["html_lang"])}">', stand, count=1)
        with open(os.path.join(dest, "index.html"), "w", encoding="utf-8") as f:
            f.write(stand)
        publish.insert(0, "index.html")
    if index is None:
        print(f"NEW NEWSSTAND: create the artifact titled \"{stand_title}\" with the files below.")
    elif legacy:
        print("LEGACY NEWSSTAND MIGRATED: the index now lives in editions/index.json. Publish every file below "
              "and, if the tool can delete files, remove edicoes/indice.json in the same call.")
    if (index is None or legacy or a.with_config) and not sample:
        shutil.copy(a.config, os.path.join(dest, "config.json"))
        publish.append("config.json")
    print(f"OK: {L['issue_label']} {number:03d} · {day.isoformat()} · {total} stories"
          f"{' · REISSUE' if existing else ''}")
    print("HEADLINE:", h.get("title", ""))
    print(f"NEWSSTAND TITLE: {stand_title}")
    print("PUBLISH (as -> path):")
    for p in publish:
        print(f"  {p} -> {os.path.abspath(os.path.join(dest, p))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
