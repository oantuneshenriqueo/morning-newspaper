# The newsstand

The newsstand is a private artifact of the reader, with several files:

```
index.html              the newsstand page (copied from assets/archive.html; never changes between editions)
config.json             the reader's profile (language, city, sections…); private
editions/index.json     list of all editions, newest first, plus the page labels
editions/YYYY-MM-DD.html one page per edition
```

`index.html` reads `editions/index.json` and builds the shelf by itself. Each edition only adds its own file and updates the index. Never delete or rewrite past editions. `scripts/assemble.py` builds every file: you only read the current state before and publish after.

Use the session's artifact tools: list artifacts, get an artifact's state (version), list and read an artifact's files, and publish from files on disk (patch mode, which only changes the files you send).

**Before publishing, in this session: list the newsstand's files and read the newsstand page itself** (the tool's action that returns the artifact's current page, e.g. reading the artifact). Some publishing tools refuse to change an artifact whose live page was not read in the same session; a file list alone does not count. The list is also how you learn whether `config.json`, `index.html` and `editions/index.json` exist.

**`index.html` is always the newsstand's main page.** When the publishing tool asks for the page, entry file or `file_path`, give it `index.html` from `WORK/archive/`, never today's edition: an edition there would replace the newsstand's cover. Editions and the index are supporting files. Publish from `WORK/archive/`, which sits in the working folder (SKILL.md, "Edition flow"): the tool refuses files from other folders.

## Finding the newsstand
Send the calls of this step together with step 0 and, as soon as the newsstand is known, do everything else in **one** round: list its files, read its page, read `config.json` and `editions/index.json` (their paths are fixed, so they need not wait for the list) and load the schemas of the calendar and email tools step 2 will call. All of these are needed before publishing anyway; split into two rounds, they cost the whole conversation twice.
1. If the request or the scheduled task prompt has the newsstand slug, use it.
2. Otherwise search the reader's artifacts by title, in this order: the newspaper name; the newsstand label in the reader's language and in English ("Banca", "Quiosco", "Newsstand"; older newsstands were created with the title "Newsstand" alone). Open the files of each match and take the one whose files include `editions/index.json`. Only if no title matches, list the artifacts and check the most recent ones with the "newspaper" icon.
3. More than one: use the most recent and, in an interactive session, say so in one line.
4. None: this is a first run → `references/setup.md` (or `references/sample.md` in a scheduled run).
5. Found, but without `config.json`:
   - **The request or the scheduled task prompt carries a config** (older newsstands predate `config.json`): that config wins. Save it as `WORK/config.json`, print a normal edition (never a sample) and run `assemble.py` with `--with-config`, so the newsstand gets its `config.json`.
   - **No config anywhere:** the newsstand only holds sample editions. In a scheduled run, add another sample edition to it; in an interactive session, run setup and keep using this newsstand (see the end of `references/setup.md`).

Then read `config.json` and `editions/index.json` from it into `WORK/config.json` and `WORK/index.json`. When the reading tool can save files to disk (an output folder), save them there instead of bringing their text into the conversation: the scripts read them from WORK, and the index alone can be several thousand tokens.

**Legacy newsstands.** A newsstand made by an early version keeps its index at `edicoes/indice.json`. If `editions/index.json` exists, it always wins: ignore the legacy file. If only the legacy file exists, save it as `WORK/index.json`: `assemble.py` recognizes it, rewrites every entry with the current keys, prints `LEGACY NEWSSTAND MIGRATED` and adds `config.json` to the files to publish. Publish them all and, if the publishing tool can delete files, remove `edicoes/indice.json` in the same call (past edition pages under `edicoes/` stay where they are).

## Creating the newsstand (first time only)
1. Run `assemble.py` without `--index`. It writes `index.html`, `config.json`, `editions/index.json` and today's edition into `WORK/archive/` and prints "NEW NEWSSTAND".
2. Publish them in one call, from disk, creating the artifact with the title "<newspaper name> · <archive_title label>" (e.g. "Morning Newspaper · Newsstand") and the icon "newspaper".
3. In an interactive session, tell the reader the newsstand was created and give the slug, to put in the scheduled task prompt.

## When there can be no newsstand
No artifact tools in this session, or publishing still fails after the retries below: make only the newspaper (`references/modes.md`), and tell the reader in one sentence why there is no newsstand. Never publish the newsstand or `config.json` anywhere public to make up for it: both are private.

## Adding today's edition
1. Before collecting: list the newsstand's files, read its page, note its current version (the tool may answer with another id or link for the same artifact: keep using the slug the task or the reader gave) and save `config.json` and `editions/index.json` into WORK. If the list also shows the legacy `edicoes/indice.json` next to `editions/index.json`, note it for step 3.
2. Run `assemble.py --index WORK/index.json`. A reissue (an entry with today's date already exists) keeps its number; the script handles it. If the published edition has more stories, it prints `KEEP:` and writes nothing (SKILL.md, step 7); `--replace` publishes over it only after the reader says yes.
3. After the final check (SKILL.md, step 6, rerunning `assemble.py` if a text changed), publish exactly the files the script listed (always `index.html`, today's edition and `editions/index.json`), in patch mode, with the version from step 1 when the tool takes one (if it has no version parameter, having read the page in step 1 is enough), `index.html` as the main page. The script rebuilds `index.html` with the title "<newspaper name> · <newsstand label>" (`NEWSSTAND TITLE`), which is what names the artifact; if the tool also takes a title, pass the same one. If step 1 found `edicoes/indice.json` and the tool can delete files (e.g. a `remove` list), remove it in the same call; past edition pages under `edicoes/` stay.
4. Publish refused because the live page was not read first: read the newsstand page, then publish once more with the version that read returns. Refused as an identical resend: check that the live version is the one you read and publish once more.
5. Version conflict: read the index again, save it to `WORK/index.json`, rerun `assemble.py` and publish. On the third failure, stop publishing: rerun `assemble.py` with `--standalone`, deliver that page and tell the reader why the newsstand was not updated.
6. `index.html` missing from the newsstand: nothing to do, the script always lists it.

## Single page

When the artifact tools publish only one HTML page per artifact (SKILL.md, step 0), there is no newsstand. Instead one private artifact, titled with the newspaper's name, always shows the latest edition. Its page carries the reader's state (config and a compact index: numbering, extras and the last 14 editions' titles and link fingerprints) in a `<script type="application/json" id="morning-newspaper-state">` line near the top, so nothing is lost between runs.

**Finding it (step 1):** the slug from the request or the task prompt; otherwise search the reader's artifacts by the newspaper's name and take the one whose page has that script. Read only the first lines of the page (the state is on one line near the top), copy the JSON inside the script exactly as it is into `WORK/state.json` with the file-writing tool, and run `python3 SKILL/scripts/assemble.py --unpack-state WORK/state.json --work WORK`. It writes `WORK/config.json` and `WORK/index.json`. Not found: first run (`references/setup.md`), or a sample edition in a scheduled run.

**Publishing (step 7):** `assemble.py --single-page` writes `WORK/single/index.html` and prints `ARTIFACT TITLE`. Publish that one file from disk, never pasted into the call: as a new version of the same artifact (with the version you read) or, the first time, as a new artifact with that title and the icon "newspaper". On a version conflict, read the page again, unpack the state again, rerun `assemble.py` and publish once more.

**A newsstand that cannot be published:** if publishing the newsstand's files is refused because the tool takes only one page, rerun `assemble.py` with `--single-page` (same `--index`) and publish that instead. Never publish an edition as the cover of an existing newsstand.

## The index entry
Written by `assemble.py`; never edit the index by hand. Each entry has `date`, `number`, `weekday`, `type` ("morning" or "weekend"), `headline`, `summary`, `file`, `extras` (`history`, `did_you_know`: one short line each, so they are not repeated), and for the last 14 editions `titles`, `source_titles` (the titles as collected, before rewriting), `links` and `fit` (per section, `[candidates, off-topic]`: the ground for keyword adjustments). Collection compares new stories only against those 14 editions, so a recurring subject (a monthly rate decision, a yearly event) is never blocked by an old headline. The index also carries `newspaper`, `founded` and the `labels` the newsstand page uses.

## Links between pages
- An edition's newsstand button points to `../index.html` (left out of copies made with `--standalone` or `--share`).
- The newsstand links each edition by its relative `file` path.
- The index is plain JSON; its texts are shown as text, never as HTML.
