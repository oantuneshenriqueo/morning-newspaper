# First-run setup

Run this only in an interactive session, when there is no newsstand or it has no `config.json`, or when the reader asks to change their newspaper. Speak in the language the user is writing in.

## 1. Check the connections first (before any question)

The agenda comes from Google Calendar and the emails waiting for a reply from Gmail. Check whether their tools are available in this session.
- If one is missing, search the connector registry for it and suggest it right away, so the connect button appears before the questions. One sentence is enough: without Calendar there is no agenda; without Gmail there are no emails waiting for a reply.
- Do not wait for the reader to connect: continue with the questions. Whatever gets connected is used from the first edition on.

## 2. Offer two ways to start (one message)

In a single short message:
- **Quick start:** "Just tell me your city" (and, if unclear, their name). Everything else uses the defaults below and can be changed later; the delivery time is asked when the schedule is offered.
- **Personalize:** up to five questions, asking only what the conversation has not already answered:
  1. What should the newspaper call you? (first name or nickname)
  2. Which city should the weather and local news cover?
  3. Which topics? Offer the defaults (technology/AI/security, local news, personal finance, games) and let them add, remove or rename sections.
  4. Newspaper name: keep the default for their language (`default_newspaper_name` in `assets/i18n/`, e.g. "Morning Newspaper", "O Jornal Matinal") or choose another?
  5. What time should the paper be ready? (for the daily schedule; default 7:00)

End the message with one line on privacy, in their language, e.g.: "Your answers are saved only in your private newsstand; nothing is sent or shared."

If the reader answers only with a city, treat it as the quick start.

## 3. Build config.json

Start from `references/config.example.json` and fill in:
- `language`: BCP-47 tag (e.g. `pt-BR`, `es`, `en-GB`). `timezone`: IANA name for their city.
- `reader.name` (may be empty in the quick start), `newspaper.name` (leave it out to use the default for the language), `newspaper.motto` (a short retro motto in their language).
- `city`: name as used in the news, plus latitude and longitude (one web search is fine).
- `news_locale`: Google News parameters for their country and language (`hl`, `gl`, `ceid`), e.g. Brazil `pt-BR` / `BR` / `BR:pt-419`; Spain `es` / `ES` / `ES:es`; US `en-US` / `US` / `US:en`.
- `wikipedia_lang`: their Wikipedia language code (`pt`, `es`, `en`, …).
- `sections`: quick start → the four default sections, with `title` and `queries` translated into their language and the `local` section pointed at their city. Personalized → for each topic an `id` (short, lowercase), a `title` in their language, a `layout` (`main` for the widest section, usually the first; `half` for two short sections shown side by side; `single` for a full-width short section), an `interest` sentence, `count` per weekday/weekend, 2–5 search `queries` in their language (short, no dates) and optional RSS `feeds` (https only). Put the country or region in the local and finance queries (e.g. "Valencia", "Comunitat Valenciana", "España inflación"): Google News mixes in other countries that share the language otherwise.
- `history_keywords`: 10–20 words in their language for preferred "On this day" topics.
- `did_you_know_themes` (optional): 20–40 short themes for "Did you know?" tied to their interests. Leave it out to use the built-in technology themes.
- `labels`: leave `{}` if `assets/i18n/` has their language (en, pt-BR, es). Otherwise translate every key of `assets/i18n/en.json` (keep the `{placeholders}` and the 7 weekdays / 12 months order).

Never put emails, phone numbers, addresses or anything sensitive in the config. It holds only what the newspaper needs.

## 4. Save it and print the first edition

The config lives in the reader's newsstand, next to the editions. Run the edition flow from step 2 of SKILL.md with `WORK/config.json`; `assemble.py` adds `config.json` to the files to publish when the newsstand is new. If a newsstand already exists from sample editions (no `config.json`), keep it: run `assemble.py` with `--index` and `--with-config`; numbering simply continues. To change the config of an existing newsstand, rerun `assemble.py` with `--with-config` (or publish just `config.json` in patch mode).

After the edition, reply in their language with 3–4 lines: today's headline, what was configured, which connections are still missing (if any), the newsstand slug, and that they can ask for changes at any time. Then offer the daily schedule once (ask the time if the quick start skipped it).
