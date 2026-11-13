# First-run setup

Run this only in an interactive session, when there is no newsstand or it has no `config.json`, or when the reader asks to change their newspaper. Speak in the language the user is writing in.

## 1. Check the connections first (before any question)

The agenda comes from Google Calendar and the emails waiting for a reply from Gmail. Check whether their tools are available in this session.
- If one is missing, search the connector registry for it and suggest it right away, so the connect button appears before the questions. One sentence is enough: without Calendar there is no agenda; without Gmail there are no emails waiting for a reply.
- Do not wait for the reader to connect: continue with the questions. Whatever gets connected is used from the first edition on.

## 2. Ask (clickable choices when available)

Ask with the session's multiple-choice question tool when there is one (e.g. `AskUserQuestion`): the reader clicks instead of typing, which is what keeps the personalized setup at about a minute. Without such a tool, ask the same questions in **one** message with numbered options. Write everything in the reader's language.

Rules for every question:
- Every option is a real choice. Never add an option that only means "I'll type it": the tool already has its own free-text field (its label changes between apps, so never name it). When free text makes sense, add "(you can also write your own)" to the question.
- Put the default first and mark it "(Recommended)". A skipped question means its default.
- At most 4 options per question.

**Screen 1** (one question): "How do you want to start?"
- **Personalize (Recommended)**: "About 1 minute: topics, delivery time and subjects you would rather not see."
- **Quick start**: "Just tell me your city. Everything else uses the defaults and can be changed later."

**Screen 2** (only for Personalize; one call, three questions):
1. **Topics** (multi-select; "you can pick several or write others"): the four default sections, each with a one-line description: technology/AI/security, news from your city, personal finance, games. Topics the reader writes become extra sections.
2. **Delivery time**: "7:00 (Recommended)", "6:00", "Another time" and "Don't schedule for now". "Another time" → ask for the time in one short line of text.
3. **Subjects you would rather not see** (multi-select; "you can pick several or write others"): "Nothing, show me everything" (default), "Politics", "Crime and tragedies" and the most followed sport in the reader's country (e.g. "Football"). If "Nothing" is picked together with a subject, the subjects win.

**Then one line of text** (both paths): the city for the weather and local news (required) and what the newspaper should call them (optional), plus the privacy line, e.g.: "Your answers are saved only in your private newsstand; nothing is sent or shared." If the city is already clear from the conversation, ask to confirm it instead.

The newspaper's name is not asked: it uses the default for the language (`default_newspaper_name` in `assets/i18n/`). Readers who want another name can ask for it at any time; it is a one-line change to `newspaper.name`.

If the reader answers screen 1 only with a city, treat it as the quick start.

## 3. Build config.json

Start from `references/config.example.json` and fill in:
- `language`: BCP-47 tag (e.g. `pt-BR`, `es`, `en-GB`). `timezone`: IANA name for their city.
- `reader.name` (may be empty), `newspaper.name` (leave it out: the default for the language is used), `newspaper.motto` (a short retro motto in their language).
- `city`: name as used in the news, plus latitude and longitude (one web search is fine).
- `news_locale`: Google News parameters for their country and language (`hl`, `gl`, `ceid`), e.g. Brazil `pt-BR` / `BR` / `BR:pt-419`; Spain `es` / `ES` / `ES:es`; US `en-US` / `US` / `US:en`.
- `wikipedia_lang`: their Wikipedia language code (`pt`, `es`, `en`, …).
- `sections`: quick start → the four default sections, with `title` and `queries` translated into their language and the `local` section pointed at their city. Personalized → for each topic an `id` (short, lowercase), a `title` in their language, a `layout` (`main` for the widest section, usually the first; `half` for two short sections shown side by side; `single` for a full-width short section), an `interest` sentence, `count` per weekday/weekend, 2–5 search `queries` in their language (short, no dates) and optional RSS `feeds` (https only). Put the country or region in the local and finance queries (e.g. "Valencia", "Comunitat Valenciana", "España inflación"): Google News mixes in other countries that share the language otherwise.
- `history_keywords`: 10–20 words in their language for preferred "On this day" topics.
- `avoid` (optional): words or short phrases the reader does not want to see, in their language. Only what the reader asked for: leave it `[]` in the quick start, when they picked "Nothing" or skipped, and never fill it in on your own. A subject picked from the list ("Politics") becomes at most 5 obvious words for it, singular and plural included (e.g. "politics", "election", "elections", "party", "government"), shown to the reader in the final summary so they can change them; words the reader wrote go in as written. It applies to every news section and to "On this day", matching whole words only ("war" does not hide "software"), ignoring case and accents; include the variants that matter (singular and plural). A section may also carry its own `avoid` list.
- `did_you_know_themes` (optional): 20–40 short themes for "Did you know?" tied to their interests. Leave it out to use the built-in technology themes.
- `labels`: leave `{}` if `assets/i18n/` has their language (en, pt-BR, es). Otherwise translate every key of `assets/i18n/en.json` (keep the `{placeholders}` and the 7 weekdays / 12 months order).

Never put emails, phone numbers, addresses or anything sensitive in the config. It holds only what the newspaper needs.

## 4. Save it and print the first edition

The config lives in the reader's newsstand, next to the editions. Run the edition flow from step 2 of SKILL.md with `WORK/config.json`; `assemble.py` adds `config.json` to the files to publish when the newsstand is new. If a newsstand already exists from sample editions (no `config.json`), keep it: run `assemble.py` with `--index` and `--with-config`; numbering simply continues. To change the config of an existing newsstand, rerun `assemble.py` with `--with-config` (or publish just `config.json` in patch mode).

After the edition, reply in their language with a short summary:
- today's headline;
- what was configured (city and topics);
- only if `avoid` is not empty: the words being avoided, asking whether to remove or add any;
- which connections are still missing (if any) and the newsstand slug.

Then the schedule:
- **A time was chosen** (7:00, 6:00 or another time): create the daily schedule now (see "Scheduling" in SKILL.md) and say so in the summary.
- **"Don't schedule for now", the quick start, or the question was skipped:** create nothing. End with one line telling them they can ask at any time, e.g.: "Whenever you want it every morning, just send me 'schedule my newspaper'."
