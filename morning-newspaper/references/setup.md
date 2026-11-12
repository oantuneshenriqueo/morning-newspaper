# First-run setup

Run this only in an interactive session, when there is no newsstand or it has no `config.json`, or when the reader asks to change their newspaper. Speak in the language the user is writing in.

## 1. Ask (one message, at most 5 short questions)

Ask only what the conversation or connected tools have not already answered:
1. What should the newspaper call you? (first name or nickname)
2. Which city should the weather and local news cover?
3. Which topics do you want? Offer the defaults in `config.example.json` as a starting point (technology/AI/security, local news, personal finance, games) and let them add, remove or rename sections.
4. Newspaper name: keep the default for their language (`default_newspaper_name` in `assets/i18n/`, e.g. "Morning Newspaper", "O Jornal Matinal") or choose another?
5. What time should the paper be ready? (for the daily schedule; default 7:00)

The language is the one they are writing in; confirm it only if it is unclear.

## 2. Build config.json

Start from `references/config.example.json` and fill in:
- `language`: BCP-47 tag (e.g. `pt-BR`, `es`, `en-GB`). `timezone`: IANA name for their city.
- `reader.name`, `newspaper.name`, `newspaper.motto` (write a short retro motto in their language).
- `city`: name as used in the news, plus latitude and longitude (look them up; one web search is fine).
- `news_locale`: Google News parameters for their country and language (`hl`, `gl`, `ceid`), e.g. Brazil `pt-BR` / `BR` / `BR:pt-419`; Spain `es` / `ES` / `ES:es`; US `en-US` / `US` / `US:en`.
- `wikipedia_lang`: their Wikipedia language code (`pt`, `es`, `en`, …).
- `sections`: for each topic, an `id` (short, lowercase), a `title` in their language, a `layout` (`main` for the widest section, usually the first; `half` for two short sections shown side by side; `single` for a full-width short section), an `interest` sentence, `count` per weekday/weekend, 2–5 search `queries` in their language (short, no dates) and optional RSS `feeds` (https only).
- `history_keywords`: 10–20 words in their language for preferred "On this day" topics, based on their interests.
- `labels`: leave `{}` if `assets/i18n/` has their language (en, pt-BR, es). Otherwise translate every key of `assets/i18n/en.json` (keep the `{placeholders}` and the 7 weekdays / 12 months order).

Never put emails, phone numbers, addresses or anything sensitive in the config. It holds only what the newspaper needs.

## 3. Save it

The config lives in the reader's newsstand, next to the editions. Run the edition flow normally from step 2 with `WORK/config.json`; `assemble.py` adds `config.json` to the files to publish when the newsstand is new. To change the config of an existing newsstand, rerun `assemble.py` with `--with-config` (or publish just `config.json` in patch mode).

Show the reader a 3–4 line summary of what was configured (in their language) and tell them they can ask for changes at any time. Then offer the daily schedule once.
