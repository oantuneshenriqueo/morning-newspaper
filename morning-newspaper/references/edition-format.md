# edition.json format

The only text you write per edition, in the reader's language. `scripts/assemble.py` turns it into HTML, escapes everything, drops empty sections, computes issue number / year / top band, and updates the newsstand index.

```json
{
  "headline": {"ref": "a4", "title": "...", "deck": "...", "text": "3 to 4 sentences.", "icon": "chip"},
  "agenda": [{"time": "8:00", "event": "Team meeting"}],
  "prep_note": "Tomorrow morning: ...",
  "classifieds": [{"text": "...", "url": "https://mail.google.com/mail/u/0/#inbox/ID"}],
  "sections": {
    "tech":  [{"ref": "a6", "title": "...", "text": "1 to 2 sentences."}],
    "local": [{"ref": "b2", "title": "...", "text": "..."},
              {"ref": "b5", "title": "...", "brief": true}]
  },
  "history": {"ref": "h1", "text": "In 2020, ..."},
  "did_you_know": {"ref": "k1", "text": "..."},
  "weather_condition": "optional: the condition translated into the reader's language",
  "week": ["Sundays only, optional: 3 lines"]
}
```

Rules:
- `agenda` and `classifieds`: a list (possibly empty) when the connector was read; an empty list prints "free agenda" / "inbox up to date". Leave the key out when Calendar or Gmail is not connected: the box says it is not connected. Connected but failing after a second try: `"agenda_error": "reason in a few words"` (or `"classifieds_error"`; `true` when the reason is unknown): the box says it could not be read and why. In a copy to share (`--share`) a left-out key hides the box instead.
- `security_alert`: not used since v1.4.2 (security alerts go in the **Attention** line of the edition summary, SKILL.md step 8). Still accepted, so older edition files build: it adds one neutral line to the classifieds box.
- The classifieds box is printed every day when Gmail was read, weekends included: an empty list prints "inbox up to date".
- `history` uses an "On this day" candidate (`h1`, `h2`…), never a news ref. Without a collected `h` ref (fallback search): `{"text": "In 1969, ...", "url": "https://source"}`.
- `did_you_know`: a collected candidate (`"ref": "k1"`), or, without one, `{"text": "...", "url": "https://page-that-confirmed-it"}`; nothing confirmed, leave it out.
- Keys under `sections` are the section `id`s from config.json. Missing or empty = the section is not printed.
- `ref` is a collected ID (`a1`, `b3`, `h2`…). URL, outlet and date are filled in automatically. For a story found outside the collection (fallback search), replace `ref` with `"url": "https://..."` and `"outlet": "Name"`.
- The headline's section label is taken from its `ref`; set `"section"` only to override it.
- `brief: true` (section stories only): printed in the "In brief" column as its title and source, with no text. Used for a story with only its title (`assemble.py` sets it by itself for those and prints `BRIEFS:`), or one with a summary that is worth only a line. Briefs count in `total_news`, not in their section's `count`. A text that only restates its title gets an `ECHO:` line.
- Headline researched in another page: keep its `ref` (the repeat checks need it) and add `"url"` and `"outlet"` of the page whose facts you used. They replace the collected link and outlet in the printed source.
- `icon` (headline illustration): pick the one that fits the subject; an unknown name or none prints `newspaper`.
  - Politics and society: `capitol` (government), `ballot` (elections), `gavel` (courts, justice), `shield` (security, defense), `megaphone` (protests, announcements), `people` (society, population), `globe` (world), `city` (city, region).
  - Economy: `coin` (money, interest), `chart` (markets, indexes), `briefcase` (jobs), `cart` (shopping, retail), `fuel` (fuel prices), `bolt` (energy), `wheat` (farming), `house` (housing, real estate).
  - Science and technology: `chip` (hardware), `robot` (AI), `lock` (cybersecurity), `phone` (phones, apps), `wifi` (internet), `flask` (science), `rocket` (space).
  - Daily life: `heart` (health), `leaf` (environment), `thermometer` (weather, heat, cold), `book` (education, books), `car` (traffic, cars), `bus` (public transport), `plane` (flights, travel).
  - Culture and sport: `gamepad` (games), `film` (cinema, TV), `music` (music), `ball` (sport, football), `trophy` (championships, awards), `newspaper` (anything else).
- `weather`: omit to use the collected forecast; `false` removes the box; or an object `{"max": 27, "min": 17, "condition": "...", "icon": "cloud", "url": "https://..."}` from a fallback (icons: `sun`, `sun-cloud`, `cloud`, `rain`, `storm`, `snow`). `url` is the page the numbers came from, and only when there is one: a forecast from the app's own weather tool has none, so leave `url` out and set `"source": "<the tool's name, in a few words>"`. Never link a page the numbers did not come from. If the collected condition is in another language, set `weather_condition`; for a condition already in the reader's language it is ignored.
- Classifieds: `tag` is optional (defaults to the "reply wanted" label; use the `resolved` label for resolved ones). Links only to `https://mail.google.com/`; no amounts, codes or long numbers (the script refuses them).
- Sample editions (scheduled run before setup, see `references/sample.md`) are made with `assemble.py --sample`; nothing changes in the JSON.
- `band` (top strip) is computed; set it only to replace the text. `date` is optional (defaults to the collection date).

The script refuses (and writes nothing) when: `WORK/collected.json` is missing, the collection printed `NETWORK BLOCKED` and the edition has stories but the no-network searches were not done (`collect.py --from-results`), a link is missing or not https, an outlet is missing, a `ref` does not exist or is repeated, a quote has 15+ words (titles and extras included), "Did you know?" has no https link, the weather `url` is given but not https, "On this day" uses a news ref, the date is before the newsstand was founded, there are more stories than `total_news.max`, the headline is missing while there are section stories (only a day with no story at all goes without one), the headline deck is missing, a section id is not in the config, a weekday next to a day number does not match the calendar ("Monday, Nov. 17" when the 17th was a Tuesday), or a template marker is left in the page. Fix the JSON and run again. Warnings (long titles, fewer or more stories than the usual range for the day, a section above its own `count` (the headline never counts there), two stories marked as possibly the same fact) do not block. `off_topic` (list of candidate refs left out as not fitting their section) and `keywords_proposal` (`{"<section id>": {"add": [...], "remove": [...]}}`) are optional; SKILL.md, step 4, says when. `assemble.py` prints `KEYWORDS:` lines for them and keeps per section `[candidates, off-topic]` in the index entry (`fit`), with the changes in `config.json`'s `keywords_log`.

After `OK:`, `CHECK:` lines name words of a printed item that its collected text does not carry (names, numbers, a dropped hedge) and, for a headline credited to another page, remind you to attribute to the collected outlet what only it says; step 6 starts with them. A story that had "outlets report…" in an earlier run and lost it gets a warning.
