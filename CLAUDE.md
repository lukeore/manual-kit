# Manual kit: house style for project manuals

These notes are for writing or editing a manual built with this kit. Every manual should look like it came from
the same author. Follow these rules, and copy patterns from `.example/src/` or from an existing manual instead of
inventing new ones.

## How a manual is laid out on disk

```
doc/manual/                 the manual (in the project repo)
  manual.json               title, output name, issue, date, header/footer, PDF metadata
  src/NN-name.html          the pages, built in file-name order; files starting with "_" are skipped
  img/                      images the pages use (committed; made by the project's own tools)
  CLAUDE.md                 project notes; imports this file with @kit/CLAUDE.md
  kit/                      this repo, as a git submodule. Don't edit it from a project repo
```

Build it with `python doc/manual/kit/build_manual.py` and check the result with `python doc/manual/kit/preview.py
--pages 5-9`, which writes PNGs to `doc/manual/.cache/preview/`. **Look at the PNGs of every page you changed** before
you call the work done.

The build must report `overflow: none` and exit 0. Pages are fixed and nothing flows onto a next page. If a page
overflows, cut words, tighten the layout, or split it into two pages. Never shrink the font sizes to make it fit.

## Format

- A4 landscape (297 × 210 mm), fixed pages, chosen so a whole page can be read on a monitor at *Fit page*, while
  each page still prints on its own.
- Each page is a `<section class="page">` with a `<div class="body">` inside it. The build adds the header, the
  footer with issue, date and page number, and the thumb index down the right edge.
- The body is a **12-column grid, 259 × 178 mm**. On a chapter opener, the body beside the dark side panel is
  169 × 178 mm. Use `height:178mm` for a block that should fill the page height.
- British English (`lang="en-GB"`).

## Page types

| Page | Markup | Notes |
|---|---|---|
| Cover | `<section class="page cover">` | Dark. `.art` image on the right, `.kicker` with `{{ISSUE}}`, `h1` with the brand (accent colour on the `<span>`), `.sub`, `.ids` part numbers, `.meta` grid at the bottom. No header, footer or tabs. |
| Contents | `<nav class="toc"></nav>` | Filled by the build from every `h2` after the first chapter. Two callouts on the left: reading on screen, printing. |
| Using this manual | ordinary page | Audience cards, conventions (net colours, tags, signal naming), the three box types. |
| Chapter opener | `class="page opener" data-ch="N" data-ch-title="…" id="chN"` | Dark `.side` panel: `.no` (two digits, "01"), `h1`, 2–3 short paragraphs, `<nav class="toc-mini"></nav>`. A big image or cards fill the body. |
| Content page | `<section class="page">` | One `h2` per page (it becomes the contents entry), then grid blocks. |
| Reference page | add `data-ref` | Gets a REFERENCE tag. Bench data meant to be printed: tables, pinouts, checklists. White background, no dark panels. |
| Schematic sheet | `class="page sheet"` | `.lbl` with an `h2`, `.sch` with an SVG that fills the page. |
| Appendix | `data-ch="A"` etc. | Letters instead of numbers. |
| Back page | `data-ch="~" data-ch-title="Revision history" data-ref id="revisions"` | Always last. Revision table (one row per issue plus blank rows for print markup), document control, how to release. |

## Headings

- `h1`: page or chapter title. Only on the cover, contents, openers and title pages.
- `h2`: one per content page. It is the contents entry. `<span class="k">` colours a second phrase in the accent colour.
  Add `data-notoc` to keep a heading out of the contents. Give an `id` when other pages link to it.
- `h3`: small uppercase green label over a block ("CALLOUTS", "BRING-UP CHECKLIST").
- `h4`: card or box title.
- `.lede`: a larger opening paragraph under the `h2` that says what the page shows.

## Components

- **Boxes**, with fixed meanings. Use the one that matches; don't use them for decoration.
  - `.warn` (yellow triangle): could damage hardware, break a guarantee or break an interface rule.
  - `.note` (blue i): background, tips, how-to. Nothing breaks if it's skipped. `.tip` is the same box.
  - `.ref` (green book): points to where the full detail lives (page, spec, file, tool).
  - Optional `<h4>` title inside. Add `.small` for a compact box.
- **Key figures**: `.stats` grid of `.stat` (`<b>value<small>unit</small></b><span>meaning</span>`). `.stat.dark`
  for the headline figure, `.stat.acc` for an accent value.
- **Cards**: `.cards` grid of `.card` (`.card.h` puts the image beside the text). Chip with the part number first.
- **Chips**: `.chip.g` (green) for the main item, `.chip` (ink) for others, `.chip.o` (outline) for passive or
  secondary items.
- **Requirement tags**: `<span class="req">PWR-03</span>`. Keep them, so each statement traces back to the clause in
  its source specification.
- **Tables**: plain `table`. Add `.tight` for dense data, `.zebra` for long tables, `td.num` for right-aligned
  numbers, `td.mono` for part numbers, paths and register names, and `tr.sum` for a totals row.
- **Code**: `pre` is dark. In it, `.c` comment, `.k` keyword, `.s` string, `.n` number, `.o` operator. `pre.light`
  is for printed reference pages. Use `code` inline and `kbd` for keys.
- **Lists**: `ul.checklist` for bring-up and test steps (it prints boxes to tick). `dl.kv` for key-value facts.
- **Figures**: `figure.stage` for a photo or render on the grey stage. `figcaption` starts with
  `<span class="fig-num">Figure 3.2</span>`, numbered by chapter.
- **Annotated screenshot**: `.shot` with `<span class="co" style="left:x%;top:y%">1</span>` markers, and a matching
  `ol.co-key` beside it.
- **Legend**: `.legend` holds net chips with their meanings.

## Net colours

These are the same in every diagram, pinout, table and chip, in every manual. Never colour a net by any other rule.

| Kind of net | Chip | Diagram stroke / fill / text | Colour |
|---|---|---|---|
| 5 V supply (VBUS, 5V rails) | `.net.v5` | `v5` / `fv5` / `tv5` | red #e5484d |
| 3.3 V supply | `.net.v3` | `v3` / `fv3` / `tv3` | orange #f2780c |
| Ground | `.net.gnd` | `gnd` / `fgnd` | grey #5f6b74 |
| Data (LED data, UART, PWM) | `.net.data` | `data` / `fdata` / `tdata` | blue #2f6fe4 |
| I²C | `.net.i2c` | `i2c` / `fi2c` / `ti2c` | violet #8b4ec4 |
| Auxiliary / general-purpose I/O | `.net.aux` | `aux` / `faux` / `taux` | amber #c99200 |
| Identification | `.net.id` | `id` / `fid` / `tid` | teal #0c9c96 |
| Control (enable, fault, buttons) | `.net.ctl` | `ctl` / `fctl` / `tctl` | pink #d6409f |
| Not connected | `.net.nc` | | light grey |

Name signals that are active low with `_n` (`FAULT_n`).

## Diagrams

Draw block diagrams and wiring by hand in inline SVG with `<svg class="dg" viewBox="…">`. Don't use images of
diagrams. Classes:

- Blocks: `blk` (grey), `blk-d` (dark, for external things like a PC; white text with `t-w`), `blk-a` (accent),
  `ic` and `ic-f` (outlined chips), `zone` (dashed boundary of a board).
- Wires: `w` plus a net class (`w v5`, `w data`). Add `dash` for optional or control lines and `thin` for minor ones.
  Draw the main power path at `stroke-width:2.4`–`2.6`.
- Text: `t-h` heading, `t-s` small grey, `t-m` mono (pin names), `t-mb` mono bold, `mid` or `end` to anchor.
- `_head.html` defines schematic symbols to reuse with `<use href="#res-h" x=".." y=".."/>`: `res-h`, `res-v`,
  `cap-h`, `cap-v`, `gnd`, `sup`, `led-v`, `tvs`, `sw-h`, `jn`, `arrow-r`. They take their colour from `currentColor`.

## Colours and type

- Palette: ink #111a1e, deep #0e1418 (dark panels, cover), stage #f3f5f4 (behind images), accent green #17b26a
  (dark green #0a7a45 for text). Use the CSS variables (`var(--accent)`) and never new colours.
- Fonts (in `fonts/`): **Space Grotesk** for headings, numbers and labels, **Inter** for body text, **JetBrains
  Mono** for code, part numbers and pin names. Body text is 8.9 pt. Don't change sizes per page.

## Links and cross-references

- `{{page:some-id}}` becomes the number of the page that holds `id="some-id"`, as a link (as plain text inside an
  existing link). Use it for every "see page N". Never type page numbers by hand.
- `href="#p{{page:ch3}}"` links to a chapter. Give each opener `id="chN"`, and each appendix `id="appA"` and so on.
- `{{ISSUE}}`, `{{DATE}}`: from manual.json. Use them on the cover and in the document control table.

## Writing

- Plain and direct. Say what the thing does and what the reader should do. Short sentences.
- Numbers with units: a non-breaking space before the unit (`5&nbsp;V`, `300&nbsp;mA`), `×` for dimensions, an en
  dash for ranges (`330–420 mA`), `·` as a separator in labels.
- Each statement traces back to a source of truth (schematic, spec, code). Keep requirement tags and say which
  source wins when they disagree (see "Sources of truth" in an existing manual's front matter).
- Open items and known gaps don't belong in the manual. They go in the project's open-items list.

## Releasing an issue

1. Complete the issue's row on the revision history page: date, pages, what changed and why.
2. Set `issue` and `date` in `manual.json`.
3. Rebuild. It must report `overflow: none`.
4. Commit the sources (and the PDF, if the project commits it), then tag `manual-issue-N`. CI checks that the tag
   matches `issue` and attaches the PDF to a GitHub release.

## Changing the kit itself

Make style changes in this repo, not in a project's `kit/` folder. Build `.example` and check the previews.
Then update the submodule in each project and rebuild that project's manual, because a style change can make
pages overflow.
