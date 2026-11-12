# Running without approving every step

For the reader, not for each edition. Read only when they ask about approvals or a scheduled run gets stuck waiting for one. Explain in the reader's language.

## What an edition uses
| Action | Tool | Risk |
| --- | --- | --- |
| Read the agenda | Google Calendar: list events | read-only |
| Read emails | Gmail: search threads, open thread | read-only |
| Collect and assemble | the session shell (2 commands: `collect.py`, `assemble.py`) | reads public feeds, writes only to the working folder |
| Fallback searches | web search / fetch page | read-only |
| Publish | artifacts: read and publish files to the newsstand | writes only to the private newsstand |

Nothing sends, deletes or changes anything outside the newsstand.

## Scheduled task
- A dawn run has nobody to approve anything. If the task asks for approvals, it stops at the first one and no edition comes out.
- In the scheduled task's settings, turn on automatic approval ("Automatically approve"), if the organization allows it. This is the change that matters most.

## Connectors (also helps for manual runs)
- In the claude.ai connector settings each tool has its own permission. Set to always allow only the read tools the edition uses: Google Calendar list/search events; Gmail search threads and read thread/message.
- Keep approval on for anything that writes: sending, replying, forwarding or deleting email; creating, editing or deleting events; labels.

## Why the scripts help here too
Collection is one command and assembly another, instead of 10–20 separate searches and page fetches per edition: fewer calls, fewer approval prompts, fewer tokens.
