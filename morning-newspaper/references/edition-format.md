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
    "local": [{"ref": "b2", "title": "...", "text": "..."}]
  },
  "history": {"ref": "h1", "text": "In 2020, ..."},
  "did_you_know": {"text": "...", "url": "https://source-that-confirmed-it"},
  "weather_condition": "optional: the condition translated into the reader's language",
  "week": ["Sundays only, optional: 3 lines"]
}
```

Rules:
- `agenda` and `classifieds`: a list (possibly empty) when the connector was read; an empty list prints "free agenda" / "inbox up to date". Leave the key out when Calendar or Gmail is not connected: the box disappears.
- `history` without a collected `h` ref (fallback search): `{"text": "In 1969, ...", "url": "https://source"}`.
- Keys under `sections` are the section `id`s from config.json. Missing or empty = the section is not printed.
- `ref` is a collected ID (`a1`, `b3`, `h2`…). URL, outlet and date are filled in automatically. For a story found outside the collection (fallback search), replace `ref` with `"url": "https://..."` and `"outlet": "Name"`.
- The headline's section label is taken from its `ref`; set `"section"` only to override it.
- Headline researched in another page: keep its `ref` (the repeat checks need it) and add `"url"` and `"outlet"` of the page whose facts you used. They replace the collected link and outlet in the printed source.
- `icon` (headline illustration): `lock`, `chip`, `coin`, `chart`, `gamepad`, `city`, `robot` or `newspaper`.
- `weather`: omit to use the collected forecast; `false` removes the box; or an object `{"max": 27, "min": 17, "condition": "...", "icon": "cloud", "url": "https://..."}` from a fallback search (icons: `sun`, `sun-cloud`, `cloud`, `rain`, `storm`). If the collected condition is in another language, set `weather_condition`.
- Classifieds: `tag` is optional (defaults to the "reply wanted" label; use the `resolved` label for resolved ones). Links only to `https://mail.google.com/`; no amounts, codes or long numbers (the script refuses them).
- Sample editions (scheduled run before setup, see `references/sample.md`) are made with `assemble.py --sample`; nothing changes in the JSON.
- `band` (top strip) is computed; set it only to replace the text. `date` is optional (defaults to the collection date).

The script refuses (and writes nothing) when: a link is missing or not https, an outlet is missing, a `ref` does not exist or is repeated, a quote has 15+ words, there are more stories than `total_news.max`, the headline deck is missing, a section id is not in the config, or a template marker is left in the page. Fix the JSON and run again. Warnings (long titles, few stories) do not block.
