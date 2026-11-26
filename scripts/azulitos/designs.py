"""The 72 Azulitos designs, built from the motif grammar (AGENT_INSTRUCTIONS §3).

Padrão construction: compose one quarter (0..500 x 0..500, top-left), clip it to
the quarter, then mirror across x=500 and y=500 to complete the tile.

  corner (0,0)        -> large motif; four tiles' corners merge into one medallion
  centre (500,500)    -> small motif (opposite corner of the quarter)
  (500,0) and (0,500) -> edge-midpoint motifs that knit neighbouring tiles
  the diagonal        -> lace band (renda) linking corner and centre

Motifs are laid in priority order; each later motif is cut back from the earlier
ones by a white reserve gap, the way painted tiles keep their figures apart.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from shapely.geometry import box
from shapely.ops import unary_union

from . import motifs as M

SIZE = 1000
HALF = SIZE / 2
GAP = 11  # white reserve between figures, px at 1000

AZUL = "#1E4FA3"
AMARELO = "#E3A008"
VERDE = "#3E7C4F"
MANGANES = "#7A4E7E"
PALETTE = {"azul": AZUL, "amarelo": AMARELO, "verde": VERDE, "manganes": MANGANES}


@dataclass
class Tile:
    id: str
    name: str
    group: str  # Padrão | Medalhão | Polícromo
    motifs: list[str]
    layers: dict[str, object] = field(default_factory=dict)  # colour key -> geometry


class Composer:
    """Lay figures in priority order, cutting each from what is already laid."""

    def __init__(self):
        self.items: list[tuple[str, object]] = []
        self._all = None

    def add(self, g, colour="azul", gap=GAP):
        if g is None or g.is_empty:
            return
        if self._all is not None:
            g = g.difference(self._all.buffer(gap, quad_segs=8))
        g = g.buffer(0)
        # drop fragments the reserve cut leaves behind: specks and slivers
        parts = [p for p in M.as_polys(g) if p.area >= 80 and not p.buffer(-1.6).is_empty]
        if not parts:
            return
        g = unary_union(parts)
        self.items.append((colour, g))
        self._all = g if self._all is None else unary_union([self._all, g])

    def layers(self):
        out: dict[str, list] = {}
        for c, g in self.items:
            out.setdefault(c, []).append(g)
        return {c: unary_union(gs) for c, gs in out.items()}


def mirror_quarter(g):
    """Clip to the top-left quarter and mirror into a full, seamless tile."""
    q = g.intersection(box(0, 0, HALF, HALF))
    parts = [q, M.mirror_x(q, HALF), M.mirror_y(q, HALF), M.mirror_y(M.mirror_x(q, HALF), HALF)]
    full = unary_union([p.buffer(0.01, quad_segs=2) for p in parts]).buffer(-0.01, quad_segs=2)
    return full.intersection(box(0, 0, SIZE, SIZE))


# --------------------------------------------------------------------------
# Motif constructors keyed by name — each returns geometry centred at (cx,cy)
# --------------------------------------------------------------------------

def big_motif(kind, cx, cy, r, a=0.0):
    """Large D4-symmetric medallion motifs (corners and Medalhão centres)."""
    if kind == "Estrela":
        return M.estrela(cx, cy, r, w=24, a=a)
    if kind == "Roseta":
        return M.roseta(cx, cy, r, k=8, a=a)
    if kind == "Quadrifólio":
        return M.quadrifolio(cx, cy, r, w=24, a=a)
    if kind == "Sol":
        return M.sol(cx, cy, r, k=16, a=a)
    if kind == "Flor":
        return M.flor(cx, cy, r, k=8, a=a)
    if kind == "Cruz":
        return unary_union([M.cruz(cx, cy, r, a=a),
                            *[M.circle(*M.polar(cx, cy, r * 0.78, a + 45 + 90 * i), r * 0.1) for i in range(4)]])
    if kind == "Leque":
        return unary_union([M.leque(cx, cy, r, a=a + 45 + 90 * i, sweep=90, k=5) for i in range(4)]
                           + [M.ring(cx, cy, r * 0.12, 9)])
    if kind == "Losango":
        return unary_union([M.losango(cx, cy, r, w=24, a=a),
                            *[M.circle(*M.polar(cx, cy, r * 0.62, a + 45 + 90 * i), r * 0.1) for i in range(4)]])
    if kind == "Espiral":
        return unary_union([M.espiral(*M.polar(cx, cy, r * 0.55, a + 90 * i), r * 0.42, a=a + 90 * i + 180, w=15)
                            for i in range(4)] + [M.quadrifolio(cx, cy, r * 0.32, w=12, a=a, solid=True)])
    raise KeyError(kind)


def small_motif(kind, cx, cy, r, a=0.0):
    """Small D4-symmetric motifs for the tile centre."""
    if kind == "Coração":
        return unary_union([M.coracao(*M.polar(cx, cy, r * 0.5, a + 45 + 90 * i), r * 0.7, a + 45 + 90 * i + 180)
                            for i in range(4)] + [M.circle(cx, cy, r * 0.14)])
    if kind == "Folha":
        leaves = [M.folha(*M.polar(cx, cy, r * 0.15, a + 90 * i), r * 0.85, a + 90 * i) for i in range(4)]
        small = [M.folha(*M.polar(cx, cy, r * 0.2, a + 45 + 90 * i), r * 0.5, a + 45 + 90 * i) for i in range(4)]
        return unary_union(leaves + small + [M.circle(cx, cy, r * 0.12)])
    if kind == "Flor":
        return M.flor(cx, cy, r, k=8, a=a, gap=7)
    if kind == "Roseta":
        return M.roseta(cx, cy, r, k=8, a=a, gap=7)
    if kind == "Estrela":
        return M.estrela(cx, cy, r, w=17, a=a)
    if kind == "Quadrifólio":
        return M.quadrifolio(cx, cy, r, w=17, a=a)
    if kind == "Losango":
        return M.losango(cx, cy, r, w=17, a=a)
    if kind == "Cruz":
        return M.cruz(cx, cy, r, a=a, w=14)
    raise KeyError(kind)


def edge_motif(kind, cx, cy, r, horizontal):
    """D2 motifs sitting on an edge midpoint (half in this tile, half in the next)."""
    a = 0 if horizontal else 90
    if kind == "flor4":
        return M.flor(cx, cy, r, k=4, a=a + 45, gap=6)
    if kind == "losango":
        return M.losango(cx, cy, r, w=14, a=a)
    if kind == "estrela":
        return M.star_poly(cx, cy, 8, r, r * 0.55, 0).difference(M.circle(cx, cy, r * 0.22))
    if kind == "meialua2":  # two crescents back to back across the edge
        return unary_union([M.meia_lua(*M.polar(cx, cy, r * 0.45, a + 90), r * 0.55, a + 90),
                            M.meia_lua(*M.polar(cx, cy, r * 0.45, a - 90), r * 0.55, a - 90)])
    if kind == "ponto":
        return unary_union([M.ring(cx, cy, r * 0.7, 14), M.circle(cx, cy, r * 0.3)])
    if kind == "quadrifolio":
        return M.quadrifolio(cx, cy, r, w=9, a=0, solid=True)
    raise KeyError(kind)


def mid_motif(kind, cx, cy, r, a):
    """Free motifs on the diagonal (no symmetry required; mirroring pairs them)."""
    if kind == "Cata-Vento":
        return M.cata_vento(cx, cy, r, k=4, a=a)
    if kind == "Trevo":
        return M.trevo(cx, cy, r, a=a)
    if kind == "Espiral":
        return M.espiral(cx, cy, r, a=a, w=12)
    if kind == "Pinha":
        return M.pinha(*M.polar(cx, cy, -r, a), 2 * r, a=a)
    if kind == "Meia-Lua":
        return M.meia_lua(cx, cy, r, a=a)
    if kind == "Concha":
        return M.concha(*M.polar(cx, cy, -r * 0.4, a), r, a=a)
    if kind == "Coração":
        return M.coracao(cx, cy, r * 1.3, a=a)
    if kind == "Folha":
        return unary_union([M.folha(cx, cy, r * 1.1, a=a - 35), M.folha(cx, cy, r * 1.1, a=a + 35),
                            M.circle(cx, cy, r * 0.16)])
    raise KeyError(kind)


def flank_motif(kind, cx, cy, a):
    """Small sprigs for the open fields of the quarter."""
    if kind == "trevo":
        return M.trevo(cx, cy, 44, a=a)
    if kind == "folhas":
        return unary_union([M.folha(cx, cy, 62, a=a - 30), M.folha(cx, cy, 62, a=a + 30), M.circle(cx, cy, 9)])
    if kind == "coracao":
        return M.coracao(cx, cy, 52, a=a + 180)
    if kind == "gota":
        return unary_union([M.vesica(*M.polar(cx, cy, -30, a), 72, 34, a), M.circle(*M.polar(cx, cy, -44, a), 9)])
    if kind == "ponto":
        return unary_union([M.circle(cx, cy, 15)] + [M.circle(*M.polar(cx, cy, 32, a + 90 * i), 8) for i in range(4)])
    raise KeyError(kind)


# --------------------------------------------------------------------------
# Padrão / Polícromo builder
# --------------------------------------------------------------------------

@dataclass
class PadraoSpec:
    corner: str
    centre: str
    band: str  # circulos | duplos | losangos | contas | onda | motivo
    mid: str
    edge: str
    frame: str  # nenhum | anel | arco | ambos
    rc: float = 270
    rm: float = 150
    re: float = 86
    flank: str = "trevo"
    colours: dict = field(default_factory=dict)  # role -> palette key (Polícromo only)


def build_padrao(s: PadraoSpec):
    col = lambda role: s.colours.get(role, "azul")
    comp = Composer()
    diag = 45  # pointing from corner (0,0) toward the centre (500,500)

    comp.add(small_motif(s.centre, HALF, HALF, s.rm), col("centre"))
    comp.add(big_motif(s.corner, 0, 0, s.rc), col("corner"))
    comp.add(edge_motif(s.edge, HALF, 0, s.re, True), col("edge"))
    comp.add(edge_motif(s.edge, 0, HALF, s.re, False), col("edge"))

    # frame lines: a ring closing round the corner medallion, and/or arcs that
    # sweep from edge motif to edge motif around the tile centre
    if s.frame in ("anel", "ambos"):
        comp.add(M.ring(0, 0, s.rc + 34, 18), col("frame"))
    if s.frame in ("arco", "ambos"):
        comp.add(M.ring(HALF, HALF, HALF - s.re * 0.1, 17), col("frame"))

    # the diagonal band between corner medallion and centre motif
    start = (s.rc + 24) / math.sqrt(2)
    end = HALF - (s.rm + 16) / math.sqrt(2)
    p0, p1 = (start, start), (end, end)
    span = math.hypot(end - start, end - start)
    midp = ((start + end) / 2, (start + end) / 2)
    if s.band == "motivo":
        comp.add(mid_motif(s.mid, *midp, min(78, span * 0.36), diag), col("mid"))
        # side sprigs reaching toward the edge motifs
        comp.add(M.strip([M.polar(*midp, span * 0.36, diag), p1], 16), col("band"))
        comp.add(M.strip([M.polar(*midp, -span * 0.36, diag), p0], 16), col("band"))
    elif s.band == "onda":
        comp.add(mid_motif(s.mid, *midp, min(60, span * 0.26), diag), col("mid"))
        comp.add(M.onda(p0, p1, 22, 16, waves=2), col("band"))
    else:
        size = {"circulos": 30, "duplos": 34, "losangos": 30, "contas": 26}[s.band]
        comp.add(M.renda(p0, p1, s.band, size, w=15), col("band"))

    # flank sprigs in the open fields either side of the diagonal, pointing at
    # the edge motifs (a diagonal-mirror pair, so the quarter stays balanced)
    for (fx, fy), ang in (((HALF * 0.74, HALF * 0.26), -45), ((HALF * 0.26, HALF * 0.74), 135)):
        comp.add(flank_motif(s.flank, fx, fy, ang), col("edge"))

    layers = {}
    for c, g in comp.layers().items():
        layers[c] = M.clean(mirror_quarter(g))
    return layers


# --------------------------------------------------------------------------
# Medalhão builder
# --------------------------------------------------------------------------

@dataclass
class MedalhaoSpec:
    medallion: str
    border: str  # anel | concha


def build_medalhao(s: MedalhaoSpec):
    comp = Composer()
    c = HALF
    comp.add(big_motif(s.medallion, c, c, 232))
    comp.add(M.ring(c, c, 268, 14))
    beads = unary_union([M.circle(*M.polar(c, c, 302, i * 360 / 24), 9.5) for i in range(24)])
    comp.add(beads)
    if s.border == "anel":
        comp.add(M.ring(c, c, 352, 18))
        comp.add(M.ring(c, c, 384, 9))
        for i in range(4):  # corner fans
            cx, cy = (0 if i in (0, 3) else SIZE), (0 if i < 2 else SIZE)
            ang = math.degrees(math.atan2(c - cy, c - cx))
            comp.add(M.leque(cx, cy, 150, a=ang, sweep=90, k=5))
    else:
        lobes = unary_union([M.circle(*M.polar(c, c, 372, i * 360 / 20), 34) for i in range(20)])
        scallop = M.outline(unary_union([lobes, M.circle(c, c, 372)]), 15)
        comp.add(scallop)
        for i in range(4):  # corner sprigs pointing into the corners
            cx, cy = (95 if i in (0, 3) else SIZE - 95), (95 if i < 2 else SIZE - 95)
            ang = math.degrees(math.atan2(cy - c, cx - c))
            comp.add(M.trevo(cx, cy, 62, a=ang))
            comp.add(M.folha(*M.polar(cx, cy, 30, ang + 180), 70, ang + 180 + 50))
            comp.add(M.folha(*M.polar(cx, cy, 30, ang + 180), 70, ang + 180 - 50))
    g = comp.layers()["azul"].intersection(box(0, 0, SIZE, SIZE))
    return {"azul": M.clean(g)}


# --------------------------------------------------------------------------
# The catalogue (deterministic — no randomness)
# --------------------------------------------------------------------------

CORNERS = ["Estrela", "Roseta", "Quadrifólio", "Sol", "Flor", "Cruz", "Leque", "Losango"]
CENTRES = ["Quadrifólio", "Flor", "Losango", "Coração", "Folha", "Estrela", "Cruz", "Roseta"]
BANDS = ["circulos", "motivo", "duplos", "onda", "losangos", "contas"]
MIDS = ["Cata-Vento", "Trevo", "Espiral", "Pinha", "Meia-Lua", "Concha", "Coração", "Folha"]
EDGES = ["flor4", "losango", "estrela", "meialua2", "ponto", "quadrifolio"]
FRAMES = ["anel", "nenhum", "arco", "ambos"]
FLANKS = ["trevo", "folhas", "coracao", "gota", "ponto"]
BAND_NAMES = {"circulos": "Renda", "duplos": "Renda", "losangos": "Losango", "contas": "Renda",
              "onda": "Onda", "motivo": None}
EDGE_NAMES = {"flor4": "Flor", "losango": "Losango", "estrela": "Estrela", "meialua2": "Meia-Lua",
              "ponto": "Roseta", "quadrifolio": "Quadrifólio"}


# Families: the six tiles sharing a corner motif also share every element that
# crosses the tile edge (corner radius, edge motif, frame), so their edge
# profiles are identical and any of them can be mixed in one seamless panel.
FAMILIES = {
    # corner: (edge motif, frame, corner radius)
    "Estrela": ("flor4", "anel", 270),
    "Roseta": ("losango", "arco", 262),
    "Quadrifólio": ("estrela", "ambos", 256),
    "Sol": ("meialua2", "nenhum", 285),
    "Flor": ("ponto", "anel", 264),
    "Cruz": ("quadrifolio", "arco", 270),
    "Leque": ("flor4", "ambos", 276),
    "Losango": ("estrela", "anel", 262),
}


def _padrao_specs():
    specs = []
    for ci, corner in enumerate(CORNERS):
        edge, frame, rc = FAMILIES[corner]
        centres = [c for c in CENTRES[ci:] + CENTRES[:ci] if c != corner][:6]
        for j, centre in enumerate(centres):
            n = ci * 6 + j
            specs.append(PadraoSpec(
                corner=corner, centre=centre,
                band=BANDS[(j + ci) % len(BANDS)],
                mid=MIDS[(n * 3) % len(MIDS)],
                edge=edge, frame=frame, rc=rc,
                rm=[150, 140, 162][(n + ci) % 3],
                flank=FLANKS[(n * 5 + ci) % len(FLANKS)],
            ))
    return specs


POLI = [
    # corner, centre, band, mid, edge, frame, colours by role
    ("Roseta", "Estrela", "motivo", "Folha", "flor4", "anel",
     {"corner": "amarelo", "centre": "manganes", "edge": "verde", "mid": "verde"}),
    ("Estrela", "Flor", "circulos", "Trevo", "quadrifolio", "ambos",
     {"corner": "amarelo", "centre": "verde", "edge": "manganes"}),
    ("Flor", "Quadrifólio", "onda", "Coração", "ponto", "arco",
     {"corner": "amarelo", "centre": "manganes", "mid": "manganes", "edge": "verde"}),
    ("Sol", "Cruz", "motivo", "Pinha", "losango", "anel",
     {"corner": "amarelo", "centre": "verde", "mid": "verde", "edge": "manganes"}),
    ("Quadrifólio", "Roseta", "duplos", "Espiral", "estrela", "nenhum",
     {"corner": "verde", "centre": "amarelo", "edge": "manganes", "band": "azul"}),
    ("Leque", "Folha", "motivo", "Concha", "meialua2", "arco",
     {"corner": "amarelo", "centre": "verde", "mid": "manganes", "edge": "amarelo"}),
    ("Cruz", "Coração", "losangos", "Cata-Vento", "flor4", "ambos",
     {"corner": "manganes", "centre": "amarelo", "edge": "verde"}),
    ("Losango", "Flor", "motivo", "Cata-Vento", "quadrifolio", "anel",
     {"corner": "verde", "centre": "amarelo", "mid": "manganes", "edge": "amarelo"}),
]

MEDALLIONS = ["Estrela", "Roseta", "Quadrifólio", "Sol", "Flor", "Cruz", "Leque", "Espiral"]


def catalogue():
    """Return [(Tile-without-geometry, builder-callable)] for all 72 tiles."""
    out = []
    n = 1
    for s in _padrao_specs():
        name = f"{s.corner} e {s.centre}"
        motifs = [s.corner, s.centre, EDGE_NAMES[s.edge]]
        if s.band in ("motivo", "onda"):
            motifs.append(s.mid)
        if BAND_NAMES[s.band]:
            motifs.append(BAND_NAMES[s.band])
        t = Tile(f"AZL-{n:02d}", name, "Padrão", list(dict.fromkeys(motifs)))
        out.append((t, (lambda s=s: build_padrao(s)), s))
        n += 1
    for border in ("anel", "concha"):
        for med in MEDALLIONS:
            s = MedalhaoSpec(med, border)
            name = f"{med} em {'Anel' if border == 'anel' else 'Concha'}"
            motifs = [med, "Renda", "Leque" if border == "anel" else "Concha"]
            if border == "concha":
                motifs += ["Trevo", "Folha"]
            t = Tile(f"AZL-{n:02d}", name, "Medalhão", list(dict.fromkeys(motifs)))
            out.append((t, (lambda s=s: build_medalhao(s)), s))
            n += 1
    for corner, centre, band, mid, edge, frame, colours in POLI:
        s = PadraoSpec(corner, centre, band, mid, edge, frame, colours=colours)
        name = f"{corner} Lisboeta"
        motifs = [corner, centre, EDGE_NAMES[edge]] + ([mid] if band in ("motivo", "onda") else [])
        if BAND_NAMES[band]:
            motifs.append(BAND_NAMES[band])
        t = Tile(f"AZL-{n:02d}", name, "Polícromo", list(dict.fromkeys(motifs)))
        out.append((t, (lambda s=s: build_padrao(s)), s))
        n += 1
    assert n == 73
    names = [t.name for t, _, _ in out]
    assert len(set(names)) == 72, "tile names must be unique"
    return out
