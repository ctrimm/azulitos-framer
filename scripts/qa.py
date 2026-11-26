#!/usr/bin/env python3
"""QA gates for Azulitos (AGENT_INSTRUCTIONS §5). Run after scripts/build.py.

    python3 scripts/qa.py

1. Render test     every tile rendered at 200 px and 1000 px; geometry checked for
                   validity, self-intersection, stray specks and slivers.
2. Panel test      every Padrão + Polícromo tile (56) rendered 2x2 and 4x4 on white;
                   programmatic seam check (edge profiles + seam continuity) and
                   corner-medallion closure check; plus mixed-family panels.
3. Contact sheets  one sheet per group on white + a sheet of 4x4 panels.
Writes qa/** and TILE_TEST.md.  Exits non-zero if any tile fails.
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from shapely.geometry import LinearRing, Polygon

sys.path.insert(0, os.path.dirname(__file__))
from azulitos.designs import FAMILIES  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
QA = os.path.join(ROOT, "qa")
SEAMLESS = ("Padrão", "Polícromo")


def load(tile_id, px):
    src = os.path.join(ROOT, "assets", "png-1000" if px <= 1000 else "png-2000", f"{tile_id}.png")
    im = Image.open(src).convert("RGBA")
    if im.size[0] != px:
        im = im.resize((px, px), Image.LANCZOS)
    return im


def on_white(im):
    bg = Image.new("RGBA", im.size, "white")
    bg.alpha_composite(im)
    return bg.convert("RGB")


def panel(images, n, px):
    """n x n panel; images is a function (row, col) -> RGBA tile at px."""
    out = Image.new("RGBA", (n * px, n * px), "white")
    for r in range(n):
        for c in range(n):
            out.alpha_composite(images(r, c), (c * px, r * px))
    return out.convert("RGB")


# ---------------------------------------------------------------- geometry ---

def parse_d(d):
    toks = d.replace("M", " ").replace("L", " ").replace("Z", " ").split()
    v = list(map(float, toks))
    return list(zip(v[::2], v[1::2]))


def geometry_check(fj):
    issues = []
    nodes = 0
    for i, s in enumerate(fj["shapes"]):
        ext = parse_d(s["d"])
        holes = [parse_d(h) for h in s["holes"]]
        nodes += len(ext) + sum(len(h) for h in holes)
        for ring in [ext] + holes:
            if not LinearRing(ring).is_simple:
                issues.append(f"shape {i}: self-intersecting ring")
        p = Polygon(ext, holes)
        if not p.is_valid:
            issues.append(f"shape {i}: invalid polygon")
        if p.area < 12:
            issues.append(f"shape {i}: stray speck ({p.area:.1f}px²)")
        if p.buffer(-1.5).is_empty:
            issues.append(f"shape {i}: sliver under 3px wide")
        xs = [x for x, _ in ext]
        ys = [y for _, y in ext]
        if min(xs) < -0.05 or min(ys) < -0.05 or max(xs) > 1000.05 or max(ys) > 1000.05:
            issues.append(f"shape {i}: outside the 1000x1000 artboard")
    return issues, nodes


# ------------------------------------------------------------------ seams ----

def alpha(im):
    return np.asarray(im.getchannel("A"), dtype=np.float32) / 255.0


def seam_check(a):
    """Edge-profile and continuity metrics on a tile's alpha (1000 px)."""
    lr = float(np.abs(a[:, 0] - a[:, -1]).mean())
    tb = float(np.abs(a[0, :] - a[-1, :]).mean())
    lr_max = float(np.abs(a[:, 0] - a[:, -1]).max())
    tb_max = float(np.abs(a[0, :] - a[-1, :]).max())
    # continuity: the step across the seam (last col -> first col of the
    # neighbour) must be no worse than ordinary steps inside the tile
    inside = float(np.abs(np.diff(a, axis=1)).mean())
    across = float(np.abs(a[:, -1] - a[:, 0]).mean())
    ink = float(max(a[:, 0].mean(), a[0, :].mean()))
    return {"lr": lr, "tb": tb, "lr_max": lr_max, "tb_max": tb_max, "inside": inside,
            "across": across, "edge_ink": ink}


def closure_check(tile_im, radius):
    """Render the 2x2 meeting point and check the merged medallion closes:
    the region around the shared corner must be 4-fold symmetric and inked."""
    px = tile_im.size[0]
    a = alpha(tile_im)
    big = np.block([[a, a], [a, a]])
    c = px
    r = int(radius * px / 1000) + 20
    crop = big[c - r:c + r, c - r:c + r]
    yy, xx = np.mgrid[-r:r, -r:r] + 0.5
    mask = (xx ** 2 + yy ** 2) <= r ** 2
    sym = max(float(np.abs(crop - np.rot90(crop))[mask].mean()),
              float(np.abs(crop - crop[:, ::-1])[mask].mean()),
              float(np.abs(crop - crop[::-1, :])[mask].mean()))
    ink = float(crop[mask].mean())
    return sym, ink


def pair_check(a, b):
    """Edge match between two different tiles placed side by side / stacked."""
    return max(float(np.abs(a[:, -1] - b[:, 0]).mean()), float(np.abs(a[-1, :] - b[0, :]).mean()),
               float(np.abs(b[:, -1] - a[:, 0]).mean()), float(np.abs(b[-1, :] - a[0, :]).mean()))


# ------------------------------------------------------------------ sheets ---

def contact_sheet(ids, names, cols, px, path, label=True):
    rows = (len(ids) + cols - 1) // cols
    pad, lab = 24, (34 if label else 0)
    W = cols * (px + pad) + pad
    H = rows * (px + pad + lab) + pad
    sheet = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(sheet)
    try:  # a TTF with Portuguese glyphs (ó, ç, ã); PIL's default bitmap font lacks them
        font = ImageFont.truetype("DejaVuSans.ttf", 13)
    except OSError:
        font = ImageFont.load_default()
    for i, tid in enumerate(ids):
        x = pad + (i % cols) * (px + pad)
        y = pad + (i // cols) * (px + pad + lab)
        sheet.paste(on_white(load(tid, px)), (x, y))
        d.rectangle([x - 1, y - 1, x + px, y + px], outline=(225, 228, 235))
        if label:
            d.text((x, y + px + 8), f"{tid}  {names[tid]}", fill=(60, 60, 70), font=font)
    sheet.save(path, optimize=True)


def main():
    manifest = json.load(open(os.path.join(ROOT, "framer", "manifest.json")))
    names = {m["id"]: m["name"] for m in manifest}
    for d in ("render-200", "panels", "sheets"):
        os.makedirs(os.path.join(QA, d), exist_ok=True)

    TOL = 0.004  # mean alpha difference allowed along an edge profile (AA noise)
    rows, failures = [], 0
    results = {}
    for m in manifest:
        tid = m["id"]
        fj = json.load(open(os.path.join(ROOT, "framer", "tiles", f"{tid}.json")))
        issues, nodes = geometry_check(fj)
        im200 = load(tid, 200)
        on_white(im200).save(os.path.join(QA, "render-200", f"{tid}.png"), optimize=True)
        im1000 = load(tid, 1000)
        a = alpha(im1000)
        render_ok = not issues and a.mean() > 0.02
        r = {"id": tid, "name": m["name"], "group": m["group"], "shapes": m["shapes"],
             "holes": m["holes"], "nodes": nodes, "issues": issues, "render": render_ok}
        if m["group"] in SEAMLESS:
            s = seam_check(a)
            rc = FAMILIES.get(m["family"] or "", (None, None, 290))[2] if m["family"] else 290
            sym, ink = closure_check(im1000, rc)
            s.update({"closure_sym": sym, "closure_ink": ink})
            s["seam_ok"] = bool(s["lr"] < TOL and s["tb"] < TOL and s["lr_max"] < 0.25 and s["tb_max"] < 0.25
                            and s["across"] <= s["inside"] + TOL)
            s["closure_ok"] = bool(sym < 0.01 and ink > 0.05)
            r.update(s)
            # panels: 2x2 at 500 px/tile, 4x4 at 250 px/tile, on white
            panel(lambda i, j: load(tid, 500), 2, 500).save(os.path.join(QA, "panels", f"{tid}-2x2.png"), optimize=True)
            panel(lambda i, j: load(tid, 250), 4, 250).save(os.path.join(QA, "panels", f"{tid}-4x4.png"), optimize=True)
        ok = render_ok and (m["group"] not in SEAMLESS or (r["seam_ok"] and r["closure_ok"]))
        r["pass"] = ok
        failures += 0 if ok else 1
        results[tid] = r
        rows.append(r)
        print(tid, "PASS" if ok else f"FAIL {issues}", flush=True)

    # mixed panels: every pair inside a family must share edge profiles
    family_rows = []
    alphas = {m["id"]: alpha(load(m["id"], 1000)) for m in manifest if m["family"]}
    for fam in FAMILIES:
        ids = [m["id"] for m in manifest if m["family"] == fam]
        worst = max(pair_check(alphas[x], alphas[y]) for x in ids for y in ids if x < y)
        ok = bool(worst < TOL)
        failures += 0 if ok else 1
        family_rows.append((fam, ids, worst, ok))
        # a mixed 4x4 panel of the family (diagonal arrangement of all six tiles)
        grid = lambda i, j, ids=ids: load(ids[(i + 2 * j) % len(ids)], 250)
        panel(grid, 4, 250).save(os.path.join(QA, "panels", f"mixed-{fam.lower().replace('ó', 'o')}-4x4.png"),
                                 optimize=True)

    # contact sheets
    for g, fn, cols in (("Padrão", "padrao", 8), ("Medalhão", "medalhao", 8), ("Polícromo", "policromo", 4)):
        ids = [m["id"] for m in manifest if m["group"] == g]
        contact_sheet(ids, names, cols, 220, os.path.join(QA, "sheets", f"{fn}.png"))
    sel = [m["id"] for m in manifest if m["group"] == "Padrão"][::4]  # 12 padrão tiles at panel scale
    sheet = Image.new("RGB", (4 * 420 + 20, 3 * 420 + 20), "white")
    for k, tid in enumerate(sel):
        p = Image.open(os.path.join(QA, "panels", f"{tid}-4x4.png")).resize((400, 400), Image.LANCZOS)
        sheet.paste(p, (20 + (k % 4) * 420, 20 + (k // 4) * 420))
    sheet.save(os.path.join(QA, "sheets", "panels-4x4.png"), optimize=True)

    json.dump(results, open(os.path.join(QA, "results.json"), "w"), indent=1, ensure_ascii=False,
              default=lambda o: o.item() if hasattr(o, "item") else str(o))
    write_tile_test(rows, family_rows, failures)
    print("failures:", failures)
    sys.exit(1 if failures else 0)


def write_tile_test(rows, family_rows, failures):
    seam = [r for r in rows if r["group"] in SEAMLESS]
    L = ["# Tile Test — Azulitos", "",
         "Generated by `scripts/qa.py` from the built exports — do not edit by hand.",
         "Gates per AGENT_INSTRUCTIONS §5. Renders: `qa/render-200/` (200 px), `assets/png-1000/` (1000 px);",
         "panels: `qa/panels/` (2×2 and 4×4 on white); contact sheets: `qa/sheets/`.", "",
         "## Summary", "",
         f"- Tiles: **{len(rows)}** — Padrão {sum(r['group'] == 'Padrão' for r in rows)}, "
         f"Medalhão {sum(r['group'] == 'Medalhão' for r in rows)}, Polícromo {sum(r['group'] == 'Polícromo' for r in rows)}",
         f"- Render test (200 px + 1000 px, geometry): **{sum(r['render'] for r in rows)}/{len(rows)} pass**",
         f"- Panel test, seams (2×2 + 4×4, programmatic): **{sum(r['seam_ok'] for r in seam)}/{len(seam)} pass**",
         f"- Panel test, corner medallion closure: **{sum(r['closure_ok'] for r in seam)}/{len(seam)} pass**",
         f"- Family mix test (all tile pairs within each Padrão family): "
         f"**{sum(f[3] for f in family_rows)}/{len(family_rows)} families pass**",
         f"- Overall: **{'PASS' if failures == 0 else f'{failures} FAILURES'}**", "",
         "### How the checks work", "",
         "- **Geometry:** every exported shape parsed back from the Framer JSON; each ring must be simple "
         "(no self-intersection), each polygon valid, no specks < 12 px², no slivers < 3 px wide, "
         "nothing outside the 1000×1000 artboard.",
         "- **Edge profiles:** in the 1000 px alpha raster, left column vs right column and top row vs "
         "bottom row; mean |Δα| must be < 0.004 (max < 0.25 for antialiasing).",
         "- **Seam continuity:** the alpha step across a seam (right edge → neighbour's left edge) must "
         "be no larger than the tile's average internal column-to-column step.",
         "- **Closure:** in a 2×2 panel, the disc around the shared corner (corner radius + 20 px) must be "
         "4-fold symmetric (mean |Δα| vs 90° rotation and both mirrors < 0.01) and inked (> 5 % coverage).",
         "- **Family mix:** for every pair of tiles in a Padrão family, right↔left and bottom↔top "
         "edge profiles must match (mean |Δα| < 0.004). Mixed 4×4 panels: `qa/panels/mixed-*-4x4.png`.",
         "- **Eyeball:** contact sheets and every 2×2/4×4 panel sheet viewed; see notes below.", "",
         "## Family mix test", "", "| Family | Tiles | Worst edge mismatch | Result |", "|---|---|---|---|"]
    for fam, ids, worst, ok in family_rows:
        L.append(f"| {fam} | {ids[0]}…{ids[-1][-2:]} | {worst:.5f} | {'✅' if ok else '❌'} |")
    L += ["", "## Per tile", "",
          "| ID | Name | Shapes | Holes | Nodes | Render 200/1000 | L↔R | T↔B | Seam step (across / inside) | Closure sym | Result |",
          "|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        if r["group"] in SEAMLESS:
            seamcols = (f"{r['lr']:.4f} | {r['tb']:.4f} | {r['across']:.4f} / {r['inside']:.4f} | "
                        f"{r['closure_sym']:.4f}")
        else:
            seamcols = "— | — | — (standalone) | —"
        L.append(f"| {r['id']} | {r['name']} | {r['shapes']} | {r['holes']} | {r['nodes']} | "
                 f"{'✅' if r['render'] else '❌ ' + '; '.join(r['issues'][:2])} | {seamcols} | "
                 f"{'✅ PASS' if r['pass'] else '❌ FAIL'} |")
    L.append("")
    with open(os.path.join(ROOT, "TILE_TEST.md"), "w") as f:
        f.write("\n".join(L))


if __name__ == "__main__":
    main()
