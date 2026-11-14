# Changelog

All notable changes to Morning Newspaper. Each release on GitHub uses the matching section below as its notes.

## v1.4.1 — 2026-11-14

### Fixed
- **Same-fact groups no longer chain**: when story B looked like A and C looked like B, all three were marked as one fact, even when A and C were different stories, so a good story could be dropped. A story now joins a group only if it looks like every story already in it, and is marked with the group's first ID.

## v1.4.0 — 2026-11-14

### New
- **Security alerts in scheduled runs**: a scheduled run sends no messages, so a security alert email (a new sign-in, a password change) used to reach nobody. The classifieds box now prints one neutral line about it, never which account or what happened.
- **Scheduled decisions are double-checked**: stories about rate decisions and economic figures (Copom, Selic, Fed, inflation, GDP…) are flagged `recurring?`, because outlets republish them for days. Their date is confirmed with one search before they are used. Readers can add terms with `recurring_terms`.
- **Sample editions are marked at the newsstand** with a red "sample" tag.
- **Snow icon** for snow, sleet, hail and frost.

### Changed
- **The classifieds box is there every day**, weekends included: an empty inbox prints "inbox up to date" instead of hiding the box.
- **"Did you know?" needs its link**: without the page that confirmed the fact, the edition is refused (leave the box out instead). "On this day" only takes its own candidates (`h1`, `h2`…).

### Fixed
- **Publishing to the newsstand**: the edition is built inside the session's working folder, the newsstand page is read before publishing, and `index.html` always goes along as the main page, so today's edition can never replace the newsstand's cover.
- **Newsstand name**: the page title is rebuilt as "<newspaper> · <newsstand>" on every edition, so newsstands still called "Newsstand" are renamed.
- **Old-news detector**: upcoming months ("January 2027") are no longer flagged as old; a year next to the month decides.
- **Feeds**: Atom, RSS 1.0, `dc:date` dates and `http` links are read. A page that is not a feed, or a feed with no dates, now shows up in `FAILURES` instead of coming back empty.
- **Weather**: asked by latitude and longitude, so towns that share a name get the right forecast.
- **Regional languages**: `pt-PT`, `pt`, `es-MX` and similar use the closest shipped labels instead of English.
- **No more tracebacks**: a headline or story written as plain text, a missing date, index entries without a date and incomplete custom labels now give a clear `ERROR:` or `WARNING:` line.
- **Long words** (URLs) wrap on phones; the drop cap keeps an opening quote with its letter.
- **More checks**: 15+ word quotes are also caught in titles and extras; two printed stories marked as the same fact give a warning; more stories than the usual range for the day give a warning; an edition dated before the newsstand was founded is refused.
- **Legacy newsstands**: the old `matutina` type becomes `morning`, the leftover `edicoes/indice.json` is removed when the publishing tool can delete files, and the index summary starts with a capital letter.

## v1.3.2 — 2026-11-14

### Fixed
- **Everyday words are not countries**: when looking for stories that tell the same fact, the Portuguese pronoun "eu" and the interjection "uê" were read as the European Union, and "US$" (the dollar) and all-caps titles ("TELL US…", "GOOGLE USA IA…") as the United States. Short forms that are also everyday words (US, USA, EU, UE) now count only in capitals, never in an all-caps title, and "US$" is left alone.
- **Spanish "EU"**: for Spanish readers, "EU" means Estados Unidos, as Mexican outlets write it.

## v1.3.1 — 2026-11-14

### Fixed
- **"usa" is not the USA**: the Portuguese and Spanish verb "usa" ("Google usa IA") was read as the country when looking for stories that tell the same fact. Now only "USA" in capitals counts (as do "U.S.A.", "US", "EUA" and "Estados Unidos").

## v1.3.0 — 2026-11-14

### New
- **Just the newspaper**: ask for the paper without the newsstand (a test, or a copy to show colleagues) and you get a single page with no newsstand button. A copy to share asks first whether your agenda and emails go in, leaves them out by default and says so at the top. Apps that cannot keep a newsstand (no artifacts) also get just the newspaper, with a line explaining why.
- **Connection status inside the boxes**: without Google Calendar or Gmail, the agenda and classifieds boxes stay and say the app is not connected. If a connected app fails twice, the box says it could not be read and why.
- **Afternoon editions** say "Evening edition" in the top band, and the footer credit can name another assistant (`newspaper.editor`).

### Improved
- **Same fact, different words**: stories that may tell the same fact (also across sections, and "EUA" = "Estados Unidos") are marked so only one is printed.
- **Old news in disguise**: titles that name another month ("inflation closes June" in November) are flagged.
- **Small towns**: stories that name your city come first in the local section; empty titles and titles that are just the outlet's name are dropped.
- **Headline source**: the printed source is the page whose facts were used, and the headline search includes the month and year.
- **Accuracy**: a sentence-by-sentence check against the sources before publishing (no invented nationalities, comparisons or advice), and "Did you know?" must be confirmed on an opened page.
- **Weekends and Mondays** look at 3 days of email, like the news.
- **The newsstand is found by name**: its page is titled "<newspaper> · <newsstand>", and older ones called just "Newsstand" are renamed.

### Fixed
- An evening reissue no longer repeats the morning's "On this day" and "Did you know?".
- A test copy no longer writes an index that could replace the morning edition.
- Text containing `{{ }}` no longer breaks the edition; classifieds accept years like 2026; single curly quotes count for the 15-word quote limit; a bad story reference prints a clear error instead of a crash; index extras are cut at a word boundary.
- A folder that cannot be written now gives a clear message instead of a crash.

## v1.2.0 — 2026-11-13

### New
- **Clickable setup**: when your Claude app shows multiple-choice questions, the setup is a couple of clicks. "Personalize" is now the recommended path and takes about a minute: topics, delivery time and subjects you would rather not see, then your city.
- **No schedule required**: pick "Don't schedule for now" and ask for the paper whenever you like. Until it is scheduled, each edition reminds you that you can say "schedule my newspaper" at any time. The schedule is never created unless you ask for it.
- **Subjects to avoid**: an optional `avoid` list in your config hides news and "On this day" facts on subjects you would rather not see. It matches whole words only, and the setup shows you the exact words so you can change them.

### Fixed
- **Older newsstands are migrated** automatically: the old index (`edicoes/indice.json`) is rewritten with the current format, and the newsstand page and your config are published again. A config in the scheduled task prompt is now used instead of producing a sample edition.
- **Publishing no longer fails** because the newsstand was not read first: its files are always listed before publishing, with one retry.
- **Every search gets a fair share**: a busy search can no longer fill all of a section's candidates and hide the others.
- **Recurring news is no longer blocked forever**: stories are compared only with the last 14 editions, using the titles as they were collected.
- **"On this day" no longer drops harmless facts**: the built-in word filter (where "war" also hid "software") was removed; only your own `avoid` list filters anything.

### Changed
- The setup no longer asks for the newspaper's name. It uses the default for your language; just ask Claude if you want another one.

### Project
- Automated tests run on every change, and a release is only published when they pass.

## v1.1.0 — 2026-11-13

### New
- **Sample edition**: if the daily schedule runs before the newspaper is set up, you get a sample edition with a short notice at the top, written like a regular newspaper section, explaining how to finish setting it up.
- **Quick start**: the first edition only needs your city. Everything else (news topics, sections, extras) can be tuned later.
- **Privacy line** in the first contact, making clear your answers stay in your private newsstand and nothing is sent or shared.

### Improved
- First contact now checks which apps are connected (calendar, email) before asking anything, so it only asks about what can actually be used.
- The daily schedule is offered only after setup is finished.
- The agenda and email boxes are left out of the edition when those apps aren't connected, instead of showing up empty.

### Project
- Releases are now published automatically by GitHub Actions, with the zip rebuilt from the source and these notes attached.

## v1.0.0

- First public release: retro 1980s–90s morning newspaper with agenda, emails awaiting a reply, weather, news on your interests, "On this day" and "Did you know?", a newsstand that keeps past editions, a daily schedule, and English, Portuguese (Brazil) and Spanish labels.
