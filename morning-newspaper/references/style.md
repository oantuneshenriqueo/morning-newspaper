# Visual style: 1980s–90s printed newspaper

The ready-made template is `assets/edition.html` (the newsstand page is `assets/archive.html`). Use the classes already there; do not reinvent the layout. This file explains the rules for when a decision is needed, e.g. when the reader asks to change the look.

## Palette
| Name | Color | Use |
| --- | --- | --- |
| Paper | `#F2E8D5` | Page background |
| Light paper | `#FBF6EC` | Boxes (weather, agenda, classifieds, extras) |
| Ink | `#1E1B16` | Text, rules, borders |
| Red | `#A8261B` | Top band, headline kicker, drop cap, main section titles |
| Blue | `#1F4A7A` | Agenda, secondary sections, links |
| Mustard | `#C8901E` | "On this day" background and the weather sun (always with ink text) |

Only these colors. No gradients (the halftone is the only texture), no shadows, no rounded corners.

## Typography
- **Gloock**: newspaper name, headline and story titles.
- **Crimson Pro**: body text, deck (italic), agenda.
- **Arsenal SC**: kickers, section names, bands, date, masthead (small caps).
- Loaded from Google Fonts (link already in the template), with Georgia as fallback.

## Page order
1. Date line: year and issue number on the left, full date on the right.
2. Newspaper name and the motto in italics.
3. Double rule and the red band with the day's summary.
4. Weather box (simple SVG icon that follows the condition).
5. Headline: kicker (section), title, deck, halftone "photo" labelled as an illustration, text with drop cap, source.
6. Today's Column (agenda), box with a blue header.
7. Classifieds (emails), dashed box.
8. Sections in config order: `main` = red-ruled title with two columns on wide screens; `half` = paired side by side with the next half; `single` = full-width box.
9. Extras: On this day (mustard) and Did you know? (light paper), side by side.
10. Masthead and the "past editions" button.

## Headline "photo"
No real photos (rights and privacy). The halftone box captioned as an illustration is the "photo", with a simple, large line icon tied to the subject.

## Phone and wide screens
- Up to 700 px: one column, except the pairs (half sections and extras), side by side from 360 px.
- From 700 px: max width 760 px, centered; the `main` section gets two columns.
- Touch targets at least 44 px tall (the newsstand button).

## Accessibility
- `lang` comes from the reader's language; `<title>` has the newspaper name and date.
- Contrast: ink on paper; red and blue only on large text or light backgrounds (all pass 4.5:1 on paper).
- Decorative SVG with `aria-hidden="true"`; the halftone with `role="img"` and an `aria-label`.
