"""Build a manual PDF in the house style from <manual>/src/*.html.

  python <kit>/build_manual.py [manual_dir] [--check] [--expect-issue "Issue N"]
  (needs pypdf: python -m pip install -r <kit>/requirements.txt)

  manual_dir            folder holding manual.json, src/ and img/. Default: the folder the kit sits in,
                        so with the kit at doc/manual/kit it builds doc/manual.
  --check               lay out and check for overflow only, no PDF
  --expect-issue X      fail unless the issue is X (CI passes this on a manual-issue-N tag)
Exits 1 if a page overflows or the PDF page count is wrong, so CI can gate on it.

Manual-specific settings live in <manual>/manual.json (see .example/manual.json):
  title, output (PDF file name), issue, date           - issue/date also fill {{ISSUE}} and {{DATE}} in the sources
  brand_html, header_label, footer_html                - page header and footer (HTML allowed)
  author, copyright, subject, keywords                 - PDF metadata (author also fills {{AUTHOR}} in _head.html)

Browser: headless Edge on Windows, Chrome or Chromium elsewhere; MANUAL_BROWSER overrides.
MANUAL_ISSUE and MANUAL_DATE override issue and date from manual.json.

The page shell (_head.html), manual.css and fonts/ come from the kit; the output HTML links to them.
Files in src/ whose names start with "_" are skipped.

Source format: each src/NN-*.html file holds fixed-size pages, <section class="page" ...>.
  data-ch="3"           starts chapter 3 (the next pages inherit it); data-ch-title="Power & protection"
  data-ch="~"           starts back matter (in the contents, but no number and no thumb tab)
  data-ref              marks a reference page meant for printing (adds a REFERENCE tag)
  <h2>                  becomes a contents entry (add data-notoc to skip one)
  <nav class="toc"></nav>            full contents (filled in here)
  <nav class="toc-mini"></nav>       the current chapter's sections (on chapter openers)
  <figure class="pcbfig" data-img="tree_a_top" data-mode="pixels" data-wmm="70"></figure>
  <figure class="pcbfig" data-img="controller_top" data-mode="callouts" data-wmm="60"
          data-items="U2|Current limit|TPS2553;LED1+LED16|Display"></figure>
  {{page:id}}           page number of the page holding element id, as a link (plain inside an existing link)
Output: <manual>/<output from manual.json>, and <manual>/manual.print.html.
"""
import argparse
import glob
import html
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys

try:
    from pypdf import PdfReader, PdfWriter
except ImportError:
    sys.exit('needs pypdf: python -m pip install -r %s' % os.path.join(os.path.dirname(__file__), 'requirements.txt'))

KIT = os.path.dirname(os.path.abspath(__file__))
ap = argparse.ArgumentParser(description='Build a manual PDF in the house style.')
ap.add_argument('manual_dir', nargs='?', default=os.path.dirname(KIT),
                help='folder with manual.json, src/ and img/ (default: the folder the kit sits in)')
ap.add_argument('--check', action='store_true', help='overflow check only, no PDF')
ap.add_argument('--expect-issue', metavar='ISSUE', help='fail unless the manual is at this issue')
ARGS = ap.parse_args()
MAN = os.path.abspath(ARGS.manual_dir)
if not os.path.exists(os.path.join(MAN, 'manual.json')):
    sys.exit('%s has no manual.json - pass the manual folder, or copy %s to start one'
             % (MAN, os.path.join(KIT, '.example')))


def rel(path):
    """Path for messages: relative to the current folder when that is shorter."""
    try:
        r = os.path.relpath(path)
        return r if len(r) < len(path) else path
    except ValueError:                          # different drive on Windows
        return path


CACHE = os.path.join(MAN, '.cache')
OUT_HTML = os.path.join(MAN, 'manual.print.html')
EDGE = r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'


def load_config():
    """Everything specific to this manual lives in <manual>/manual.json (see the module docstring)."""
    path = os.path.join(MAN, 'manual.json')
    with open(path, encoding='utf-8') as f:
        cfg = json.load(f)
    missing = [k for k in CONFIG_KEYS if not cfg.get(k)]
    if missing:
        sys.exit('%s: missing %s' % (rel(path), ', '.join(missing)))
    return cfg


CONFIG_KEYS = ('title', 'output', 'issue', 'date', 'brand_html', 'header_label', 'footer_html',
               'author', 'copyright', 'subject', 'keywords')
CFG = load_config()
OUT_PDF = os.path.join(MAN, CFG['output'])
ISSUE = os.environ.get('MANUAL_ISSUE') or CFG['issue']
DATE = os.environ.get('MANUAL_DATE') or CFG['date']
TITLE = CFG['title']
BACK = '~'                     # data-ch key for back matter: listed in the contents, no number, no thumb tab

PAGE_RE = re.compile(r'<section class="page([^"]*)"([^>]*)>(.*?)</section>', re.S)


def attr(s, name):
    m = re.search(r'\b%s="([^"]*)"' % name, s)
    if m:
        return m.group(1)
    return '' if re.search(r'\b%s\b' % name, s) else None


def slug(t):
    return re.sub(r'[^a-z0-9]+', '-', re.sub(r'<[^>]+>', '', t).lower()).strip('-')


# ---------------------------------------------------------------- PCB overlays
CAL = None


def calib():
    global CAL
    if CAL is None:
        with open(os.path.join(MAN, 'img', 'calib.json')) as f:
            CAL = json.load(f)
    return CAL


def board_of(img):
    return img.rsplit('_', 1)[0]


def point(img, spec):
    """'U2' or 'LED1+LED16' (centroid) or '@x,y' (KiCad mm) -> image px."""
    c = calib()
    cal = c['calib'][img]
    fps = c['boards'][board_of(img)]['fp']
    if spec.startswith('@'):
        x, y = (float(v) for v in spec[1:].split(','))
    else:
        pts = [fps[r] for r in spec.split('+')]
        x = sum(p[0] for p in pts) / len(pts)
        y = sum(p[1] for p in pts) / len(pts)
    return cal['ax'] * x + cal['bx'], cal['ay'] * y + cal['by']


def pcbfig(attrs):
    img = attr(attrs, 'data-img')
    mode = attr(attrs, 'data-mode') or 'plain'
    wmm = float(attr(attrs, 'data-wmm') or 60)
    style = attr(attrs, 'style') or ''
    cls = attr(attrs, 'class') or 'pcbfig'
    c = calib()
    cal = c['calib'][img]
    w, h = cal['w'], cal['h']
    u = w / wmm                                   # viewBox units per mm on the page
    parts = []
    if mode == 'pixels':
        side = 'B' if img.endswith('_bottom') else 'F'
        fps = c['boards'][board_of(img)]['fp']
        r = 2.05 * u
        for ref, (x, y, s, _v) in sorted(fps.items()):
            if s != side or not re.fullmatch(r'D\d+', ref):
                continue
            n = int(ref[1:])
            px, py = cal['ax'] * x + cal['bx'], cal['ay'] * y + cal['by']
            col = '#e0a100' if n in (16, 26) else ('#17b26a' if n <= 21 else '#2f6fe4')
            bx, by = px + r * 1.15, py - r * 1.15
            parts.append('<g class="badge"><circle cx="%.1f" cy="%.1f" r="%.1f" fill="%s"/>'
                         '<text x="%.1f" y="%.1f" font-size="%.1f">%d</text></g>'
                         % (bx, by, r, col, bx, by + .1 * r, 1.05 * r, n))
    elif mode == 'callouts':
        items = []
        for it in (attr(attrs, 'data-items') or '').split(';'):
            if not it.strip():
                continue
            f = it.split('|')
            px, py = point(img, f[0].strip())
            forced = f[3].strip() if len(f) > 3 else ''
            side = forced or ('L' if px < w / 2 else 'R')
            items.append({'px': px, 'py': py, 'label': f[1].strip(), 'sub': f[2].strip() if len(f) > 2 else '',
                          'side': side})
        fs = 2.75 * u
        gap = 4.0 * u
        for side in ('L', 'R'):
            grp = sorted([i for i in items if i['side'] == side], key=lambda i: i['py'])
            pitch = fs * 2.55
            ys = [i['py'] for i in grp]
            for _ in range(60):                    # relax labels apart, keep inside the figure height
                for k in range(1, len(ys)):
                    if ys[k] - ys[k - 1] < pitch:
                        d = (pitch - (ys[k] - ys[k - 1])) / 2
                        ys[k - 1] -= d
                        ys[k] += d
                for k in range(len(ys)):
                    ys[k] = min(max(ys[k], fs), h - fs * 1.6)
            for i, ly in zip(grp, ys):
                ex = -gap if side == 'L' else w + gap
                tx = ex - fs * .5 if side == 'L' else ex + fs * .5
                anchor = 'end' if side == 'L' else 'start'
                parts.append('<polyline class="lead" points="%.1f,%.1f %.1f,%.1f %.1f,%.1f" stroke-width="%.2f"/>'
                             % (i['px'], i['py'], (0 - gap * .35) if side == 'L' else (w + gap * .35), ly, ex, ly,
                                .32 * u))
                parts.append('<circle class="lead-dot" cx="%.1f" cy="%.1f" r="%.1f" stroke-width="%.2f"/>'
                             % (i['px'], i['py'], .95 * u, .35 * u))
                parts.append('<text class="lbl" x="%.1f" y="%.1f" font-size="%.1f" text-anchor="%s">%s</text>'
                             % (tx, ly - (fs * .42 if i['sub'] else 0), fs, anchor, html.escape(i['label'])))
                if i['sub']:
                    parts.append('<text class="lbl-sub" x="%.1f" y="%.1f" font-size="%.1f" text-anchor="%s">%s</text>'
                                 % (tx, ly + fs * .62, fs * .82, anchor, html.escape(i['sub'])))
    svg = '<svg class="ov" viewBox="0 0 %d %d" preserveAspectRatio="none">%s</svg>' % (w, h, ''.join(parts))
    return ('<figure class="%s" style="width:%.1fmm;%s"><img src="img/%s.jpg" alt="">%s</figure>'
            % (cls, wmm, style, img, svg))


# ---------------------------------------------------------------- 7-segment glyphs
# XL9555 port bit order on LO-002 (both digits): 0 f, 1 e, 2 a, 3 g, 4 d, 5 b, 6 c, 7 DP
SEGS = {  # bit: polygon in a 26 x 40 box
    2: 'M6 2h13l-2 3h-9z',            # a
    5: 'M20 3l1.5 1.5v13l-2 2-1.5-2v-11z',  # b
    6: 'M20 21l1.5 1.5v13l-1.5 1.5-2-3v-11z',  # c
    4: 'M6 38h13l-2-3h-9z',           # d
    1: 'M5 21l1.5 2v11l-2 3-1.5-1.5v-13z',  # e
    0: 'M5 3l1.5 3v11l-1.5 2-1.5-1.5v-13z',  # f
    3: 'M6.5 18.5h12l1.5 1.5-1.5 1.5h-12l-1.5-1.5z',  # g
}


def seg_svg(mask, h=9):
    parts = []
    for bit, d in SEGS.items():
        on = mask >> bit & 1
        parts.append('<path d="%s" fill="%s"/>' % (d, '#ff3b30' if on else '#e7ebe9'))
    parts.append('<circle cx="24.5" cy="37" r="1.6" fill="%s"/>' % ('#ff3b30' if mask & 128 else '#e7ebe9'))
    return ('<svg viewBox="0 0 27 40" style="height:%smm;vertical-align:middle;background:#1a2226;border-radius:.8mm;padding:.5mm">%s</svg>'
            % (h, ''.join(parts)))


# ---------------------------------------------------------------- assembly
def load_pages():
    pages = []
    for fn in sorted(glob.glob(os.path.join(MAN, 'src', '*.html'))):
        if os.path.basename(fn).startswith('_'):
            continue
        with open(fn, encoding='utf-8') as f:
            text = f.read()
        for m in PAGE_RE.finditer(text):
            pages.append({'cls': m.group(1), 'attrs': m.group(2), 'body': m.group(3), 'src': os.path.basename(fn)})
    return pages


def build():
    pages = load_pages()
    chapters = []                       # (key, title, first page index)
    cur = None
    toc = []                            # (chapter key, title, id, page no)
    ids = {}
    for n, p in enumerate(pages, 1):
        p['n'] = n
        ch = attr(p['attrs'], 'data-ch')
        if ch is not None:
            cur = (ch, attr(p['attrs'], 'data-ch-title'), n)
            chapters.append(cur)
        p['ch'] = cur

        def h2id(m):
            a, t = m.group(1), m.group(2)
            hid = attr(a, 'id') or slug(t)
            if hid in ids:
                hid += '-%d' % n
            ids[hid] = n
            if 'data-notoc' not in a and p['ch']:
                entry = re.sub(r'<[^>]+>', '', re.sub(r'<span class="req".*?</span>', '', t)).strip()
                entry = re.sub(r'^Appendix [A-Z] · ', '', entry)     # the chapter line already says which appendix
                toc.append((p['ch'][0], entry, hid, n))
            a = re.sub(r'\s*id="[^"]*"', '', a)
            return '<h2 id="%s"%s>%s</h2>' % (hid, a, t)

        p['body'] = re.sub(r'<h2([^>]*)>(.*?)</h2>', h2id, p['body'], flags=re.S)
        for m in re.finditer(r'\bid="([^"]+)"', p['attrs'] + p['body']):
            ids.setdefault(m.group(1), n)
    total = len(pages)

    chap_title = {k: t for k, t, _ in chapters}
    chap_first = {k: f for k, _, f in chapters}
    out = []
    for p in pages:
        body = p['body']
        body = re.sub(r'<figure class="(pcbfig[^"]*)"([^>]*)></figure>',
                      lambda m: pcbfig(m.group(2) + ' class="%s"' % m.group(1)), body)
        pg = lambda key: str(ids.get(key, '?'))
        body = re.sub(r'href="#p\{\{page:([^}]+)\}\}"', lambda m: 'href="#p%s"' % pg(m.group(1)), body)

        def page_link(m):                   # a bare page number in text becomes a link, unless already in one
            before = body[:m.start()]
            if before.rfind('<a') > before.rfind('</a>'):
                return pg(m.group(1))
            return '<a href="#p%s">%s</a>' % (pg(m.group(1)), pg(m.group(1)))
        body = re.sub(r'\{\{page:([^}]+)\}\}', page_link, body)
        body = body.replace('{{ISSUE}}', ISSUE).replace('{{DATE}}', DATE)
        body = re.sub(r'\{\{seg:(0x[0-9A-Fa-f]+)(?::([\d.]+))?\}\}',
                      lambda m: seg_svg(int(m.group(1), 16), m.group(2) or 9), body)
        if '<nav class="toc"></nav>' in body:
            parts = []
            for k, t, f in chapters:
                if k in ('0',):
                    continue
                parts.append('<div class="ch"><a href="#p%d"><span class="n">%s</span>%s<span class="p">%d</span></a>'
                             % (f, '' if k == BACK else k, t, f))
                for ck, st, hid, pn in toc:
                    if ck == k and html.unescape(st) != html.unescape(t):   # a page titled like its chapter needs no second line
                        parts.append('<a class="s" href="#%s">%s<span class="p">%d</span></a>' % (hid, st, pn))
                parts.append('</div>')
            body = body.replace('<nav class="toc"></nav>', '<nav class="toc">%s</nav>' % ''.join(parts))
        if '<nav class="toc-mini"></nav>' in body and p['ch']:
            items = ''.join('<a href="#%s">%s<span>%d</span></a>' % (hid, st, pn)
                            for ck, st, hid, pn in toc if ck == p['ch'][0])
            body = body.replace('<nav class="toc-mini"></nav>', '<nav class="toc-mini">%s</nav>' % items)
        cls = p['cls']
        frame = ''
        if 'cover' not in cls:
            ch = p['ch']
            chap = '' if not ch or ch[0] == '0' else ch[1] if ch[0] == BACK else '%s&ensp;%s' % (ch[0], ch[1])
            tag = '<span class="tag">Reference</span>' if attr(p['attrs'], 'data-ref') is not None else ''
            frame += ('<div class="page-head"><span class="brand">%s</span><span>%s</span>'
                      '%s<span class="chap">%s</span></div>' % (CFG['brand_html'], CFG['header_label'], tag, chap))
            frame += ('<div class="page-foot"><span>%s &middot; %s</span><span>%s</span>'
                      '<span class="num">%d<small>/ %d</small></span></div>' % (ISSUE, DATE, CFG['footer_html'], p['n'], total))
            thumbs = ''.join('<a href="#p%d" class="%s">%s</a>' % (f, 'on' if ch and k == ch[0] else '', k)
                             for k, _, f in chapters if k not in ('0', BACK))
            frame += '<nav class="thumbs">%s</nav>' % thumbs
        other = re.sub(r'\s*(data-[a-z-]+|id)(="[^"]*")?', '', p['attrs'])
        out.append('<section class="page%s" id="p%d"%s>%s%s</section>\n<!-- %s -->' %
                   (cls, p['n'], other, frame, body, p['src']))

    with open(os.path.join(KIT, '_head.html'), encoding='utf-8') as f:
        head = f.read()
    kit_href = pathlib.PurePath(os.path.relpath(KIT, MAN)).as_posix()     # manual.css and fonts, seen from the output HTML
    head = (head.replace('{{TITLE}}', html.escape(TITLE)).replace('{{AUTHOR}}', html.escape(CFG['author']))
            .replace('{{KIT}}', kit_href))
    doc = head + '\n'.join(out) + '\n</body>\n</html>\n'
    with open(OUT_HTML, 'w', encoding='utf-8') as f:
        f.write(doc)
    print('pages: %d  chapters: %s' % (total, ', '.join('%s=%d' % (k, f) for k, _, f in chapters)))
    return doc, total


CHECK_JS = r'''
<script>
document.fonts.ready.then(function () {
  var mm = 96 / 25.4, bad = [];
  document.querySelectorAll('section.page').forEach(function (pg) {
    if (pg.classList.contains('cover')) return;
    var r = pg.getBoundingClientRect(), lim = r.bottom - 12.5 * mm, rlim = r.right - 21 * mm;
    var worst = 0, wr = 0, who = '';
    pg.querySelectorAll('.body *, .sch *').forEach(function (el) {
      if (el.closest('svg.ov') || el.closest('.thumbs')) return;
      var b = el.getBoundingClientRect();
      if (b.height === 0) return;
      if (b.bottom - lim > worst) { worst = b.bottom - lim; who = el.tagName + '.' + el.className; }
      if (b.right - rlim > wr && !el.closest('.opener .side')) { wr = b.right - rlim; }
    });
    if (worst > 1 || wr > 1) bad.push(pg.id + ':' + (worst / mm).toFixed(1) + 'mm-down,' + (wr / mm).toFixed(1) + 'mm-right(' + who + ')');
  });
  document.title = 'OVERFLOW:' + (bad.join(' | ') || 'none');
});
</script>
'''


def browser():
    """The headless browser to print with: MANUAL_BROWSER, else Edge on Windows, else Chrome/Chromium on PATH."""
    if os.environ.get('MANUAL_BROWSER'):
        return shutil.which(os.environ['MANUAL_BROWSER']) or os.environ['MANUAL_BROWSER']
    if sys.platform == 'win32' and os.path.exists(EDGE):
        return EDGE
    for name in ('google-chrome', 'google-chrome-stable', 'chromium', 'chromium-browser', 'msedge'):
        if shutil.which(name):
            return shutil.which(name)
    sys.exit('no headless browser found: install Chrome or Chromium, or set MANUAL_BROWSER')


def uri(path):
    return pathlib.Path(path).resolve().as_uri()


def edge(args):
    """Run the headless browser and wait for it.
    On Windows msedge.exe hands off to a child process and returns at once, so go through PowerShell's
    Start-Process -Wait, which waits for the whole process tree. Elsewhere Chrome blocks until it is done."""
    exe = browser()
    prof = os.path.join(CACHE, 'edge-profile')
    os.makedirs(prof, exist_ok=True)
    base = ['--headless=new', '--disable-gpu', '--no-first-run', '--user-data-dir=' + prof,
            '--allow-file-access-from-files', '--run-all-compositor-stages-before-draw',
            '--virtual-time-budget=20000']
    if sys.platform == 'win32':
        arglist = ','.join("'%s'" % a.replace("'", "''") for a in base + args)
        ps = "Start-Process -FilePath '%s' -ArgumentList @(%s) -Wait" % (exe, arglist)
        return subprocess.run(['powershell', '-NoProfile', '-Command', ps], capture_output=True, text=True)
    if sys.platform.startswith('linux'):
        base += ['--no-sandbox', '--disable-dev-shm-usage']     # CI runners and containers block Chrome's sandbox
    return subprocess.run([exe] + base + args, capture_output=True, text=True, timeout=300)


def check(doc):
    """Lay the document out in Edge and report any page whose content runs into the footer or thumb tabs.
    The page script writes its findings into document.title, which ends up in the PDF's metadata."""
    path = os.path.join(MAN, 'manual.check.html')
    tmp = os.path.join(CACHE, 'check.pdf')
    with open(path, 'w', encoding='utf-8') as f:
        f.write(doc.replace('</body>', CHECK_JS + '</body>'))
    if os.path.exists(tmp):
        os.remove(tmp)
    edge(['--no-pdf-header-footer', '--print-to-pdf=' + tmp, uri(path)])
    os.remove(path)
    res = 'check did not run'
    try:
        res = PdfReader(tmp).metadata.get('/Title', res)
    except Exception as e:                      # noqa: BLE001
        res += ' (%s)' % e
    res = res.replace('OVERFLOW:', '')
    print('overflow:', res.replace(' | ', '\n  '))
    return res == 'none'


def pdf(total):
    tmp = OUT_PDF + '.tmp'
    r = edge(['--no-pdf-header-footer', '--generate-pdf-document-outline', '--print-to-pdf=' + tmp,
              uri(OUT_HTML)])
    if not os.path.exists(tmp):
        sys.exit('print failed:\n' + r.stderr[-2000:])
    rd = PdfReader(tmp)
    wr = PdfWriter(clone_from=rd)
    wr.add_metadata({'/Title': TITLE, '/Author': CFG['author'], '/Copyright': CFG['copyright'],
                     '/Subject': CFG['subject'], '/Keywords': CFG['keywords']})
    wr.page_mode = '/UseOutlines'
    with open(OUT_PDF, 'wb') as f:
        wr.write(f)
    os.remove(tmp)
    n = len(rd.pages)
    print('pdf: %s  (%d pages, %.1f MB)' % (rel(OUT_PDF), n, os.path.getsize(OUT_PDF) / 1e6))
    if n != total:
        print('ERROR: PDF has %d pages, expected %d - a page overflowed onto a second sheet' % (n, total))
    return n == total


if __name__ == '__main__':
    if ARGS.expect_issue and ARGS.expect_issue != ISSUE:
        sys.exit('ERROR: building %r but the tag says %r - bump issue/date in manual.json and the revisions page'
                 % (ISSUE, ARGS.expect_issue))
    doc, total = build()
    ok = check(doc)
    if not ARGS.check:
        ok = pdf(total) and ok
    sys.exit(0 if ok else 1)
