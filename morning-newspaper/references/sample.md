# Sample edition (scheduled run, no setup yet)

Someone scheduled the newspaper before ever setting it up. Nobody is there to answer questions, so instead of stopping, publish a sample edition: a real edition with the default sections, opened by a short notice that explains how to set it up. The notice text comes from the `sample_*` labels; you write nothing about it.

## 1. Build a temporary config

Write `WORK/config.json` from `references/config.example.json`, changed as follows:
- `language`: the language the scheduled task prompt is written in.
- `timezone`: the `timeZone` that Google Calendar returns for the primary calendar, if connected; otherwise `UTC`.
- `city`: remove it (no weather, no local news). Remove the `local` section.
- `news_locale` and `wikipedia_lang`: match the language (and the country, if the task prompt makes it obvious).
- Sections: keep `tech`, `money` and `games`; translate their `title` and `queries` into the language. `newspaper`: leave `name` out so the default name for the language is used; write a short motto in the language.
- `labels`: if `assets/i18n/` has no file for the language, translate every key of `assets/i18n/en.json` here (including the `sample_*` keys).

## 2. Run the normal flow

Steps 2 to 5 of SKILL.md as usual (agenda and email only if connected), with two differences:
- The weather is left out (`"weather": false` in `edition.json`).
- Run `assemble.py` with `--sample`. It adds the notice at the top, labels the edition "Sample edition" and never publishes `config.json`, so the next scheduled run still knows setup has not happened.

## 3. Publish

Publish to the newsstand as in `references/archive.md` (it is created if missing). Do not create, change or delete scheduled tasks. Send no messages: the notice at the top of the edition is the message.
