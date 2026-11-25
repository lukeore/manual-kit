"""Rasterise pages of a built manual for review.

  python <kit>/preview.py [manual_dir] [--pages FIRST[-LAST]] [--dpi N]

manual_dir defaults to the folder the kit sits in. PNGs go to <manual>/.cache/preview/pNN.png.
"""
import argparse
import json
import os

import pymupdf

KIT = os.path.dirname(os.path.abspath(__file__))
ap = argparse.ArgumentParser(description='Rasterise manual pages to PNG.')
ap.add_argument('manual_dir', nargs='?', default=os.path.dirname(KIT))
ap.add_argument('--pages', help='page or range, e.g. 4 or 4-9 (default: all)')
ap.add_argument('--dpi', type=int, default=80)
args = ap.parse_args()

man = os.path.abspath(args.manual_dir)
with open(os.path.join(man, 'manual.json'), encoding='utf-8') as f:
    pdf = os.path.join(man, json.load(f)['output'])
out = os.path.join(man, '.cache', 'preview')
doc = pymupdf.open(pdf)
first, last = 1, doc.page_count
if args.pages:
    a, _, b = args.pages.partition('-')
    first = int(a)
    last = int(b) if b else first
os.makedirs(out, exist_ok=True)
for n in range(first, last + 1):
    doc[n - 1].get_pixmap(dpi=args.dpi).save(os.path.join(out, 'p%02d.png' % n))
print('pages %d-%d of %d -> %s' % (first, last, doc.page_count, out))
