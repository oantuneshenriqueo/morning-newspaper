#!/usr/bin/env python3
"""Builds an edition of the morning newspaper from a short JSON written by the model.

Inputs: WORK/edition.json (format in references/edition-format.md), WORK/collected.json (required:
the collection is never skipped). Every run also appends its command and output to WORK/run.log.
(from collect.py) and the reader's config.json. Stories can point at collected items by ID
("ref": "a3"); the script fills in URL, outlet and date by itself.

Output, if every check passes:
  WORK/archive/editions/YYYY-MM-DD.html
  WORK/archive/editions/index.json     (previous index + the new entry on top)
  WORK/archive/index.html              (always: the publishing tool needs the page in every publish)
  WORK/archive/config.json             (when the newsstand is new or legacy, or with --with-config)
and the list of files to publish. With --standalone (a test or a copy that is not going to the
newsstand) or --share (a copy to show other people) it writes only WORK/standalone/YYYY-MM-DD.html:
no newsstand button, and the index is left untouched.
With --single-page (the publishing tool takes one HTML page per artifact, so there can be no
newsstand) it writes WORK/single/index.html: today's edition with the reader's state (config and a
compact index) embedded in a <script type="application/json" id="morning-newspaper-state"> block
near the top, so the next run can recover it with --unpack-state.
If anything fails it prints the errors, writes nothing and exits 1.

Standard library only. No network access.
Usage:
  python3 assemble.py --skill SKILL_DIR --config config.json --work WORK_DIR [--index index.json]
                      [--with-config] [--with-page] [--sample] [--standalone | --share | --single-page]
  python3 assemble.py --unpack-state STATE_FILE --work WORK_DIR
"""
import hashlib
import argparse
import datetime as dt
import html
import json
import os
import re
import shutil
import sys
import unicodedata

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
    "snow": f'<path d="M9 26h25a8 8 0 0 0 0-16 10 10 0 0 0-19 3 7 7 0 0 0-6 13z" fill="#FBF6EC" stroke="#1E1B16" stroke-width="1.5"/><path d="M14 31v6M11 34h6M24 31v6M21 34h6M34 31v6M31 34h6" {_S}/>',
    "storm": f'<path d="M9 26h25a8 8 0 0 0 0-16 10 10 0 0 0-19 3 7 7 0 0 0-6 13z" fill="#FBF6EC" stroke="#1E1B16" stroke-width="1.5"/><path d="M23 28l-4 7h5l-3 7" {_S}/>',
}
_P = 'stroke="#1E1B16" stroke-width="1.5" fill="#FBF6EC"'
_F = 'fill="#1E1B16"'
SVG_ICON = {
    "lock": f'<rect x="14" y="26" width="28" height="22" {_S}/><path d="M19 26v-7a9 9 0 0 1 18 0v7M28 34v6" {_S}/>',
    "chip": f'<rect x="16" y="16" width="24" height="24" {_S}/><rect x="22" y="22" width="12" height="12" {_S}/><path d="M22 10v6M28 10v6M34 10v6M22 40v6M28 40v6M34 40v6M10 22h6M10 28h6M10 34h6M40 22h6M40 28h6M40 34h6" {_S}/>',
    "coin": f'<circle cx="28" cy="28" r="17" {_S}/><circle cx="28" cy="28" r="12" {_S}/><path d="M32 22h-6a3 3 0 0 0 0 6h4a3 3 0 0 1 0 6h-6M28 19v3M28 34v3" {_S}/>',
    "chart": f'<path d="M10 46h36M10 46V10" {_S}/><path d="M14 38l9-10 7 6 12-15" {_S}/><path d="M36 19h6v6" {_S}/>',
    "gamepad": f'<path d="M14 22h28a8 8 0 0 1 8 8l-2 10a5 5 0 0 1-9 2l-3-5H20l-3 5a5 5 0 0 1-9-2L6 30a8 8 0 0 1 8-8z" {_S}/><path d="M16 29v6M13 32h6" {_S}/><circle cx="38" cy="30" r="1.5" fill="#1E1B16"/><circle cx="42" cy="34" r="1.5" fill="#1E1B16"/>',
    "city": f'<path d="M8 46h40M12 46V24h10v22M22 46V14h12v32M34 46V28h10v18" {_S}/><path d="M16 29h2M16 35h2M26 19h4M26 25h4M26 31h4M38 33h2M38 39h2" {_S}/>',
    "robot": f'<rect x="14" y="20" width="28" height="22" {_S}/><path d="M28 12v8M10 28v8M46 28v8M22 36h12" {_S}/><circle cx="28" cy="11" r="2" {_S}/><circle cx="22" cy="29" r="2.5" {_S}/><circle cx="34" cy="29" r="2.5" {_S}/>',
    "newspaper": f'<rect x="10" y="12" width="36" height="32" {_S}/><path d="M16 20h24M16 26h10M16 32h10M16 38h10M30 26h10v12H30z" {_S}/>',
    "heart": f'<path d="M28 46C16 37 9 30 9 21a9 9 0 0 1 19-4 9 9 0 0 1 19 4c0 9-7 16-19 25z" {_S}/><path d="M13 27h8l3-6 5 12 3-6h11" {_S}/>',
    "ball": f'<circle cx="28" cy="28" r="18" {_S}/><path d="M28 21l6 4.5-2.3 7h-7.4L22 25.5z" {_S}/><path d="M28 21V10M34 25.5l10-3.5M31.7 32.5l6 8.5M24.3 32.5l-6 8.5M22 25.5l-10-3.5" {_S}/>',
    "trophy": f'<path d="M19 10h18v12a9 9 0 0 1-18 0z" {_S}/><path d="M19 14h-6a6 6 0 0 0 6 8M37 14h6a6 6 0 0 1-6 8M28 31v7M18 46h20M22 46l2-8h8l2 8" {_S}/>',
    "leaf": f'<path d="M12 44C12 24 24 12 44 12c0 20-12 32-32 32z" {_S}/><path d="M12 44L36 20M22 34v-8M28 28h8" {_S}/>',
    "globe": f'<circle cx="28" cy="28" r="18" {_S}/><ellipse cx="28" cy="28" rx="8" ry="18" {_S}/><path d="M10 28h36M13 19h30M13 37h30" {_S}/>',
    "gavel": f'<g transform="rotate(45 22 18)"><rect x="10" y="11" width="24" height="12" {_S}/><path d="M14 11v12M30 11v12M22 23v22" {_S}/></g><path d="M26 48h22M29 48v-5h16v5" {_S}/>',
    "ballot": f'<path d="M22 21V8h12v13" {_S}/><path d="M25 14l2.5 2.5 4-4" {_S}/><path d="M10 26l4-6h28l4 6v20H10z" {_S}/><path d="M10 26h36M21 23h14" {_S}/>',
    "capitol": f'<path d="M12 22h32L28 12z M8 46h40M10 42h36" {_S}/><path d="M15 22v20M23 22v20M33 22v20M41 22v20" {_S}/>',
    "car": f'<path d="M8 38v-8l6-2 5-8h18l6 8 5 2v8z" {_S}/><path d="M23 28h12" {_S}/><circle cx="17" cy="38" r="4" {_P}/><circle cx="39" cy="38" r="4" {_P}/>',
    "plane": f'<path d="M28 8c2 0 3 2 3 5v9l15 9v4l-15-4v9l5 4v3l-8-2-8 2v-3l5-4v-9l-15 4v-4l15-9v-9c0-3 1-5 3-5z" {_S}/>',
    "bus": f'<rect x="14" y="10" width="28" height="32" rx="4" {_S}/><path d="M14 30h28M14 18h28M19 36h2M35 36h2M18 42v4M38 42v4" {_S}/>',
    "book": f'<path d="M28 16c-5-4-12-5-18-4v30c6-1 13 0 18 4 5-4 12-5 18-4V12c-6-1-13 0-18 4zM28 16v30" {_S}/>',
    "flask": f'<path d="M22 10h12M25 10v12L13 42a3 3 0 0 0 3 4h24a3 3 0 0 0 3-4L31 22V10" {_S}/><path d="M18 34h20" {_S}/><circle cx="25" cy="40" r="1.5" {_F}/><circle cx="31" cy="38" r="1.5" {_F}/>',
    "rocket": f'<path d="M28 8c7 6 9 15 7 26H21c-2-11 0-20 7-26z" {_S}/><circle cx="28" cy="20" r="3" {_S}/><path d="M21 27l-6 6v7l7-4M35 27l6 6v7l-7-4M25 38l3 8 3-8" {_S}/>',
    "film": f'<rect x="10" y="24" width="36" height="22" {_S}/><path d="M10 24v-8h36v8M18 16l-4 8M26 16l-4 8M34 16l-4 8M42 16l-4 8" {_S}/>',
    "music": f'<path d="M22 40V14l20-4v26M22 20l20-4" {_S}/><circle cx="17" cy="40" r="5" {_S}/><circle cx="37" cy="36" r="5" {_S}/>',
    "phone": f'<rect x="18" y="8" width="20" height="40" rx="3" {_S}/><path d="M18 14h20M18 40h20M26 44h4" {_S}/>',
    "house": f'<path d="M10 26L28 10l18 16M14 23v23h28V23" {_S}/><path d="M24 46V34h8v12" {_S}/>',
    "cart": f'<path d="M8 12h6l5 24h22l4-16H16" {_S}/><circle cx="22" cy="42" r="3" {_S}/><circle cx="38" cy="42" r="3" {_S}/>',
    "bolt": f'<path d="M31 8L15 31h11l-3 17 18-24H30z" {_S}/>',
    "briefcase": f'<rect x="10" y="18" width="36" height="26" {_S}/><path d="M22 18v-5h12v5M10 28h36M25 28v4h6v-4" {_S}/>',
    "shield": f'<path d="M28 9l16 6v11c0 10-7 17-16 21-9-4-16-11-16-21V15z" {_S}/><path d="M21 28l5 5 10-10" {_S}/>',
    "wheat": f'<path d="M28 48V14" {_S}/><path d="M28 22c-5 0-8-3-8-7 5 0 8 3 8 7zM28 22c5 0 8-3 8-7-5 0-8 3-8 7z" {_S}/><path d="M28 30c-5 0-8-3-8-7 5 0 8 3 8 7zM28 30c5 0 8-3 8-7-5 0-8 3-8 7z" {_S}/><path d="M28 38c-5 0-8-3-8-7 5 0 8 3 8 7zM28 38c5 0 8-3 8-7-5 0-8 3-8 7z" {_S}/><path d="M28 14c-2.5-2-2.5-5 0-7 2.5 2 2.5 5 0 7z" {_S}/>',
    "fuel": f'<path d="M10 46h24M14 46V12h16v34M14 24h16M30 20h5l5 5v14a3 3 0 0 1-6 0v-8h-4" {_S}/>',
    "wifi": f'<path d="M10 22a26 26 0 0 1 36 0M16 29a17 17 0 0 1 24 0M22 36a8 8 0 0 1 12 0" {_S}/><circle cx="28" cy="42" r="2.5" {_F}/>',
    "thermometer": f'<path d="M24 34V12a4 4 0 0 1 8 0v22a8 8 0 1 1-8 0z" {_S}/><circle cx="28" cy="40" r="3" {_F}/><path d="M28 37V20M36 16h4M36 22h4M36 28h4" {_S}/>',
    "megaphone": f'<path d="M10 24v8h6l20 10V14L16 24zM16 24v8" {_S}/><path d="M17 33l3 11h5l-2-9M42 22v12" {_S}/>',
    "people": f'<circle cx="21" cy="20" r="6" {_S}/><circle cx="37" cy="22" r="5" {_S}/><path d="M9 44c0-8 5-13 12-13s12 5 12 13M33 33c1-1 2-1 4-1 5 0 9 4 9 12" {_S}/>',
}


# Older newsstands wrote the index in Portuguese (edicoes/indice.json). Entries are always
# rewritten with the current keys, so an index never mixes the two spellings.
LEGACY_INDEX_KEYS = ("edicoes", "fundado_em", "jornal")
LEGACY_KEYS = {"data": "date", "numero": "number", "dia_semana": "weekday", "tipo": "type", "manchete": "headline",
               "resumo": "summary", "arquivo": "file", "titulos": "titles"}
LEGACY_EXTRAS = {"historia": "history", "voce_sabia": "did_you_know"}
LEGACY_TYPES = {"fim de semana": "weekend", "manhã": "morning", "manha": "morning", "matutina": "morning",
                "amostra": "sample"}
DEDUP_EDITIONS = 14  # titles/links only exist to avoid repeats: kept for the latest editions only
STATE_ID = "morning-newspaper-state"
STATE_PAT = r'<script type="application/json" id="morning-newspaper-state">(.*?)</script>'


class _Tee:
    """Everything printed also goes to WORK/run.log, written by the script itself: a debug report can
    quote the real output later, and the model spends no tokens on it (it never reads the log)."""

    def __init__(self, out, log):
        self.out, self.log = out, log

    def write(self, txt):
        self.out.write(txt)
        try:
            self.log.write(txt)
        except (OSError, ValueError):
            pass
        return len(txt)

    def flush(self):
        self.out.flush()
        try:
            self.log.flush()
        except (OSError, ValueError):
            pass


def start_log(work, script):
    """Appends this run's command, time and output to WORK/run.log. Never blocks the edition."""
    try:
        os.makedirs(work, exist_ok=True)
        log = open(os.path.join(work, "run.log"), "a", encoding="utf-8", buffering=1)
        now = dt.datetime.now(dt.timezone.utc).astimezone()
        log.write(f"\n===== {script} · {now.isoformat(timespec='seconds')} · "
                  f"{' '.join(sys.argv[1:])}\n")
        sys.stdout = _Tee(sys.stdout, log)
    except OSError:
        pass


def link_id(url):
    """Short fingerprint of a link: the single-page state keeps these instead of long URLs."""
    return hashlib.sha1(str(url).encode("utf-8")).hexdigest()[:12]


def state_block(cfg, index):
    """The reader's state as one line of JSON for the single page. '<' is escaped so nothing in it
    can close the script tag; json.loads reads it back unchanged."""
    editions = []
    for e in index["editions"]:
        e = {k: v for k, v in e.items() if k != "file"}
        if "links" in e:
            e["link_ids"] = sorted({link_id(u) for u in e.pop("links") if u} | set(e.get("link_ids") or []))
        editions.append(e)
    state = {"format": 1, "config": cfg,
             "index": {"newspaper": index["newspaper"], "founded": index["founded"], "editions": editions}}
    data = json.dumps(state, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
    return f'<script type="application/json" id="{STATE_ID}">{data}</script>'


def unpack_state(path, work):
    """--unpack-state: reads the state copied from the single page (the JSON alone, or the page
    with its state block) and writes WORK/config.json and WORK/index.json."""
    try:
        with open(path, encoding="utf-8") as f:
            raw = f.read()
        m = re.search(STATE_PAT, raw, re.S)
        state = json.loads(m.group(1) if m else raw)
        cfg, index = state["config"], state["index"]
        if not isinstance(cfg, dict) or not isinstance(index.get("editions"), list):
            raise ValueError("config or index has the wrong shape")
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as e:
        print(f"ERROR: could not read the state ({type(e).__name__}: {str(e)[:120]}). Copy the whole JSON "
              f"inside <script id=\"{STATE_ID}\"> from the page, exactly as it is, and run again.")
        return 1
    os.makedirs(work, exist_ok=True)
    with open(os.path.join(work, "config.json"), "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=1)
    with open(os.path.join(work, "index.json"), "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=1)
    last = (sorted(index["editions"], key=lambda e: str(e.get("date") or ""), reverse=True) or [{}])[0]
    print(f"STATE: wrote config.json and index.json to {os.path.abspath(work)} "
          f"(last edition: No. {last.get('number', '-')}, {last.get('date', '-')}; "
          f"{len(index['editions'])} editions)")
    return 0


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
    # Braces too: a story about templates ("{{ name }}") must stay text, never become a marker.
    return html.escape(str(v), quote=True).replace("{", "&#123;").replace("}", "&#125;")


def short(t, limit=140):
    """Cut at a word boundary, with an ellipsis."""
    t = " ".join((t or "").split())
    return t if len(t) <= limit else t[: limit - 1].rsplit(" ", 1)[0].rstrip(",;:") + "…"


def _fold(t):
    return unicodedata.normalize("NFKD", t or "").encode("ascii", "ignore").decode().lower()


def _stems(t):
    """Words cut to their first 5 letters, so "carregar" and "carregando" match."""
    return {w[:5] for w in re.findall(r"[a-z0-9]+", _fold(t)) if len(w) > 3}


# Words that soften a claim: when the source has one and the printed text has none, the paper
# states as fact what the source only reported ("potentially exposed" -> "exposed").
HEDGES = {"potencialmente", "possivelmente", "suposto", "suposta", "supostos", "supostas", "supostamente",
          "teria", "teriam", "alegado", "alegada", "alegadamente", "pode", "podem", "poderia", "poderiam",
          "possivel", "possiveis", "suspeita", "suspeito", "segundo", "aparentemente", "presumivelmente",
          "potentially", "possibly", "allegedly", "alleged", "reportedly", "may", "might", "could",
          "suspected", "apparently", "supuesto", "supuesta", "supuestamente", "podria", "podrian",
          "presunto", "presunta", "presuntamente", "posiblemente", "potencialmente"}
STOP_CAPS = {"o", "a", "os", "as", "um", "uma", "the", "el", "la", "los", "las", "en", "em", "no", "na", "de", "do",
             "da", "and", "e", "y", "in", "on", "of", "por", "para", "com", "con", "with", "un", "una", "an"}


# Common words that open a sentence before a name ("Após Durov negar…", "After Apple…"). The first
# word of a sentence counts as a possible name only when it is not one of these (or an attribution
# word, or an adverb in -mente / -ly).
SENTENCE_OPENERS = {
    # pt
    "apos", "antes", "depois", "durante", "desde", "entre", "sobre", "contra", "pelo", "pela", "pelos",
    "pelas", "sem", "sob", "ate", "ante", "perante", "segundo", "conforme", "tambem", "ainda", "hoje",
    "ontem", "amanha", "agora", "enquanto", "mas", "porem", "contudo", "entretanto", "todavia", "assim",
    "alem", "apesar", "embora", "quando", "onde", "como", "porque", "pois", "logo", "mesmo", "nem",
    "nesta", "neste", "nessa", "nesse", "naquela", "naquele", "esta", "este", "essa", "esse", "isso",
    "isto", "aquela", "aquele", "cada", "todo", "toda", "todos", "todas", "outro", "outra", "outros",
    "outras", "muitos", "muitas", "varios", "varias", "alguns", "algumas", "nenhum", "nenhuma", "para",
    "pra", "aos", "nos", "nas", "dos", "das", "num", "numa", "seu", "sua", "seus", "suas", "ja", "so",
    "cerca", "quase", "apenas", "somente", "tambem", "talvez", "enfim", "afinal", "entao", "agora",
    "segunda", "terca", "quarta", "quinta", "sexta", "sabado", "domingo",
    # en
    "after", "before", "during", "since", "until", "while", "although", "though", "because", "when",
    "where", "with", "without", "within", "about", "against", "among", "between", "under", "over",
    "from", "into", "through", "also", "still", "today", "yesterday", "tomorrow", "now", "but", "yet",
    "meanwhile", "however", "instead", "despite", "this", "that", "these", "those", "each", "every",
    "other", "some", "many", "most", "several", "their", "its", "his", "her", "our", "your", "both",
    "such", "even", "only", "just", "nearly", "almost", "then", "there", "here", "what", "which",
    "who", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
    # es
    "tras", "antes", "despues", "durante", "desde", "entre", "sobre", "contra", "hasta", "segun",
    "tambien", "todavia", "hoy", "ayer", "manana", "ahora", "mientras", "pero", "aunque", "cuando",
    "donde", "como", "porque", "pues", "esta", "este", "estos", "estas", "cada", "todo", "toda",
    "todos", "todas", "otro", "otra", "otros", "otras", "muchos", "muchas", "varios", "varias",
    "algunos", "algunas", "ningun", "ninguna", "para", "sus", "solo", "casi", "lunes", "martes",
    "miercoles", "jueves", "viernes", "sabado",
}


def _opener(tok):
    f = _fold(tok)
    return f in SENTENCE_OPENERS or f in ATTRIBUTION or f.endswith(("mente", "ly"))


# Words that only attribute a fact to its outlet ("Segundo o BPMoney, …"): the rules ask for this
# when only a small outlet backs a story, so they never count as facts the source lacks.
ATTRIBUTION = {"segundo", "conforme", "according", "segun", "informa", "informou", "reporta", "relata",
               "relatou", "afirma", "afirmou", "reports", "reported", "informo",
               # "outlets report…": the hedge the rules ask for when only small outlets carry a story
               "relatam", "reportam", "informam", "noticiam", "noticiou", "veiculos", "sites",
               "imprensa", "relatos", "outlets", "media", "report", "reporting", "medios", "reportan",
               "informan", "informaron", "publicam", "publicou", "dizem", "afirmam"}
# Plural attributions ("outlets report…", "sites relatam…"): fair only when several collected
# candidates carry the fact (marked ≈ by the collection). One outlet is named instead ("Segundo o
# Pplware, …"): edition No. 011 wrote "Sites relatam" for a story only Pplware carried.
PLURAL_ATTRIBUTION = {"relatam", "reportam", "informam", "noticiam", "veiculos", "sites", "relatos",
                      "outlets", "report", "reportan", "informan", "informaron", "publicam", "dizem",
                      "afirmam", "medios"}
# Month names, so a date taken from the story's own publication date ("on Friday, November 20")
# does not count as a word or number the source lacks.
MONTH_NAMES = [("janeiro", "enero", "January"), ("fevereiro", "febrero", "February"), ("março", "marzo", "March"),
               ("abril", "abril", "April"), ("maio", "mayo", "May"), ("junho", "junio", "June"),
               ("julho", "julio", "July"), ("agosto", "agosto", "August"), ("setembro", "septiembre", "September"),
               ("outubro", "octubre", "October"), ("novembro", "noviembre", "November"),
               ("dezembro", "diciembre", "December")]


def date_words(when):
    """The day, month and year of a collected date ("2026-11-20 10:45") as source text: the day and
    month the story came out are known, so printing them is not a fact from memory. The hour is not
    included (a "10" or "45" elsewhere in the text still gets a CHECK)."""
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", str(when or ""))
    if not m:
        return ""
    year, month, day = m.group(1), int(m.group(2)), int(m.group(3))
    if not 1 <= month <= 12:
        return ""
    return " ".join([str(day), f"{day:02d}", str(month), f"{month:02d}", year, *MONTH_NAMES[month - 1]])


def overstated_attribution(written, base, refs):
    """A plural attribution ("sites relatam…") for a story only one collected outlet carries."""
    words = set(re.findall(r"[a-z]+", _fold(" ".join(w for w in written if w))))
    if not words & PLURAL_ATTRIBUTION or not base.get("id"):
        return None
    group = base.get("same_as") or base["id"]
    outlets = {_fold(n.get("outlet") or "") for n in refs.values()
               if n.get("id") == group or n.get("same_as") == group}
    outlets.discard("")
    if len(outlets) > 1:
        return None
    name = base.get("outlet") or "the outlet"
    return (f"plural attribution, but only {name} carries this story: name it (\"Segundo o {name}, …\", in "
            "the reader's language) instead of \"outlets report…\"")


# Other names of a country the source names by its short form ("EUA" in the title, "Estados Unidos"
# in the text). Short forms are matched in capitals only ("us" and "eu" are also everyday words).
COUNTRY_NAMES = [(r"\b(?:EUA|EEUU|EE\. ?UU|USA)\b|\bU\.S\.|\bUS\b(?!\$)", r"estados unidos|united states",
                  "Estados Unidos United States EUA EEUU USA"),
                 (r"\bUK\b", r"reino unido|united kingdom", "Reino Unido United Kingdom UK"),
                 (r"\bUE\b", r"uniao europeia|union europea|european union", "União Europeia Unión Europea European Union UE")]


def with_country_names(source):
    source = source or ""
    extra = [names for short, full, names in COUNTRY_NAMES
             if re.search(short, source) or re.search(full, _fold(source))]
    return " ".join([source, *extra])


def unsupported(written, source, empty_summary):
    """What step 6 must look at in one printed item: names and numbers the collected text does not
    carry, a hedge the source had and the text dropped and, when the summary was empty (only the
    title backs the story), longer words that are not in the title. A hint, never a block: a
    paraphrase is fine, a fact added from memory is not."""
    source = with_country_names(source)
    src = _stems(source)
    src_words = set(re.findall(r"[a-z0-9]+", _fold(source)))
    notes = []
    names = []
    fields = written if isinstance(written, (list, tuple)) else [written]
    for field in fields:
        caps = re.findall(r"\b\w", field or "")
        if caps and sum(c.isupper() for c in caps) / len(caps) > 0.6:
            continue  # Title Case ("Road Work Starts Monday"): capitals say nothing about names
        for sentence in re.split(r"(?<=[.!?:;])\s+|\n", field or ""):
            toks = re.findall(r"[\w][\w'’-]*", sentence)
            for i, tok in enumerate(toks):
                if not tok[:1].isupper() or tok.lower() in STOP_CAPS:
                    continue
                # The first word of a sentence is always capitalized, so it counts as a name only when
                # the next word is capitalized too ("Pavel Durov negou…", edition No. 009).
                if i == 0 and (_opener(tok) or not (len(toks) > 1 and toks[1][:1].isupper()
                                                    and toks[1].lower() not in STOP_CAPS)):
                    continue
                if not (_stems(tok) <= src) and _fold(tok) not in src_words:
                    names.append(tok)
    written = " ".join(f for f in fields if f)
    nums = [n for n in re.findall(r"\d+(?:[.,]\d+)*", written or "")
            if n not in source and n.replace(".", "").replace(",", "") not in re.sub(r"[.,]", "", source)]
    if names:
        notes.append("names not in the source: " + ", ".join(dict.fromkeys(names)))
    if nums:
        notes.append("numbers not in the source: " + ", ".join(dict.fromkeys(nums)))
    if src_words & HEDGES and not set(re.findall(r"[a-z0-9]+", _fold(written))) & HEDGES:
        notes.append("the source hedges (" + ", ".join(sorted(src_words & HEDGES)) + ") and the text does not")
    if empty_summary:
        named = {_fold(n) for n in names}
        src4 = {w[:4] for w in src}  # "ganhou" restates "ganha": same root, another tense
        extra = [w for w in re.findall(r"[a-z0-9]+", _fold(written))
                 if len(w) >= 6 and w[:5] not in src and w[:4] not in src4 and w not in named
                 and w not in ATTRIBUTION]
        if extra:
            notes.append("only the title backs it; words not in the title: " + ", ".join(list(dict.fromkeys(extra))[:8]))
    return notes


def wrong_weekdays(text, day, L):
    """Weekday + day number pairs ("terça-feira, 17", "Tuesday, Nov. 17") that the calendar does not
    back. The model works weekdays out in its head and gets them wrong; the script knows the calendar.
    Only full weekday names count ("segunda" alone is also an ordinal). The month is the one named,
    else the nearest date to the edition with that day number (within 10 days); anything else is
    left alone."""
    names = [_fold(w) for w in L.get("weekdays") or []]
    if len(names) != 7 or not text:
        return []
    months = [_fold(m) for m in (L.get("months") or [])] + [_fold(m) for m in (L.get("months_short") or [])]
    month_re = "|".join(re.escape(m) for m in sorted(set(filter(None, months)), key=len, reverse=True))
    folded = _fold(text)
    out = []
    for wd, name in enumerate(names):
        pat = (re.escape(name) + r"[\s,(]*(?:dia\s+)?(?:(" + (month_re or "(?!)") + r")\.?\s+)?"
               r"(\d{1,2})(?![\d:%h])(?:\s*(?:de\s+)?(" + (month_re or "(?!)") + r"))?")
        for m in re.finditer(r"\b" + pat, folded):
            n = int(m.group(2))
            if not 1 <= n <= 31:
                continue
            month_word = m.group(1) or m.group(3)
            candidates = []
            if month_word and month_word in months:
                mon = months.index(month_word) % 12 + 1
                for y in (day.year - 1, day.year, day.year + 1):
                    try:
                        candidates.append(dt.date(y, mon, n))
                    except ValueError:
                        pass
                candidates = [min(candidates, key=lambda d: abs((d - day).days))] if candidates else []
            else:
                for delta in range(-10, 11):
                    d = day + dt.timedelta(days=delta)
                    if d.day == n:
                        candidates.append(d)
                candidates = candidates[:1]
            if candidates and candidates[0].weekday() != wd:
                d = candidates[0]
                out.append((m.group(0), d.isoformat(), L["weekdays"][d.weekday()]))
    return out


# ---------------------------------------------------------------- keyword self-tuning
# The model may adjust a section's "keywords" on its own, the one config change it makes without
# the reader, because keywords only reorder candidates (never hide one) and can be undone. The
# script, not the model, decides whether there is enough ground: the model only lists the
# candidates it left out as off-topic ("off_topic") and proposes words ("keywords_proposal").
KW_WINDOW = 5          # editions looked at, today included
KW_NEEDED = 3          # of them with many off-topic candidates
KW_COOLDOWN_DAYS = 7   # one change per section per week
KW_MAX = 15            # words per section
KW_MAX_ADD = 4         # words added per change
KW_SETTLE = 3          # editions after a change before judging it
KW_WORSE = 0.10        # off-topic share that much higher after the change → undo it


def kw_heavy(stat):
    """An edition where a section brought many off-topic candidates: at least 2 and a quarter."""
    try:
        cand, off = int(stat[0]), int(stat[1])
    except (TypeError, ValueError, IndexError):
        return False
    return off >= 2 and off * 4 >= cand


def kw_rate(stats):
    vals = [int(st[1]) / int(st[0]) for st in stats if st and int(st[0] or 0) > 0]
    return sum(vals) / len(vals) if vals else 0.0


def kw_valid_word(w):
    if not isinstance(w, str):
        return False
    w = w.strip()
    return (2 <= len(w) <= 40 and len(w.split()) <= 3 and not w.isdigit()
            and re.fullmatch(r"[\w][\w \-'.+&]*", w) is not None
            and not re.search(r"https?|www\.|\.(com|net|org)\b", w.lower()))


def kw_is_local(sec, cfg):
    city = _fold((cfg.get("city") or {}).get("name", ""))
    return bool(city) and any(city in _fold(str(q)) for q in sec.get("queries") or [])


def keyword_tuning(cfg, ed, collected, previous, day, L):
    """Decides today's keyword change (or undo) from the evidence. Returns (fit, changes, notes, lines, dirty):
    fit = this edition's {section: [candidates, off_topic]} for the index; changes = list of
    (section_id, new_keywords, log_entry); notes = lines printed on the page; lines = KEYWORDS: output;
    dirty = an earlier change was judged (its log entry changed), so config.json must be saved."""
    lines, notes, changes, dirty = [], [], [], False
    news = collected.get("news") or {}
    where = {n["id"]: sid for sid, lst in news.items() for n in lst if isinstance(n, dict) and "id" in n}
    off = ed.get("off_topic") or []
    if not isinstance(off, list):
        off = []
        lines.append("ignored off_topic: it must be a list of candidate refs, e.g. [\"a3\", \"a8\"]")
    unknown = [r for r in off if r not in where]
    if unknown:
        lines.append(f"ignored off_topic refs not in collected.json: {', '.join(map(str, unknown[:5]))}")
    fit = {}
    for sid, lst in news.items():
        fit[sid] = [len(lst), len({r for r in off if where.get(r) == sid})]
    secs = {s["id"]: s for s in cfg.get("sections") or []}
    log = cfg.get("keywords_log") if isinstance(cfg.get("keywords_log"), list) else []
    hist = sorted([e for e in previous if isinstance(e.get("fit"), dict)], key=lambda e: str(e.get("date")))
    title = lambda sid: secs.get(sid, {}).get("title", sid)

    # 1. Judge earlier changes once KW_SETTLE editions came after them; undo the ones that made it worse.
    for entry in log:
        if entry.get("settled") or entry.get("section") not in secs:
            continue
        after = [e["fit"].get(entry["section"]) for e in hist if str(e.get("date")) > str(entry.get("date"))]
        after.append(fit.get(entry["section"]))
        after = [st for st in after if st]
        if len(after) < KW_SETTLE:
            continue
        entry["settled"] = True
        dirty = True
        now_rate = kw_rate(after[-KW_SETTLE:])
        sec = secs[entry["section"]]
        if now_rate > float(entry.get("before_rate") or 0) + KW_WORSE and sec.get("keywords") == entry.get("after"):
            changes.append((entry["section"], list(entry.get("before") or []),
                            {"date": day.isoformat(), "section": entry["section"], "undo_of": entry.get("date"),
                             "before": entry.get("after"), "after": list(entry.get("before") or []), "settled": True}))
            notes.append(L["keywords_undo_note"].format(section=title(entry["section"])))
            lines.append(f"{entry['section']}: the change of {entry.get('date')} made it worse "
                         f"({now_rate:.0%} off-topic after, {float(entry.get('before_rate') or 0):.0%} before): undone")
    undone = {c[0] for c in changes}

    # 2. Today's proposal, applied only with the evidence.
    prop = ed.get("keywords_proposal")
    if prop and not isinstance(prop, dict):
        lines.append("ignored keywords_proposal: it must look like {\"tech\": {\"add\": [...], \"remove\": [...]}}")
        prop = {}
    for sid, p in (prop or {}).items():
        why = None
        sec = secs.get(sid)
        recent = [e["fit"].get(sid) for e in hist[-(KW_WINDOW - 1):]] + [fit.get(sid)]
        heavy = sum(1 for st in recent if kw_heavy(st))
        last = max([str(x.get("date")) for x in log if x.get("section") == sid] + [""])
        current = [k for k in (sec or {}).get("keywords") or [] if isinstance(k, str)]
        add = p.get("add") if isinstance(p, dict) else None
        remove = p.get("remove") if isinstance(p, dict) else None
        add = [w.strip() for w in add or [] if isinstance(w, str)]
        remove = [w for w in remove or [] if isinstance(w, str)]
        have = {_fold(k) for k in current}
        new_words = []
        for w in add:
            if _fold(w) not in have and _fold(w) not in {_fold(x) for x in new_words}:
                new_words.append(w)
        if not sec:
            why = "no such section"
        elif kw_is_local(sec, cfg):
            why = "local news keeps no keywords"
        elif sid in undone:
            why = "its last change was just undone"
        elif last and (day - dt.date.fromisoformat(last[:10])).days < KW_COOLDOWN_DAYS:
            why = f"already changed on {last[:10]} (one change a week)"
        elif heavy < KW_NEEDED:
            why = (f"not enough ground: many off-topic candidates in {heavy} of the last {len(recent)} "
                   f"editions, {KW_NEEDED} needed")
        elif not new_words or not all(kw_valid_word(w) for w in add):
            why = "add 1-4 short words or phrases (letters, at most 3 words each, no links)"
        elif len(new_words) > KW_MAX_ADD:
            why = f"at most {KW_MAX_ADD} words per change"
        elif any(_fold(w) not in have for w in remove):
            why = "remove only words the section already has"
        elif len(remove) > len(new_words):
            why = "remove at most as many words as you add (keywords never shrink to a filter)"
        if why:
            lines.append(f"{sid}: proposal ignored: {why}")
            continue
        drop = {_fold(w) for w in remove}
        after = [k for k in current if _fold(k) not in drop] + new_words
        if len(after) > KW_MAX:
            lines.append(f"{sid}: proposal ignored: more than {KW_MAX} words; remove some")
            continue
        changes.append((sid, after, {"date": day.isoformat(), "section": sid, "before": current, "after": after,
                                     "before_rate": round(kw_rate([st for st in recent if st]), 3),
                                     "settled": False}))
        notes.append(L["keywords_note"].format(section=title(sid), words=", ".join(new_words)))
        lines.append(f"{sid}: applied (+{', +'.join(new_words)}"
                     + (f", -{', -'.join(remove)}" if remove else "") + f"; ground: {heavy} of {len(recent)} editions)")
    return fit, changes, notes, lines, dirty


def apply_keyword_changes(cfg, changes):
    secs = {s["id"]: s for s in cfg.get("sections") or []}
    log = cfg.get("keywords_log") if isinstance(cfg.get("keywords_log"), list) else []
    for sid, after, entry in changes:
        secs[sid]["keywords"] = after
        log.append(entry)
    cfg["keywords_log"] = log[-20:]


def word_count(t):
    return len(re.findall(r"\w+", t or ""))


def long_quotes(t):
    return [c for c in re.findall(r"[\"“«‘]([^\"”»’]+)[\"”»’]", t or "") if word_count(c) >= 15]


def label_file(folder, lang):
    """The shipped label file for a language: exact match, else the base language, else any regional
    file of it ("pt-PT" and "pt" use pt-BR.json). None if the language has no file."""
    base = lang.split("-")[0].lower()
    files = sorted(n[:-5] for n in os.listdir(folder) if n.endswith(".json"))
    return next((c for c in files if c.lower() == lang.lower()), None) \
        or next((c for c in files if c.lower() == base), None) \
        or next((c for c in files if c.lower().split("-")[0] == base), None)


def missing_labels(skill, cfg):
    """Keys still in English: the language ships no label file and config.labels lacks them."""
    lang = cfg.get("language") or "en"
    folder = os.path.join(skill, "assets", "i18n")
    if label_file(folder, lang):
        return []
    with open(os.path.join(folder, "en.json"), encoding="utf-8") as f:
        keys = [k for k in json.load(f) if not k.startswith("_") and k != "html_lang"]
    custom = cfg.get("labels") or {}
    return [k for k in keys if k not in custom]


def load_labels(skill, cfg):
    lang = cfg.get("language") or "en"
    folder = os.path.join(skill, "assets", "i18n")
    with open(os.path.join(folder, "en.json"), encoding="utf-8") as f:
        labels = json.load(f)
    # Exact file first; otherwise the base language or any regional file of it ("pt-PT" and "pt"
    # use pt-BR.json): labels in a close variant beat a page in English.
    match = label_file(folder, lang)
    if match and match != "en":
        with open(os.path.join(folder, f"{match}.json"), encoding="utf-8") as f:
            labels.update(json.load(f))
        if match.lower() != lang.lower():
            labels["html_lang"] = lang
    labels.update(cfg.get("labels") or {})
    labels.setdefault("html_lang", lang)
    return labels


LABEL_LISTS = {"weekdays": 7, "weekdays_short": 7, "months_short": 12, "months": 12}


def label_errors(L):
    out = []
    for k, n in LABEL_LISTS.items():
        if not isinstance(L.get(k), list) or len(L[k]) != n or not all(isinstance(x, str) for x in L[k]):
            out.append(f"labels.{k} must be a list of {n} texts")
    for k, v in L.items():
        if k.startswith("_") or k in LABEL_LISTS:
            continue
        if not isinstance(v, str):
            out.append(f"labels.{k} must be a text")
    return out


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
    # .get: a story with a bad ref is already an ERROR; it must not crash before that is printed.
    return (f'<{tag} class="display">{esc(n.get("title", ""))}</{tag}>\n'
            f'<p>{esc(n.get("text", ""))} <a href="{esc(n.get("url", ""))}" target="_blank" rel="noopener">'
            f'{esc(L["source"])}: {esc(n.get("outlet", ""))}</a></p>\n')


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
        items = [n for n in sections.get(sec["id"]) or [] if not n.get("brief")]
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


def briefs_html(cfg, sections, L):
    """The "In brief" column: stories that only have their title, one line each with the source,
    grouped by section in the config's order. Nothing when there is none."""
    groups = []
    for sec in cfg["sections"]:
        items = [n for n in sections.get(sec["id"]) or [] if n.get("brief")]
        if not items:
            continue
        lines = "".join(f'<p class="breve">{esc(n.get("title", ""))} <a href="{esc(n.get("url", ""))}" '
                        f'target="_blank" rel="noopener">{esc(n.get("outlet", ""))}</a></p>\n' for n in items)
        groups.append(f'<div class="breve-sec sc">{esc(sec["title"])}</div>\n{lines}')
    if not groups:
        return ""
    return (f'<section class="breves">\n<div class="cab sc">{esc(L["briefs_title"])}</div>\n'
            + "".join(groups) + "</section>\n")


def echoes(item, base):
    """True when a printed text tells nothing its title does not: fewer than 3 meaningful words
    beyond the collected title, the printed title and the outlet's name."""
    known = _stems(" ".join(str(x or "") for x in (base.get("title"), item.get("title"), base.get("outlet"),
                                                   item.get("outlet"))))
    known4 = {w[:4] for w in known}
    new = {w for w in _stems(item.get("text", "")) if w not in known and w[:4] not in known4
           and w not in {a[:5] for a in ATTRIBUTION}}
    return len(new) < 3


def main():
    """Any unexpected problem still ends in an ERROR line (nothing written), never a traceback."""
    try:
        rc = build()
        if isinstance(sys.stdout, _Tee):
            print(f"[exit {rc}]")
        return rc
    except Exception as e:  # pragma: no cover - the specific checks below should catch it first
        print(f"ERROR: could not build the edition ({type(e).__name__}: {str(e)[:160]})")
        print("Nothing was written. Fix edition.json (or the config/index) and run again.")
        return 1


def build():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skill")
    ap.add_argument("--config")
    ap.add_argument("--work", required=True)
    ap.add_argument("--index", help="current index.json of the newsstand; omit if it does not exist yet")
    ap.add_argument("--with-config", action="store_true", help="also write config.json into the output to publish")
    ap.add_argument("--with-page", action="store_true", help="kept for older instructions: index.html is now always written")
    ap.add_argument("--sample", action="store_true",
                    help="sample edition for a reader with no setup yet: adds the setup notice and never publishes config.json")
    ap.add_argument("--standalone", action="store_true",
                    help="a single page that is not added to the newsstand (test or 'don't publish')")
    ap.add_argument("--share", action="store_true",
                    help="like --standalone, for showing other people: says on the page what was left out")
    ap.add_argument("--single-page", action="store_true",
                    help="one page that replaces the previous one in the same artifact, carrying the reader's state")
    ap.add_argument("--replace", action="store_true",
                    help="reissue: replace today's published edition even if it has more stories")
    ap.add_argument("--unpack-state", metavar="FILE",
                    help="write WORK/config.json and WORK/index.json from the state copied from a single page")
    a = ap.parse_args()
    start_log(a.work, "assemble.py")
    if a.unpack_state:
        return unpack_state(a.unpack_state, a.work)
    if not (a.skill and a.config):
        ap.error("--skill and --config are required to build an edition")
    if sum(map(bool, (a.standalone, a.share, a.single_page))) > 1:
        ap.error("choose only one of --standalone, --share and --single-page")
    single = a.single_page
    standalone = a.standalone or a.share or single

    errors, warnings = [], []
    BRIEFED.clear()
    with open(a.config, encoding="utf-8") as f:
        cfg = json.load(f)
    with open(os.path.join(a.work, "edition.json"), encoding="utf-8") as f:
        ed = json.load(f)
    cpath = os.path.join(a.work, "collected.json")
    if not os.path.exists(cpath):
        # The collection is never skipped: without it there is nothing to check the stories against
        # (and an edition of one story found by hand looks complete when it is not).
        print("ERROR: WORK/collected.json not found: run collect.py first (step 2). With NETWORK BLOCKED, "
              "follow references/no-network.md and run collect.py --from-results. Then rewrite edition.json "
              "with the printed IDs.")
        print("Nothing was written.")
        return 1
    with open(cpath, encoding="utf-8") as f:
        collected = json.load(f)
    refs = {n["id"]: n for lst in (collected.get("news") or {}).values() for n in lst}
    refs.update({h["id"]: h for h in collected.get("history") or []})
    refs.update({d["id"]: d for d in collected.get("did_you_know") or [] if isinstance(d, dict) and "id" in d})
    L = load_labels(a.skill, cfg)
    bad_labels = label_errors(L)
    if bad_labels:
        for e in bad_labels:
            print("ERROR:", e)
        print("Nothing was written. Fix the labels in config.json and run again.")
        return 1
    untranslated = missing_labels(a.skill, cfg)
    if untranslated:
        print(f"WARNING: {len(untranslated)} labels are still in English for language "
              f"\"{cfg.get('language')}\" (no file in assets/i18n/): {', '.join(untranslated)}. "
              "Translate them into config.labels and save config.json.")
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
        return str(e.get("date") or "")

    undated = [e for e in old if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", d_of(e))]
    if undated:
        # An entry with no valid date cannot be placed on the shelf: it is dropped, and said so.
        warnings.append(f"{len(undated)} index entr{'y' if len(undated) == 1 else 'ies'} without a valid date "
                        "dropped from the index")
        old = [e for e in old if e not in undated]

    try:
        day = dt.date.fromisoformat(str(ed.get("date") or collected.get("date") or ""))
    except ValueError:
        print("ERROR: no valid date: set \"date\": \"YYYY-MM-DD\" in edition.json, or run collect.py first "
              "(its collected.json carries the date)")
        print("Nothing was written. Fix edition.json and run again.")
        return 1
    previous = [e for e in old if d_of(e) != day.isoformat()]
    existing = next((e for e in old if d_of(e) == day.isoformat()), None)
    number = existing.get("number") if existing and existing.get("number") else \
        max([e.get("number") or 0 for e in previous] + [0]) + 1
    try:
        founded = dt.date.fromisoformat((index or {}).get("founded") or (index or {}).get("fundado_em") or day.isoformat())
    except (TypeError, ValueError):
        founded = min([dt.date.fromisoformat(d_of(e)) for e in old] + [day])
    if day < founded and not standalone:
        errors.append(f"the edition date {day.isoformat()} is before the newsstand was founded "
                      f"({founded.isoformat()}); check the date")
    year_n = (day.year - founded.year) - ((day.month, day.day) < (founded.month, founded.day)) + 1
    weekend = day.weekday() >= 5
    section_ids = [s["id"] for s in cfg["sections"]]
    titles = {s["id"]: s["title"] for s in cfg["sections"]}
    used = set()

    def resolve(item, where):
        if not isinstance(item, dict):
            errors.append(f"{where}: must be an object like {{\"ref\": \"a1\", \"title\": \"...\", \"text\": \"...\"}}")
            return {}
        r = dict(item)
        # A section story only its title backs becomes a brief below: it needs no text.
        # Same rule as the conversion further down: no researched page of its own (no url, or the
        # collected one repeated).
        title_only = where != "headline" and r.get("ref") in refs \
            and (not item.get("url") or item.get("url") == refs[r["ref"]].get("url")) \
            and not (refs[r["ref"]].get("summary") or "").strip()
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
        for field in (("title",) if r.get("brief") or title_only else ("title", "text")):
            if not (r.get(field) or "").strip():
                errors.append(f"{where}: missing {field}")
        for q in long_quotes(r.get("title", "")) + long_quotes(r.get("text", "")) + long_quotes(r.get("deck", "")):
            errors.append(f"{where}: quote with 15+ words: “{q[:50]}…”")
        return r

    h = ed.get("headline")
    # A day with no story that passed the rules still gets its edition (agenda, classifieds, weather,
    # extras) with a short note in place of the headline: never an empty-handed run. A headline is
    # only optional when there is no story at all.
    secs = ed.get("sections") or {}
    no_news = not h and isinstance(secs, dict) and not any(secs.values())
    if not h:
        if not no_news:
            errors.append("missing headline (make the most relevant story the headline)")
        h = {}
    else:
        h = resolve(h, "headline")
    if h:
        if word_count(h.get("title")) > 14:
            warnings.append("headline has more than 14 words")
        if not h.get("deck"):
            errors.append("headline: missing deck")
    if h.get("brief"):
        errors.append("headline: a headline is never a brief; pick a story with a summary as headline")
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
        if not isinstance(items or [], list):
            errors.append(f"section '{sid}' must be a list of stories")
            continue
        sections[sid] = [r for r in (resolve(n, f"{sid}[{i}]") for i, n in enumerate(items or [])) if r]
        for n in sections[sid]:
            base = refs.get(n.get("ref") or "")
            # A story only its title backs has nothing to tell beyond that title: it is printed as a
            # brief (title and source), never as a paragraph that restates the title.
            if base and not n.get("brief") and not (base.get("summary") or "").strip() \
                    and n.get("url") == base.get("url"):
                n["brief"] = True
                BRIEFED.append(n["ref"])
            if n.get("brief"):
                n["text"] = ""
            if word_count(n.get("title")) > 12:
                warnings.append(f"{sid}: title over 12 words: {n.get('title', '')[:40]}")
    # A weekday next to a day number is checked against the calendar ("segunda-feira, 17" when the
    # 17th was a Tuesday): the one kind of date the model writes from its head.
    dated = [("headline", h)] + [(f"{sid}[{i}]", n) for sid, lst in sections.items() for i, n in enumerate(lst)]
    dated += [(f"classifieds[{i}]", c) for i, c in enumerate(ed.get("classifieds") or []) if isinstance(c, dict)]
    for where, item in dated:
        for field in ("title", "deck", "text"):
            for said, real, weekday in wrong_weekdays(str((item or {}).get(field) or ""), day, L):
                errors.append(f"{where}: \"{said}\" does not match the calendar: {real} is a {weekday}. "
                              "Write the weekday from the date, or leave the weekday out")
    if isinstance(ed.get("prep_note"), str):
        for said, real, weekday in wrong_weekdays(ed["prep_note"], day, L):
            errors.append(f"prep_note: \"{said}\" does not match the calendar: {real} is a {weekday}")
    # An attribution ("Veículos relatam…", "Segundo o X…") is how the paper hedges a story only small
    # outlets carry. Trimming text to clear a CHECK must never drop it: once a run had it for a ref,
    # a later run without it gets a warning. Kept in WORK/attributions.json between runs.
    apath = os.path.join(a.work, "attributions.json")
    try:
        with open(apath, encoding="utf-8") as f:
            had = set(json.load(f))
    except (OSError, ValueError, TypeError):
        had = set()
    now_has = set()
    for where, item in dated:
        ref = (item or {}).get("ref")
        if not ref or where.startswith("classifieds"):
            continue
        words = set(re.findall(r"[a-z]+", _fold(" ".join(str(item.get(k) or "") for k in ("title", "deck", "text")))))
        if words & ATTRIBUTION:
            now_has.add(ref)
        elif ref in had:
            warnings.append(f"{ref}: an earlier run attributed this story to its outlets (\"outlets report…\") "
                            "and this text states it as fact. Put the attribution back unless a larger "
                            "outlet or an opened page confirms it (SKILL.md step 3)")
    try:
        with open(apath, "w", encoding="utf-8") as f:
            json.dump(sorted(had | now_has), f)
    except OSError:
        pass
    # Each section's "count" range is for its own stories; the headline is apart and never counts.
    for sid, lst in sections.items():
        rng = ((next((s for s in cfg["sections"] if s["id"] == sid), {}).get("count") or {})
               .get("weekend" if weekend else "weekday") or [])
        lst = [n for n in lst if not n.get("brief")]  # a one-line brief does not take a story's place
        if len(rng) > 1 and len(lst) > rng[1]:
            warnings.append(f"{sid}: {len(lst)} stories, above its count of {rng[0]}-{rng[1]} "
                            "(the headline does not count): drop the weakest")
    # The collection marks stories that may tell the same fact (≈a1): both printed is one fact twice.
    printed_refs = [n.get("ref") for n in ([h] if h else []) + [x for v in sections.values() for x in v] if n.get("ref")]
    for r in printed_refs:
        twin = (refs.get(r) or {}).get("same_as")
        if twin in printed_refs:
            warnings.append(f"{r} and {twin} may tell the same fact (≈{twin}): keep only one unless they differ")
    total = (1 if h else 0) + sum(len(v) for v in sections.values())
    if total and collected.get("network_blocked") and not collected.get("from_results"):
        # The collection said NETWORK BLOCKED and the no-network searches were skipped: stories found
        # one by one leave every other section empty while the edition looks finished.
        errors.append("the collection printed NETWORK BLOCKED: follow references/no-network.md (one search per "
                      "section, all results in WORK/results.json, collect.py --from-results) before writing stories")
    h_sid = next((sid for sid, lst in (collected.get("news") or {}).items()
                  if h.get("ref") and any(n["id"] == h["ref"] for n in lst)), None)
    if not h_sid and h.get("section"):
        h_sid = next((sid for sid, t in titles.items() if t == h["section"]), None)
    filled = [sid for sid in section_ids if sections.get(sid) or sid == h_sid]
    empty = [sid for sid in section_ids if sid not in filled]
    limits = cfg.get("total_news") or {}
    if total > limits.get("max", 10):
        errors.append(f"{total} stories: the maximum is {limits.get('max', 10)}")
    usual = limits.get("weekend" if weekend else "weekday") or [0]
    if total < usual[0]:
        warnings.append(f"only {total} stories (usual minimum {usual[0]}); fine if it is a slow day")
    if len(usual) > 1 and total > usual[1]:
        warnings.append(f"{total} stories: above the usual {usual[0]}-{usual[1]} for "
                        f"{'a weekend' if weekend else 'a weekday'}; drop the weakest unless all are worth it")

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
    # A missing key prints "not connected". Easy to leave out by mistake when the connector WAS read
    # and came back empty (edition No. 009 said "Gmail not connected" over an empty inbox): say so.
    if not (a.share or a.sample or ed.get("sample")):
        for key, err, box, app in (("agenda", "agenda_error", "the agenda box", "Google Calendar"),
                                   ("classifieds", "classifieds_error", "the classifieds box", "Gmail")):
            if key not in ed and not ed.get(err):
                warnings.append(f"no \"{key}\" key: {box} will say {app} is not connected. If {app} was read "
                                f"(even with nothing in it), write \"{key}\": [] instead; leave it out only "
                                f"when {app} is not connected")
    classifieds = []
    for i, c in enumerate(ed.get("classifieds") if has_mail else []):
        c = dict(c)
        if c.get("url") and not str(c["url"]).startswith("https://mail.google.com/"):
            errors.append(f"classifieds[{i}]: link must be https://mail.google.com/...")
        long_numbers = [n for n in re.findall(r"\d{4,}", c.get("text", "")) if not re.fullmatch(r"(19|20)\d\d", n)]
        if long_numbers or re.search(r"[$€£¥]|R\$", c.get("text", "")):  # a year is fine; codes are not
            errors.append(f"classifieds[{i}]: looks like it contains an amount or a code; remove it")
        c.setdefault("tag", L["wanted_reply"])
        c["in_gmail"] = L["in_gmail"]
        classifieds.append(c)

    weather = collected.get("weather") if ed.get("weather", True) else None
    if isinstance(ed.get("weather"), dict):
        weather = ed["weather"]
    # The link is optional: a forecast from the app's own weather tool has no page. When given, it
    # must be https; "source" (optional) names where the numbers came from when there is no link.
    weather_url = str((weather or {}).get("url") or "")
    if weather and weather_url and not weather_url.startswith("https://"):
        errors.append(f"weather.url: not an https link ({weather_url[:60]}); leave \"url\" out when the "
                      "forecast has no page")
    # weather_condition only translates a collected condition that came in another language; one
    # already in the reader's language is printed as collected.
    reader_lang = str(cfg.get("language") or "en").split("-")[0].lower()
    if weather and ed.get("weather_condition") and not (
            not isinstance(ed.get("weather"), dict) and str(weather.get("condition_lang") or "").lower() == reader_lang):
        weather = dict(weather, condition=ed["weather_condition"])

    hist = ed.get("history") or {}
    dyk = ed.get("did_you_know") or {}
    hist = {"text": hist} if isinstance(hist, str) else dict(hist) if isinstance(hist, dict) else {}
    dyk = {"text": dyk} if isinstance(dyk, str) else dict(dyk) if isinstance(dyk, dict) else {}
    history_ids = {x["id"] for x in collected.get("history") or [] if isinstance(x, dict) and "id" in x}
    if hist.get("ref"):
        base = refs.get(hist["ref"])
        if hist["ref"] not in history_ids:
            errors.append(f"history: ref {hist['ref']} is not an 'On this day' candidate (h1, h2…)"
                          if base else f"history: ref {hist['ref']} is not in collected.json")
        else:
            hist.setdefault("url", base.get("url", ""))
    dyk_ids = {x["id"] for x in collected.get("did_you_know") or [] if isinstance(x, dict) and "id" in x}
    if dyk.get("ref"):
        if dyk["ref"] not in dyk_ids:
            errors.append(f"did_you_know: ref {dyk['ref']} is not a 'Did you know?' candidate (k1, k2…)")
        else:
            dyk.setdefault("url", refs[dyk["ref"]].get("url", ""))
    if dyk.get("text") and not str(dyk.get("url", "")).startswith("https://"):
        errors.append("did_you_know: missing the https link of the page that confirmed it (no confirmed page: leave it out)")
    for where, box in (("history", hist), ("did_you_know", dyk)):
        for q in long_quotes(box.get("text", "")):
            errors.append(f"{where}: quote with 15+ words: “{q[:50]}…”")
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
        plural(len(classifieds), "classified", "classifieds") if classifieds else (L["inbox_clear"] if has_mail else ""),
        f"{total} {L['news_items']}"]))
    summary_line = band.split(" · ", 1)[1] if " · " in band else band
    summary_line = summary_line[:1].upper() + summary_line[1:]
    shared_note = ""
    if a.share and not (has_agenda or has_mail):
        shared_note = L["shared_note_both"]
    elif a.share and not has_agenda:
        shared_note = L["shared_note_agenda"]
    elif a.share and not has_mail:
        shared_note = L["shared_note_mail"]

    # Keyword self-tuning: only for an edition that goes to the newsstand (or the single page).
    kw_fit, kw_changes, kw_notes, kw_lines, kw_dirty = {}, [], [], [], False
    if not sample and not (standalone and not single):
        kw_fit, kw_changes, kw_notes, kw_lines, kw_dirty = keyword_tuning(cfg, ed, collected, previous, day, L)

    def fmt_date(fmt):
        return fmt.format(weekday=L["weekdays"][day.weekday()], day=day.day,
                          month=L["months_short"][day.month - 1], year=day.year)

    text_h = (h.get("text") or "").strip()
    # An opening quote or bracket goes into the drop cap with the first letter ("“A…"), never alone.
    lead = re.match(r"[\"“«‘'(\[]*\w", text_h)
    first_letter = lead.group(0) if lead else text_h[:1]
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
        "CONDITION": (weather or {}).get("condition", ""), "URL_WEATHER": weather_url,
        "url_weather": bool(weather_url),
        "weather_source": bool(not weather_url and (weather or {}).get("source")),
        "WEATHER_SOURCE": (weather or {}).get("source", ""),
        "no_news": no_news, "headline": bool(h), "HEADLINE_SECTION": h_section, "HEADLINE_TITLE": h.get("title", ""),
        "HEADLINE_DECK": h.get("deck", ""),
        "SVG_HEADLINE": svg(SVG_ICON.get(h.get("icon"), SVG_ICON["newspaper"]), 56),
        "FIRST_LETTER": first_letter, "HEADLINE_REST": text_h[len(first_letter):],
        "URL_HEADLINE": h.get("url", ""), "OUTLET_HEADLINE": h.get("outlet", ""),
        "agenda_block": has_agenda or bool(agenda_failed) or not a.share, "agenda_free": has_agenda and not agenda,
        "agenda_off": not (has_agenda or agenda_failed or a.share),
        "mail_off": not (has_mail or mail_failed or a.share),
        "agenda_failed": bool(agenda_failed), "AGENDA_FAILED": agenda_failed,
        "mail_failed": bool(mail_failed), "MAIL_FAILED": mail_failed,
        "prep": bool(ed.get("prep_note")), "PREP_NOTE": ed.get("prep_note", ""),
        # The box is always there when Gmail was read, weekends too: empty = "inbox up to date".
        "classifieds_block": has_mail or bool(mail_failed) or not a.share,
        "classifieds_empty": has_mail and not classifieds,
        # Legacy (v1.4.0-v1.4.1): alerts now go in the edition summary; still accepted so older
        # edition files build. One neutral line, never which account or what happened.
        "security_alert": has_mail and bool(ed.get("security_alert")) and not a.share,
        "SECTIONS_HTML": sections_html(cfg, sections, L), "BRIEFS_HTML": briefs_html(cfg, sections, L),
        "week": bool(week),
        "extras": bool(hist.get("text") or dyk.get("text")),
        "history": bool(hist.get("text")), "HISTORY": hist.get("text", ""),
        "url_history": str(hist.get("url", "")).startswith("https://"), "URL_HISTORY": hist.get("url", ""),
        "didyouknow": bool(dyk.get("text")), "DIDYOUKNOW": dyk.get("text", ""),
        "url_didyouknow": str(dyk.get("url", "")).startswith("https://"), "URL_DIDYOUKNOW": dyk.get("url", ""),
        "FOOTER_CREDITS": footer,
        "shared_note": bool(shared_note), "SHARED_NOTE": shared_note, "newsstand_button": not standalone,
        "editor_note": bool(kw_notes), "EDITOR_NOTE": " ".join(kw_notes),
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
    # Field checks above already name the field behind a bad link; this one only catches the rest,
    # so one problem never prints two errors.
    if not errors:
        for href in re.findall(r'href="([^"]*)"', page):
            if not (href.startswith("https://") or (href == "../index.html" and not standalone)):
                errors.append(f"invalid link in page: {href[:60] or '(empty)'} (a story or box without an https link)")
    for tag in ("section", "div", "article", "p"):
        if len(re.findall(rf"<{tag}[\s>]", page)) != page.count(f"</{tag}>"):
            errors.append(f"unbalanced <{tag}> tags in page")

    # What step 6 should look at first: printed names, numbers and hedges the collected text does not
    # back. A headline with its own researched page is checked by the model against that page.
    CHECKS.clear()
    ECHOES.clear()
    items = [("headline", h)] if h and not (h.get("url") and h.get("url") != (refs.get(h.get("ref")) or {}).get("url")) else []
    base_h = refs.get(h.get("ref") or "") if h else None
    if base_h and h.get("url") and h.get("url") != base_h.get("url") and base_h.get("outlet") \
            and _fold(base_h.get("outlet")) != _fold(h.get("outlet")) \
            and _fold(base_h["outlet"]) not in _fold(" ".join(str(h.get(k) or "") for k in ("title", "deck", "text"))):
        # The printed credit is the opened page; a fact only the collected title or summary carries
        # (e.g. who asked for the update) is then credited to a page that never says it.
        CHECKS.append(f"headline ({h['ref']}): the printed source is {h.get('outlet')}. A fact that page does "
                      f"not state but the collected title or summary from {base_h['outlet']} does must be "
                      f"attributed to {base_h['outlet']} in the text (\"Segundo a {base_h['outlet']}, …\", in the "
                      "reader's language), or come out. Nothing to fix if every fact is on that page")
    items += [(n.get("ref") or sid, n) for sid, lst in sections.items() for n in lst]
    items += [("history", hist), ("did_you_know", dyk)]
    for where, item in items:
        base = refs.get(item.get("ref") or "")
        if not base:
            continue
        # The outlet counts as source text: "Segundo o BPMoney" names where the fact came from.
        source = " ".join(str(base.get(k) or "") for k in ("year", "title", "summary", "text", "extract", "outlet"))
        if "id" in base:
            source += " " + date_words(base.get("date"))
        written = [str(item.get(k) or "") for k in ("title", "deck", "text")]
        title_only = "id" in base and not (base.get("summary") or base.get("text") or base.get("extract"))
        if item.get("brief"):
            title_only = False  # a brief is its title: only names and numbers are worth a look
        elif base.get("summary") and item.get("text") and echoes(item, base):
            ECHOES.append(f"{where}" + (f" ({item['ref']})" if item.get("ref") and item["ref"] != where else "")
                          + ": the text only restates the title; tell what the collected summary adds "
                            "(who, where, when, how many, what happens next), or set \"brief\": true")
        notes = unsupported(written, source, title_only)
        plural = overstated_attribution(written, base, refs) if "id" in base else None
        for note in notes + ([plural] if plural else []):
            CHECKS.append(f"{where}" + (f" ({item['ref']})" if item.get("ref") and item["ref"] != where else "")
                          + f": {note}")

    for w in warnings:
        print("WARNING:", w)
    if errors:
        for e in errors:
            print("ERROR:", e)
        print("Nothing was written. Fix edition.json and run again.")
        return 1

    # A reissue never silently replaces a fuller edition of the same day (an afternoon run with the
    # network blocked can bring 2 stories where the morning had 5). Nothing is written; the model
    # keeps the published edition unless the reader chooses to replace it (--replace).
    if existing and not standalone and not a.replace:
        # "stories" since v1.13.0: link_ids also hold a story's second address (Google News and the
        # outlet's page), so they no longer count stories.
        before = existing.get("stories") if isinstance(existing.get("stories"), int) else \
            len(existing.get("link_ids") or existing.get("links") or []) or (len(existing.get("titles") or []) + 1 if existing.get("headline") else 0)
        if before > total:
            print(f"KEEP: today's edition No. {number:03d} is already published with {before} stories; "
                  f"this reissue has {total}. Nothing was written.")
            print("  Scheduled run: publish nothing; reply with the normal summary of the published edition "
                  f"(headline: {existing.get('headline', '')}).")
            print("  Interactive run: ask the reader in one line whether to replace it (it has fewer stories). "
                  "If yes, run again with --replace; if not, keep it and say so in one line.")
            return 3

    if kw_changes or kw_dirty:
        apply_keyword_changes(cfg, kw_changes)
        with open(a.config, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    for line in kw_lines:
        print("KEYWORDS:", line)

    if standalone and not single:
        # Nothing goes to the newsstand: no index is written, so a copy can never replace the
        # morning entry by mistake if someone publishes WORK/archive later.
        out_dir = os.path.join(a.work, "standalone")
        os.makedirs(out_dir, exist_ok=True)
        path = os.path.join(out_dir, f"{day.isoformat()}.html")
        with open(path, "w", encoding="utf-8") as f:
            f.write(page)
        print(f"OK: {L['issue_label']} {number:03d} · {day.isoformat()} · {total} stories · "
              f"{'SHARE COPY' if a.share else 'STANDALONE'}")
        print("HEADLINE:", h.get("title", "") or "(none: no story today; the summary adds a Missing line for the news)")
        print(f"NOT FOR THE NEWSSTAND: send this file to the reader: {os.path.abspath(path)}")
        coverage(total, filled, empty, titles)
        next_steps(False, standalone=True)
        return 0

    stories = ([h] if h else []) + [n for v in sections.values() for n in v]
    entry = {
        "date": day.isoformat(), "number": number, "weekday": L["weekdays"][day.weekday()],
        "type": "sample" if sample else ("weekend" if weekend else "morning"),
        "headline": h.get("title", "") or (L["no_news_title"] if no_news else ""), "summary": summary_line,
        "file": f"editions/{day.isoformat()}.html",
        "extras": {"history": hist.get("summary") or short(hist.get("text", "")),
                   "did_you_know": dyk.get("summary") or short(dyk.get("text", ""))},
        "stories": total,  # what the reissue guard compares (link_ids may hold two per story)
        "titles": [n.get("title", "") for n in stories[1:]],
        # The titles as collected (before rewriting): what the next collections are compared against.
        "source_titles": [refs[n["ref"]].get("title", "") for n in stories if n.get("ref") in refs],
        # Fingerprints, not the links: Google News redirect URLs are long, and the index is read by
        # every edition. collect.py compares fingerprints the same way.
        "link_ids": sorted({link_id(u) for n in stories
                            for u in (n.get("url"), (refs.get(n.get("ref") or "") or {}).get("alt_url")) if u}),
    }
    if kw_fit:
        # Per section [candidates, off-topic ones]: the ground for adjusting keywords (KW_WINDOW editions).
        entry["fit"] = kw_fit
    archive_labels = {k: L[k] for k in ("html_lang", "archive_title", "archive_kicker", "archive_subtitle",
                                        "latest_edition", "previous_editions", "archive_empty", "archive_error",
                                        "weekend_tag", "sample_tag", "issue_label", "months_short", "date_short_format")}
    new = {"newspaper": news_name, "founded": (index or {}).get("founded") or (index or {}).get("fundado_em")
           or day.isoformat(), "labels": archive_labels, "editions": [entry] + previous}
    new["editions"].sort(key=d_of, reverse=True)
    for e in new["editions"]:
        if "links" in e:  # entries written before v1.9.0
            e["link_ids"] = sorted({link_id(u) for u in e.pop("links") if u} | set(e.get("link_ids") or []))
    for e in new["editions"][DEDUP_EDITIONS:]:
        for k in ("titles", "source_titles", "links", "link_ids", "fit"):
            e.pop(k, None)

    if single:
        # One page per artifact: today's edition replaces yesterday's, and the state block keeps
        # config, numbering and the repeat checks alive between runs. The page title is the
        # newspaper's name, so the artifact keeps one stable name.
        page = re.sub(r"<title>.*?</title>", f"<title>{esc(news_name)}</title>", page, count=1)
        cfg_state = dict(cfg)
        page = page.replace('<meta charset="utf-8">', '<meta charset="utf-8">\n' + state_block(cfg_state, new), 1)
        out_dir = os.path.join(a.work, "single")
        os.makedirs(out_dir, exist_ok=True)
        path = os.path.join(out_dir, "index.html")
        with open(path, "w", encoding="utf-8") as f:
            f.write(page)
        print(f"OK: {L['issue_label']} {number:03d} · {day.isoformat()} · {total} stories · SINGLE PAGE"
              f"{' · REISSUE' if existing else ''}")
        print("HEADLINE:", h.get("title", "") or "(none: no story today; the summary adds a Missing line for the news)")
        print(f"ARTIFACT TITLE: {news_name}")
        print(f"PUBLISH this one file as the artifact's page (from disk, never pasted): {os.path.abspath(path)}")
        coverage(total, filled, empty, titles)
        next_steps(True)
        return 0

    stand_title = f"{news_name} · {L['archive_title']}"
    dest = os.path.join(a.work, "archive")
    os.makedirs(os.path.join(dest, "editions"), exist_ok=True)
    with open(os.path.join(dest, "editions", f"{day.isoformat()}.html"), "w", encoding="utf-8") as f:
        f.write(page)
    with open(os.path.join(dest, "editions", "index.json"), "w", encoding="utf-8") as f:
        json.dump(new, f, ensure_ascii=False, indent=1)
    publish = [f"editions/{day.isoformat()}.html", "editions/index.json"]
    # The publishing tool needs the newsstand page in every publish, and the page's own <title>
    # names the artifact: so index.html is always rebuilt from the template with the right title.
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
    config_changed = bool(collected.get("config_changed")) or os.path.exists(os.path.join(a.work, "config.changed"))
    if (index is None or legacy or a.with_config or kw_changes or kw_dirty or config_changed) and not sample:
        shutil.copy(a.config, os.path.join(dest, "config.json"))
        publish.append("config.json")
    print(f"OK: {L['issue_label']} {number:03d} · {day.isoformat()} · {total} stories"
          f"{' · REISSUE' if existing else ''}")
    print("HEADLINE:", h.get("title", "") or "(none: no story today; the summary adds a Missing line for the news)")
    print(f"NEWSSTAND TITLE: {stand_title}")
    print("PUBLISH (as -> path; index.html is the newsstand's main page, never an edition):")
    for p in publish:
        print(f"  {p} -> {os.path.abspath(os.path.join(dest, p))}")
    coverage(total, filled, empty, titles)
    next_steps(False)
    return 0


def coverage(total, filled, empty, titles):
    """What the edition really carries: the summary (step 8) is written from this line, never from the plan."""
    print(f"COVERAGE: {total} stor{'y' if total == 1 else 'ies'} · with stories: "
          f"{', '.join(titles[s] for s in filled) or 'none'} · empty: {', '.join(titles[s] for s in empty) or 'none'}")
    if empty:
        print("  The summary's Missing line names the empty sections (or says no news was confirmed, when all are). "
              "Never describe the edition as covering them.")


CHECKS = []
ECHOES = []    # texts that only restate their title
BRIEFED = []   # title-only stories the script printed as briefs


def next_steps(single, standalone=False):
    """What is left after the files are written, printed where the model reads it."""
    if BRIEFED:
        print("BRIEFS: " + ", ".join(BRIEFED) + " printed in the briefs column (title and source only): only "
              "their title backs them. Nothing to fix.")
    for e in ECHOES:
        print("ECHO:", e)
    for c in CHECKS:
        print("CHECK:", c)
    if CHECKS:
        print("  Each CHECK names words the collected text does not carry. Keep them only if they are a "
              "paraphrase or come from the page you opened for the headline; otherwise remove them (step 6). "
              "A CHECK is a hint, not a score: never remove an attribution (\"outlets report…\") or a hedge "
              "to clear one.")
    print("NEXT (mandatory, in order):")
    print("  6. Check every sentence against what backs it (collected title and summary, a page you opened, "
          "the Wikipedia text); remove what is not there, and rerun this script if anything changed.")
    if standalone:
        print("  7. Nothing to publish: send the file above to the reader, with one sentence on why there is "
              "no newsstand (references/modes.md).")
    else:
        print("  7. Then publish exactly the file" + ("" if single else "s") + " above, nothing else.")
    print("  8. Reply with the edition summary (SKILL.md step 8): at most 4 lines, in the reader's language, "
          "built from the OK and COVERAGE lines above (never from the plan), no process, sources, network "
          "or script details.")


if __name__ == "__main__":
    sys.exit(main())
