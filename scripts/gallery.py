#!/usr/bin/env python3
"""Marketplace gallery renders (AGENT_INSTRUCTIONS §7). Run after build.py.

Canvas renders of the actual tile SVGs — no badge, no UI, no text burned in.
  marketplace/00-cover.png     mixed 4x4 panel (one Padrão family), cobalt on white
  marketplace/01-panel.png     single-tile 4x4 panel showing the merged rosettes
  marketplace/02-padrao.png    all 48 Padrão tiles
  marketplace/03-medalhao.png  all 16 Medalhão tiles
  marketplace/04-policromo.png all 8 Polícromo tiles
  marketplace/05-recolor.png   one panel in three Azul values
06-start-here comes from a screenshot of the Framer Start Here page.
The OG image and favicons in marketplace/ are not touched.
"""
from __future__ import annotations

import json
import os
import sys

from PIL import Image

sys.path.insert(0, os.path.dirname(__file__))
from azulitos.designs import AZUL  # noqa: E402
from azulitos.export import svg_to_png  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUT = os.path.join(ROOT, "marketplace")
W, H = 1600, 1200

COVER_FAMILY = "Roseta"   # mixed panel
PANEL_TILE = "AZL-01"     # single-tile panel
RECOLOR_TILE = "AZL-07"
RECOLORS = [AZUL, "#0E6B66", "#B4462E"]  # cobalt, deep teal, terracotta


def svg(tid):
    return open(os.path.join(ROOT, "assets", "svg", f"{tid}.svg")).read()


def tile(tid, px, colour=None):
    s = svg(tid)
    if colour:
        s = s.replace(AZUL, colour)
    return svg_to_png(s, px)


def panel(get, n, px):
    out = Image.new("RGBA", (n * px, n * px), (255, 255, 255, 255))
    for r in range(n):
        for c in range(n):
            out.alpha_composite(get(r, c), (c * px, r * px))
    return out


def canvas():
    return Image.new("RGBA", (W, H), (255, 255, 255, 255))


def grid_sheet(ids, cols, px, gap):
    rows = (len(ids) + cols - 1) // cols
    img = canvas()
    gw, gh = cols * px + (cols - 1) * gap, rows * px + (rows - 1) * gap
    x0, y0 = (W - gw) // 2, (H - gh) // 2
    for i, tid in enumerate(ids):
        img.alpha_composite(tile(tid, px), (x0 + (i % cols) * (px + gap), y0 + (i // cols) * (px + gap)))
    return img


def save(img, name):
    img.convert("RGB").save(os.path.join(OUT, f"{name}.png"), optimize=True)
    print("wrote", name)


def main():
    manifest = json.load(open(os.path.join(ROOT, "framer", "manifest.json")))
    by_group = lambda g: [m["id"] for m in manifest if m["group"] == g]
    fam = [m["id"] for m in manifest if m["family"] == COVER_FAMILY]

    px = 260
    cache = {t: tile(t, px) for t in fam}
    mixed = panel(lambda r, c: cache[fam[(r + 2 * c) % len(fam)]], 4, px)
    img = canvas()
    img.alpha_composite(mixed, ((W - 4 * px) // 2, (H - 4 * px) // 2))
    save(img, "00-cover")

    one = tile(PANEL_TILE, px)
    img = canvas()
    img.alpha_composite(panel(lambda r, c: one, 4, px), ((W - 4 * px) // 2, (H - 4 * px) // 2))
    save(img, "01-panel")

    save(grid_sheet(by_group("Padrão"), 8, 170, 22), "02-padrao")
    save(grid_sheet(by_group("Medalhão"), 6, 200, 34), "03-medalhao")
    save(grid_sheet(by_group("Polícromo"), 4, 300, 40), "04-policromo")

    px = 120
    img = canvas()
    gap = (W - 3 * 4 * px) // 4
    for k, col in enumerate(RECOLORS):
        t = tile(RECOLOR_TILE, px, col)
        img.alpha_composite(panel(lambda r, c: t, 4, px), (gap + k * (4 * px + gap), (H - 4 * px) // 2))
    save(img, "05-recolor")


if __name__ == "__main__":
    main()
