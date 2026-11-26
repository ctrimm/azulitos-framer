"""SVG / PNG / Framer-JSON writers."""
from __future__ import annotations

import io
import json

import cairosvg
from PIL import Image

from . import motifs as M
from .designs import PALETTE, SIZE

LAYER_ORDER = ["azul", "verde", "manganes", "amarelo"]


def _ring_d(coords):
    pts = list(coords)[:-1]  # drop closing duplicate
    s = "M {:.1f} {:.1f}".format(*pts[0])
    s += "".join(" L {:.1f} {:.1f}".format(*p) for p in pts[1:])
    return s + " Z"


def poly_d(p):
    """One SVG path for a polygon with holes (even-odd)."""
    ext = p.exterior
    if ext.is_ccw:  # normalise winding: exterior clockwise in y-down coords
        ext = type(ext)(list(ext.coords)[::-1])
    return " ".join([_ring_d(ext.coords)] + [_ring_d(h.coords) for h in p.interiors])


def ordered_layers(layers):
    return [(k, layers[k]) for k in LAYER_ORDER if k in layers and not layers[k].is_empty]


def to_svg(tile, layers):
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{SIZE}" height="{SIZE}" viewBox="0 0 {SIZE} {SIZE}">',
           f"<title>{tile.id} {tile.name}</title>"]
    for key, g in ordered_layers(layers):
        ds = [poly_d(p) for p in M.as_polys(g)]
        out.append(f'<path id="{key}" fill="{PALETTE[key]}" fill-rule="evenodd" d="{" ".join(ds)}"/>')
    out.append("</svg>")
    return "\n".join(out) + "\n"


def svg_to_png(svg: str, px: int, background=None) -> Image.Image:
    data = cairosvg.svg2png(bytestring=svg.encode(), output_width=px, output_height=px,
                            background_color=background)
    return Image.open(io.BytesIO(data)).convert("RGBA")


def to_framer(tile, layers):
    """Shape list for the Framer build: each polygon is one exterior + its holes.

    fill "azul" means: bind to the vector set's Azul Color variable.
    Any other value is a static hex fill (Polícromo).
    """
    shapes = []
    for key, g in ordered_layers(layers):
        fill = "azul" if (key == "azul" and tile.group != "Polícromo") else PALETTE[key]
        for p in M.as_polys(g):
            ext = p.exterior
            if ext.is_ccw:
                ext = type(ext)(list(ext.coords)[::-1])
            shapes.append({"fill": fill, "d": _ring_d(ext.coords),
                           "holes": [_ring_d(h.coords) for h in p.interiors]})
    return {"id": tile.id, "name": f"{tile.id} {tile.name}", "group": tile.group, "shapes": shapes}


def write_json(path, obj):
    with open(path, "w") as f:
        json.dump(obj, f, separators=(",", ":"), ensure_ascii=False)
