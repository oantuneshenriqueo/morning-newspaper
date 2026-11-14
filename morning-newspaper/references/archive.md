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

**Always list the newsstand's files in this session before publishing to it.** The publishing tool refuses to change an artifact whose file list it has not been shown in the same session, and the list is also how you learn whether `config.json`, `index.html` and `editions/index.json` exist.

## Finding the newsstand
1. If the request or the scheduled task prompt has the newsstand slug, use it.
2. Otherwise search the reader's artifacts by title, in this order: the newspaper name; the newsstand label in the reader's language and in English ("Banca", "Quiosco", "Newsstand"; older newsstands were created with the title "Newsstand" alone). Open the files of each match and take the one whose files include `editions/index.json`. Only if no title matches, list the artifacts and check the most recent ones with the "newspaper" icon.
3. More than one: use the most recent and, in an interactive session, say so in one line.
4. None: this is a first run → `references/setup.md` (or `references/sample.md` in a scheduled run).
5. Found, but without `config.json`:
   - **The request or the scheduled task prompt carries a config** (older newsstands predate `config.json`): that config wins. Save it as `WORK/config.json`, print a normal edition (never a sample) and run `assemble.py` with `--with-config`, so the newsstand gets its `config.json`.
   - **No config anywhere:** the newsstand only holds sample editions. In a scheduled run, add another sample edition to it; in an interactive session, run setup and keep using this newsstand (see the end of `references/setup.md`).

Then read `config.json` and `editions/index.json` from it into `WORK/config.json` and `WORK/index.json`.

**Legacy newsstands.** A newsstand made by an early version keeps its index at `edicoes/indice.json`. If `editions/index.json` exists, it always wins: ignore the legacy file. If only the legacy file exists, save it as `WORK/index.json`: `assemble.py` recognizes it, rewrites every entry with the current keys, prints `LEGACY NEWSSTAND MIGRATED` and adds `index.html` and `config.json` to the files to publish. Publish them all and, if the publishing tool can delete files, remove `edicoes/indice.json` in the same call (past edition pages under `edicoes/` stay where they are).

## Creating the newsstand (first time only)
1. Run `assemble.py` without `--index`. It writes `index.html`, `config.json`, `editions/index.json` and today's edition into `WORK/archive/` and prints "NEW NEWSSTAND".
2. Publish them in one call, from disk, creating the artifact with the title "<newspaper name> · <archive_title label>" (e.g. "Morning Newspaper · Newsstand") and the icon "newspaper".
3. In an interactive session, tell the reader the newsstand was created and give the slug, to put in the scheduled task prompt.

## Without artifact tools (local newsstand)

Some hosts (another app, an IDE agent) have no artifact tools. Then the newsstand is a folder on disk, `~/newspaper/newsstand/`, with the same files. Never publish it on the web to make up for it: the newsstand and `config.json` are private.
- **Finding it:** if `~/newspaper/newsstand/editions/index.json` exists, that is the newsstand: copy its `config.json` and `editions/index.json` into WORK, as in step 1. If it does not exist, this is a first run.
- **Adding the edition:** run `assemble.py` as usual, then copy what it wrote into the folder: `mkdir -p ~/newspaper/newsstand && cp -r WORK/archive/. ~/newspaper/newsstand/` (plain `-r`; some hosts refuse `-a`). Past editions stay, because the script only writes the new files.
- Tell the reader the folder path, and that `index.html` there opens the newsstand in a browser. If the host's home folder does not survive between sessions, say so in one line: the next session will not find it and would start a new newsstand.

## Adding today's edition
1. Before collecting: list the newsstand's files, note its current version and save `config.json` and `editions/index.json` into WORK.
2. Run `assemble.py --index WORK/index.json`. A reissue (an entry with today's date already exists) keeps its number; the script handles it.
3. Publish only the files the script listed, in patch mode, with the version from step 1. If the newsstand's title is not the `NEWSSTAND TITLE` the script printed (an older one called just "Newsstand"), pass that title in the same call so the next search finds it by name.
4. Publish refused because the artifact was not read first: list the newsstand's files again, then publish once more with the version that listing returns.
5. Version conflict: read the index again, save it to `WORK/index.json`, rerun `assemble.py` and publish. On the third failure, stop and (if interactive) tell the reader.
6. If `index.html` is missing from the newsstand, rerun `assemble.py` with `--with-page`: it adds `index.html` to the files to publish.

## The index entry
Written by `assemble.py`; never edit the index by hand. Each entry has `date`, `number`, `weekday`, `type` ("morning" or "weekend"), `headline`, `summary`, `file`, `extras` (`history`, `did_you_know`: one short line each, so they are not repeated), and for the last 14 editions `titles`, `source_titles` (the titles as collected, before rewriting) and `links`. Collection compares new stories only against those 14 editions, so a recurring subject (a monthly rate decision, a yearly event) is never blocked by an old headline. The index also carries `newspaper`, `founded` and the `labels` the newsstand page uses.

## Links between pages
- An edition's newsstand button points to `../index.html` (left out of copies made with `--standalone` or `--share`).
- The newsstand links each edition by its relative `file` path.
- The index is plain JSON; its texts are shown as text, never as HTML.
