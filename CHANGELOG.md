# Changelog

All notable changes to Morning Newspaper. Each release on GitHub uses the matching section below as its notes.

## Unreleased

### Fixed
From the debug report of scheduled edition No. 011.
- **A fact already printed came back told with other names.** "Gigante chinesa apresenta novo modelo de IA… reforço na segurança" passed without `printed?` five days after "Alibaba lança novo modelo de inteligência artificial… reforço da cibersegurança". The repeat hints now fold "IA"/"AI" (in capitals only, since "ia" is also a verb) with "inteligência artificial"/"artificial intelligence", and drop the "ciber"/"cyber" prefix ("cibersegurança" ≈ "segurança", "cyberattack" ≈ "attack"). Only hints change (`printed?`, `≈`, `earlier?`); what the script drops on its own does not.
- **The story's own date counted as a number not in the source.** "na sexta-feira, 20 de novembro" taken from the collected date got `CHECK: numbers not in the source: 20`. The day, month (number and name) and year of a candidate's date now count as source text; its hour does not.
- **"Sites relatam" for a story only one outlet carried.** A plural attribution ("outlets report…", "sites relatam…") on a story no other collected candidate carries (no `≈`) now gets a `CHECK:` asking to name the outlet ("Segundo o Pplware, …"). SKILL.md says the same.

### Changed
- **The final check comes before publishing.** Steps 6 and 7 swapped: check every sentence (and rerun `assemble.py` if a text changed), then publish once. Before, the edition was published and then checked, which meant publishing twice whenever the check changed a word. `assemble.py`'s `NEXT` lines follow the new order.

## v1.13.0 — 2026-11-21

From the debug report of scheduled edition No. 010: the story texts had become the headline reworded, because most candidates come from Google News searches, which send no summary.

### New
- **Stories with substance.** `collect.py` reads the opening of the story's own page for the first title-only candidates of each section (`scripts/enrich.py`): the page's description or first paragraphs, cut near 380 characters. Google News links are turned into the outlet's address through the outlet's own search feed or Google News' own lookup, and the printed link then points to the outlet. A page dated before the window flags the candidate `old page? MM-DD`. Capped at 18 pages and 45 seconds per edition.
- **"In brief" column.** A story with only its title is printed as one line with its source (`"brief": true`), never as a paragraph that restates the title; `assemble.py` does it by itself (`BRIEFS:`). A text that only restates its title gets an `ECHO:` line.
- **Summaries win.** Between stories of similar relevance, the one with a summary is chosen, in every slot. When two candidates tell the same fact, the one with a summary is kept. Photo captions at the start of a feed's description (g1 and other portals) are removed, and a description that is only a caption no longer counts as a summary.
- **Nearby places.** `scripts/cities.py` builds, once per city, the list of towns, villages and districts within `region.radius_km` (60 by default) with their distance: IBGE in Brazil, GeoNames elsewhere, and a list written by the model only when no source answers (replaced by real data after 30 days). No population cut. Local candidates are flagged `near Salto 9km`, `city (district)`, `other state? RN` or `where?`, and sorted by distance.
- **Direct feeds.** `scripts/feeds.py` finds the own RSS feeds of the outlets that bring each section's stories and checks that they carry summaries; setup offers to add them.

### Changed
- The fallback headline is written in up to 3 sentences, as many as its title and summary back.

## v1.12.0 — 2026-11-19

### New
- **Install as a plugin, with updates on their own.** This repository is now a plugin marketplace. In the Claude desktop app: **Customize → Plugins → Add marketplace**, enter `oantuneshenriqueo/morning-newspaper`, keep **Sync automatically** on and install **morning-newspaper**. In Claude Code: `/plugin marketplace add oantuneshenriqueo/morning-newspaper`, then `/plugin install morning-newspaper@morning-newspaper`. The plugin always holds the latest release, never unreleased work. If you used the zip before, delete that skill after installing the plugin so Claude does not see two copies; your newsstand is not touched. In the desktop app a plugin skill may not show in the `/` menu: type `/morning-newspaper:morning-newspaper` or just ask for your morning newspaper.

### Fixed
From the debug report of scheduled edition No. 009.
- **Classifieds said "Gmail not connected" over an empty inbox.** An inbox that was read and has nothing waiting for a reply is now `[]`, and `assemble.py` warns when the agenda or classifieds key is missing, since that prints "not connected".
- **A name added from memory at the start of a sentence went unchecked** ("Pavel Durov negou…"). The first word now counts as a possible name when a capitalized word follows it, unless it is an ordinary opening word ("Após", "Segundo", "Também", "After", "Tras", adverbs in -mente / -ly).

## v1.11.0 — 2026-11-18

From the debug reports of scheduled editions No. 007 and No. 008.

### New
- **Section keywords that tune themselves.** Each section (except local news) has `keywords`: stories that carry one fill the candidate list first, the others are flagged `fit?`, so a weak list only reorders and never hides a story. Setup now writes them for every section, without asking. In each edition the model lists the candidates it left out as off-topic (`off_topic`); when a section keeps bringing them, `collect.py` prints `KEYWORDS REVIEW` and the model may propose a few words. `assemble.py` applies the proposal only with ground (many off-topic candidates in 3 of the last 5 editions), one change per section a week, adding or swapping words, never shrinking the list to a filter, with every word validated. The paper prints a one-line editor's note, and a change that makes the next 3 editions worse is undone by itself. It is the one config change made without the reader; everything else still needs their yes.
- **Weekday check.** `assemble.py` refuses a weekday next to a day number that the calendar does not back ("segunda-feira, 17" when the 17th was a Tuesday), in any language with labels.
- **Attributions are kept.** "Outlets report…" is never a `CHECK:`; a run that drops an attribution an earlier run had gets a warning. A headline credited to the page that was opened gets a `CHECK:` until a fact only the collected title carries is attributed to its outlet.
- **`earlier? MM-DD` flag** for a fact the same searches returned before the window (probably a republication), and a `SUMMARIES` line saying how many candidates have a summary.
- **"Did you know?"** tries the reader's Wikipedia first, then seed articles per theme, then the English search; list articles are skipped, `Retry-After` is honored and the HTTP code is reported in `FAILURES`.

### Fixed
- Same-fact grouping (`≈`): a shared coined name (Java4Shell, Log4j) or CVE id now groups two titles; bare numbers ("4.5") no longer do.
- The headline is chosen before any search and only that story is researched; if its fact is older than the window, the next story takes its place without a new search. If the best result's page does not open, the next one is tried once.
- Rate moves named without "rate of" ("juros", "rate cut") are flagged `recurring?`.
- No `CHECK:` for the story's own outlet, country short and full names, or another tense of a title word; `weather_condition` is ignored when the condition is already in the reader's language.
- An `ERROR:` that survives two fixes drops the story it names, so the edition still comes out. A scheduled run never ends before the summary: a call that did not run is sent again.

### Changed
- Fewer rounds: the newsstand's files, page, config, index and the calendar and email tool schemas are read in one round.
- `edition.json` is fixed with the file-editing tool, never with a script.
- The User-Agent names the project page.

## v1.10.0 — 2026-11-17

### New
- **28 more headline illustrations.** The halftone "photo" of the headline now has 36 line icons instead of 8, so stories about health, sport, elections, courts, the environment, travel, culture and more get a matching drawing instead of the generic newspaper: `capitol`, `ballot`, `gavel`, `shield`, `megaphone`, `people`, `globe`, `briefcase`, `cart`, `fuel`, `bolt`, `wheat`, `house`, `phone`, `wifi`, `flask`, `rocket`, `heart`, `leaf`, `thermometer`, `book`, `car`, `bus`, `plane`, `film`, `music`, `ball` and `trophy`. Same style as the original eight.
- `references/edition-format.md` groups the icons by topic; `SKILL.md` lists them all. An unknown name still prints `newspaper`.

### Tests
- A new test keeps the icon lists in `SKILL.md` and `edition-format.md` in sync with the drawings and checks that each one is valid SVG.

## v1.9.0 — 2026-11-16

From the debug report of scheduled edition No. 006.

### New
- **`CHECK:` lines.** After `OK:`, `assemble.py` names the words of each printed item that its collected text does not carry: names, numbers, a hedge the source had and the text dropped ("potentially exposed" printed as "exposed") and, when only the title backs a story, the longer words that are not in it. Step 7 starts with them.
- **`printed?` flag.** The collection marks a story that looks like a fact a recent edition already printed, told by another outlet in other words (the reader's city is left out of the comparison). Nothing is dropped: the model leaves it out unless it brings something new.
- **`avoid_outlets`** (optional, in `config.json`): outlet names whose stories never come in, such as another country's sites that share the language.
- **Section count warning.** A section above its own `count` gets a warning; the headline never counts there.

### Fixed
- Scheduled runs no longer send the "takes a few minutes" line: nothing goes out before the summary.
- The newsstand's summary line says the inbox is up to date when Gmail was read and nothing is waiting.
- The index keeps short link fingerprints instead of Google News links, so it is about half the size; older entries are converted on the next edition.

### Changed
- Never cut the scripts' output (`| head` hid possible warnings).
- Keep the source's hedges: a possibility is never printed as a fact.
- The thorough headline search is also used when the results are about something else, with the full name instead of an acronym.
- The agenda names the primary calendar explicitly; Gmail conversations with several messages are opened when the shown message does not settle them; only the tool schemas about to be called are loaded.
- A story may be printed in the section whose interest it fits (a sandbox game found by a tech search goes to games).
- `references/archive.md`: the version is passed only when the publishing tool takes one; keep the slug the task gave.

## v1.8.0 — 2026-11-15

From the debug report of a first edition made in another app, which came out with a single story while the reply promised every section.

### New
- **`COVERAGE:` line.** After `OK:`, `assemble.py` prints how many stories the edition has, which sections carry them and which came out empty, in every mode. The edition summary is written from these lines, never from the plan, and empty sections go in the **Missing** line.
- **`run.log`.** `collect.py` and `assemble.py` append their command, time and full output to `WORK/run.log` by themselves. The model never reads it and the reader never gets it; it is there for a debug report.

### Fixed
- `assemble.py` refuses an edition without `WORK/collected.json`: the collection is never skipped.
- `assemble.py` refuses stories when the collection printed `NETWORK BLOCKED` and the no-network searches (`collect.py --from-results`) were skipped. A day with no story still comes out as before.
- The "only the newspaper" modes (`--standalone`, `--share`) now print the mandatory steps 7 and 8, like the others.
- The first-run summary lists the topics as settings, never as what today's edition contains.

## v1.7.0 — 2026-11-15

From the debug report of edition No. 005 (an afternoon reissue in a session whose network blocked every source).

### New
- **A weaker reissue never replaces the published edition.** When today's edition is already at the newsstand with more stories, `assemble.py` prints `KEEP:` and writes nothing. A scheduled run keeps the published edition; an interactive run asks the reader, and `--replace` publishes over it only after a yes.
- **A day with no story still gets its edition.** If no story passes the rules, the paper comes out with the agenda, classifieds, weather and extras, and a short "no confirmed news today" note in place of the headline. The summary adds a **Missing** line.
- **`DROPPED` in the collection.** Each section lists what the script left out and why (outside the window, already printed, `avoid` list, same story), so a missing story never has to be guessed.
- **Rules that are never optional.** SKILL.md now opens with the six rules editions broke: every fact has a source, no guessed dates or hand-filtered results, no extra searches, step 7 always, the step 8 summary only, and `KEEP` means stop. `assemble.py` also prints the mandatory next steps after `OK:`.

### Fixed
- Two different games with release dates in the same month counted as one story: titles are now compared without dates, months and years.
- A summary that added facts to its title was erased; only one that merely repeats the title is now.
- With the network blocked, every section printed `(nothing new)`; it now says the sources were not reached.
- A lone extra box ("On this day" or "Did you know?") now takes the full width.

### Changed
- **Headline facts come from an opened page.** Beyond the collected title and summary, only what the opened page says is printed; the search tool's own written summary is not a source.
- **No network:** every result goes to `results.json` with its own snippet (never the search tool's answer), dates only when shown as the publication date, and no second round of section searches.
- **"Did you know?"** tries up to three confirming pages and widens today's theme to any technology or science fact before leaving the box out.
- **Attention line:** accounts only, never dates, places or devices.

## v1.6.0 — 2026-11-15

Faster editions that spend fewer tokens. In an agent session every call re-reads the whole conversation, so the work here is fewer rounds and less text pulled in.

### New
- **"Did you know?" candidates from the collection.** `collect.py` looks up Wikipedia articles on today's theme and prints them as `k1`, `k2`… with their summary. Like "On this day", the Wikipedia text counts as confirmation, so the usual one or two searches plus an opened page are gone. `"did_you_know": {"ref": "k1", "text": "…"}` fills in the link. The manual way (`references/extras.md`) stays for when no candidate fits.
- **Quick network check.** Before the full collection, one request to each kind of source runs in parallel. If none answers, the collection stops at once with `NETWORK BLOCKED` instead of waiting for every source to fail.

### Changed
- **Step 4 carries its essentials.** The JSON skeleton and the writing rules a normal edition needs are now in SKILL.md, so `references/writing.md` and `references/edition-format.md` are read only for uncommon fields or an error. A normal edition now reads about a third less instruction text, in fewer calls.
- **Fewer rounds.** Steps 0 and 1 go out together, the newsstand's file list and page are read in one round, and the no-network searches (sections, weather and history) go out in one parallel block.
- **No-network "On this day"** comes from one search instead of opening the Wikipedia date page (very long), and a `date?` story is confirmed with one search of its title, only if it would be printed.

## v1.5.1 — 2026-11-15

### Changed
- **Shorter SKILL.md.** It now holds only what every edition needs: a nine-step overview of a normal day, a "when to read what" table and steps 0 to 8. The rarer cases move to their own files, read only when they happen: `references/modes.md` (missing tools, only the newspaper, no folder to write in), `references/scheduling.md` and `references/no-network.md` (with the results file format, moved out of `edition-format.md`). Nothing in the rules changed; SKILL.md went from about 22 KB to 17 KB.

## v1.5.0 — 2026-11-15

From the first run in the Claude mobile app (a separate account, no newsstand, shell network blocked).

### New
- **Step 0: choose the mode first.** Before anything else the skill checks the session's tools and decides where the edition goes (newsstand, single page or only the newspaper), where the agenda and weather come from, and whether scheduling exists. No more finding out at step 6 that the newsstand cannot be published.
- **Single page with its state.** In apps whose artifact tools publish one HTML page per artifact, `assemble.py --single-page` writes today's edition with the reader's config and a compact index (numbering, extras, recent titles and link fingerprints) in a JSON block near the top. The next run reads the first lines of the page and restores everything with `assemble.py --unpack-state`, so the setup, the issue number and the repeat checks survive between runs.
- **`collect.py --from-results`.** When the sources are blocked, Claude writes its web search results to `results.json` and the script applies the same date window, repeat checks, `avoid` list, same-fact groups, flags and IDs as a normal collection. Results with no date are kept, flagged `date?`, to be confirmed. The weather can come from the app's weather tool, and "On this day" from the Wikipedia page for the date.

### Fixed
- **Weather without a link.** A forecast from the app's own weather tool has no page, and `assemble.py` refused it, so a page the numbers did not come from had to be linked. `url` is now optional, `source` names where the numbers came from, and a bad link is one error naming `weather.url`.
- **One error per problem.** The page-wide link check no longer repeats a problem a field check already reported (the confusing `invalid link in page:` with an empty link).
- **"Schedule my newspaper" only where it can be done.** The 📅 line and the setup's delivery-time question need a scheduled-task tool in the session.
- **Local news for small towns.** Every local query carries the state or region (never the name alone: a town named after another place brought that place's news), the city's coordinates are confirmed by a search, and an empty local section gets one search for the region before being left out.
- **Docs:** the phone's calendar tool as an agenda source, the hosts the shell needs, and the working folder when the publishing tool reads from one fixed folder.

## v1.4.3 — 2026-11-15

### Fixed
- **Languages without a label file** (anything but English, Portuguese and Spanish): labels the setup forgot to translate used to fall back to English silently. `assemble.py` now prints a `WARNING` listing the keys still in English, and the skill translates them into `config.labels` and saves the config.
- **Old-news check in every language**: month names were fixed in Portuguese, Spanish and English, so in other languages a story about "septembre" or "ottobre del 2025" was not flagged. The label files gain `months` (full month names), and `collect.py` also reads `config.labels.months`, matched exactly as written ("mars" is March, "Mars" is the planet). A year now counts when it comes within the next two words ("ottobre del 2025").

## v1.4.2 — 2026-11-15

### Fixed
- **Short edition summary**: scheduled runs were told to "send no messages", but a session always ends with a reply the reader sees, so it came out as a long report in English (sources, caveats, newsstand details). Every edition now ends with the same summary, in the paper's language and at most four lines: the edition number and headline; **Attention** only for what needs the reader (security alert emails, with the accounts); **Missing** only when a connector is off or failed, or the weather or a section came out empty; and, in runs asked by hand with no schedule, the "schedule my newspaper" reminder. No agenda, sources list or caveats.
- **Security alerts** go in the summary's Attention line in every run, no longer in the paper. `security_alert` in the edition file is still accepted, so older files build.
- **Sample edition** ends with one sentence on how to set the newspaper up.

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
