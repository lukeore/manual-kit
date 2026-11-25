# Manual kit

A house style and build pipeline for project manuals: A4-landscape PDFs written as HTML pages, printed by a
headless browser. Each project keeps its own pages, images and settings, and brings in this kit as a git submodule.

What it gives you:

- `manual.css`, `fonts/` and `_head.html`: the look. Dark chapter openers, a clickable thumb index, net colours,
  callout boxes, tables, key figures, diagram classes and schematic symbols.
- `build_manual.py` puts the pages together, fills in the contents and page links, checks every page for
  overflow, and prints the PDF with bookmarks and metadata.
- `preview.py` renders pages to PNG so you can review them.
- `workflow/manual.yml` is a GitHub Actions template that builds on every pull request and releases on a tag.
- `.example/` is a small sample manual that shows every page type and component.
- `CLAUDE.md` has the style rules for writing pages, for Claude and for people.

## Start a manual in a project

```sh
git submodule add https://github.com/lukeore/manual-kit.git doc/manual/kit
cp -r doc/manual/kit/.example/manual.json doc/manual/kit/.example/src doc/manual/kit/.example/img doc/manual/
cp doc/manual/kit/workflow/manual.yml .github/workflows/manual.yml
printf '.cache/\n*.pdf\nmanual.print.html\nmanual.check.html\n' >> doc/manual/.gitignore
```

Then:

1. Edit `doc/manual/manual.json` (see below), and replace the example pages and image.
2. Add `doc/manual/CLAUDE.md` with `@kit/CLAUDE.md` on its first line, followed by anything specific to the project.
3. Build: `python doc/manual/kit/build_manual.py`.

Cloning a project that uses the kit: `git clone --recurse-submodules …`, or `git submodule update --init` in an
existing clone.

## manual.json

| Key | Used for |
|---|---|
| `title` | PDF title and the page `<title>` |
| `output` | PDF file name, written next to `manual.json` |
| `issue`, `date` | Footer and the `{{ISSUE}}` and `{{DATE}}` tokens. The env vars `MANUAL_ISSUE` and `MANUAL_DATE` override them |
| `brand_html` | Brand in the page header. HTML is allowed: `Widget<b>-</b>1` colours the hyphen |
| `header_label` | Text after the brand, such as "Project manual" |
| `footer_html` | Copyright line in the footer |
| `author`, `copyright`, `subject`, `keywords` | PDF metadata |

Every key is required.

## Build

```sh
python -m pip install -r doc/manual/kit/requirements.txt     # pypdf, pymupdf
python doc/manual/kit/build_manual.py                        # PDF and manual.print.html in doc/manual/
python doc/manual/kit/build_manual.py --check                # overflow check only
python doc/manual/kit/preview.py --pages 3-5 --dpi 80        # PNGs in doc/manual/.cache/preview/
```

Both scripts take the manual folder as an optional first argument. By default they use the folder the kit sits in.

The build exits 1 if any page's content runs into the footer or the thumb tabs, or if the PDF's page count is
wrong. It needs a Chromium-based browser: Edge on Windows, Chrome or Chromium elsewhere. Set `MANUAL_BROWSER` to
choose one. Builds on Windows with Edge and on Linux with Chrome give the same pages.

## Source format

Each `src/NN-name.html` holds one or more `<section class="page">` elements, built in file-name order.

| Markup | Effect |
|---|---|
| `data-ch="3" data-ch-title="Power"` | Starts chapter 3: a thumb tab and a contents entry. Later pages inherit it |
| `data-ch="A"` | Starts an appendix |
| `data-ch="~"` | Starts back matter: in the contents, but no number and no tab |
| `data-ref` | REFERENCE tag in the header, for printable bench pages |
| `<h2>` | A contents entry. Add `data-notoc` to skip it |
| `<nav class="toc"></nav>` | Full contents |
| `<nav class="toc-mini"></nav>` | The current chapter's sections, on chapter openers |
| `{{page:id}}` | Number of the page holding `id`, as a link |
| `{{ISSUE}}`, `{{DATE}}` | From manual.json |
| `{{seg:0xNN}}` | A 7-segment digit glyph (bit order 0 f, 1 e, 2 a, 3 g, 4 d, 5 b, 6 c, 7 DP) |
| `<figure class="pcbfig" data-img="board_top" data-mode="callouts" data-wmm="60" data-items="U2\|Label\|Sub;…">` | A PCB render with labelled leader lines. Needs `img/calib.json` (mm-to-pixel calibration and footprint positions) from the project's image tools |

`CLAUDE.md` has the page types, components and style rules.

## CI

`workflow/manual.yml` checks out submodules, builds with Chrome on Ubuntu, and uploads the PDF and page previews.
On a `manual-issue-N` tag it also checks that `issue` in manual.json is "Issue N" and attaches the PDF to a GitHub
release.

If this kit repo is private, the default `GITHUB_TOKEN` can't read it. Either make the kit public, or give the
checkout step a token that can, for example a fine-grained personal access token with read access to this repo,
stored as a secret: `with: { submodules: true, token: ${{ secrets.MANUAL_KIT_TOKEN }} }`.

Don't commit the PDF. Let CI publish it to a release on each `manual-issue-N` tag, and link to the release
download (`…/releases/download/manual-issue-N/<output>.pdf`) from the project README. Pull requests get the PDF
and previews as a workflow artifact for review. Artifacts expire, so they are not the published copy.

This repo's own workflow builds `.example` on every push.

## Updating a project to a newer kit

```sh
cd doc/manual/kit && git pull origin main && cd -
python doc/manual/kit/build_manual.py          # a style change can make pages overflow
git add doc/manual/kit && git commit -m "Update manual kit"
```

## Licences

The fonts are under the SIL Open Font License 1.1 (`fonts/OFL.txt`).
