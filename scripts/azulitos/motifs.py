"""Motif bank for Azulitos.

Every motif is a function returning a shapely geometry (filled area, the
"painted" part of the tile) in tile coordinates: 1000x1000 artboard, y down.
Nothing here is traced from a historical panel or an existing set — each shape
is built from circles, polygons and buffered curves (DECISION_LOG D9).

Conventions
- (cx, cy): motif centre.  r: overall radius.  a: rotation in degrees.
- Lines are never strokes: a "line" is a LineString buffered into a filled
  strip (AGENT_INSTRUCTIONS §2).
"""
from __future__ import annotations

import math

from shapely import affinity
from shapely.geometry import LineString, MultiPolygon, Point, Polygon, box
from shapely.ops import unary_union

# Max deviation (px at 1000) between a true arc and its polygon approximation.
SAGITTA = 0.12


def _segs(r: float) -> int:
    """quad_segs for a circle of radius r so the chord error stays <= SAGITTA."""
    if r <= SAGITTA * 2:
        return 2
    theta = 2 * math.acos(1 - SAGITTA / r)
    n = math.ceil((2 * math.pi / theta) / 4)
    return max(3, min(n, 64))


def circle(cx, cy, r):
    return Point(cx, cy).buffer(r, quad_segs=_segs(r))


def ring(cx, cy, r, w):
    return circle(cx, cy, r + w / 2).difference(circle(cx, cy, max(r - w / 2, 0.01)))


def strip(points, w, cap="round"):
    """A thin filled shape following a polyline (our substitute for a stroke)."""
    style = {"round": 1, "flat": 2, "square": 3}[cap]
    return LineString(points).buffer(w / 2, quad_segs=_segs(w / 2), cap_style=style, join_style=1)


def rot(g, a, cx, cy):
    return affinity.rotate(g, a, origin=(cx, cy))


def polar(cx, cy, r, deg):
    t = math.radians(deg)
    return cx + r * math.cos(t), cy + r * math.sin(t)


def mirror_x(g, x0):
    return affinity.scale(g, xfact=-1, yfact=1, origin=(x0, 0))


def mirror_y(g, y0):
    return affinity.scale(g, xfact=1, yfact=-1, origin=(0, y0))


# --------------------------------------------------------------------------
# Elementary shapes
# --------------------------------------------------------------------------

def star_poly(cx, cy, n, ro, ri, a=0.0):
    pts = []
    for i in range(2 * n):
        r = ro if i % 2 == 0 else ri
        pts.append(polar(cx, cy, r, a - 90 + i * 180 / n))
    return Polygon(pts)


def vesica(cx, cy, length, width, a=0.0):
    """Pointed petal / leaf: lens from two circles, base at (cx,cy), tip along angle a."""
    # lens of length L and width W from two arcs
    L, W = length, width
    R = (L * L / 4 + W * W / 4) / W  # radius of each arc
    d = R - W / 2  # centre offset from axis
    c1 = circle(cx + L / 2, cy - d, R)
    c2 = circle(cx + L / 2, cy + d, R)
    lens = c1.intersection(c2)
    return rot(lens, a, cx, cy)


def ellipse(cx, cy, rx, ry, a=0.0):
    e = affinity.scale(Point(0, 0).buffer(1, quad_segs=_segs(max(rx, ry))), rx, ry, origin=(0, 0))
    e = affinity.translate(e, cx, cy)
    return rot(e, a, cx, cy)


def diamond(cx, cy, rx, ry, a=0.0):
    return rot(Polygon([(cx, cy - ry), (cx + rx, cy), (cx, cy + ry), (cx - rx, cy)]), a, cx, cy)


def outline(g, w):
    """Keep only a band of width w inside the boundary of g (an outlined motif)."""
    inner = g.buffer(-w, quad_segs=8, join_style=1)
    return g.difference(inner)


# --------------------------------------------------------------------------
# Motif bank (AGENT_INSTRUCTIONS §3)
# --------------------------------------------------------------------------

def estrela(cx, cy, r, w=16, a=0.0, open_=True):
    """Eight-point star: outlined star with a solid inner star and a dot."""
    outer = star_poly(cx, cy, 8, r, r * 0.62, a)
    parts = [outline(outer, w) if open_ else outer]
    if open_:
        inner = star_poly(cx, cy, 8, r * 0.62, r * 0.40, a + 22.5)
        parts.append(inner.difference(circle(cx, cy, r * 0.2)))
        parts.append(circle(cx, cy, r * 0.11))
    return unary_union(parts)


def roseta(cx, cy, r, k=8, a=0.0, gap=12):
    """Rosette: k pointed petals around a ringed centre."""
    core = r * 0.26
    petals = [vesica(*polar(cx, cy, core + gap, a + i * 360 / k), r - core - gap,
                     (r - core) * math.tan(math.pi / k) * 0.9, a + i * 360 / k) for i in range(k)]
    inner = [vesica(*polar(cx, cy, core + gap + (r - core) * 0.35, a + 180 / k + i * 360 / k),
                    (r - core) * 0.45, (r - core) * 0.16, a + 180 / k + i * 360 / k) for i in range(k)]
    centre = ring(cx, cy, core * 0.72, core * 0.36)
    return unary_union(petals + inner + [centre, circle(cx, cy, core * 0.22)])


def quadrifolio(cx, cy, r, w=16, a=0.0, solid=False):
    """Quatrefoil: four lobes, outlined, with a small diamond heart."""
    d, rr = r * 0.42, r * 0.58
    lobes = unary_union([circle(*polar(cx, cy, d, a + 45 + 90 * i), rr) for i in range(4)])
    if solid:
        return lobes.difference(diamond(cx, cy, r * 0.18, r * 0.18, a))
    body = outline(lobes, w)
    heart = diamond(cx, cy, r * 0.34, r * 0.34, a + 45).difference(circle(cx, cy, r * 0.08))
    return unary_union([body, heart])


def trevo(cx, cy, r, a=0.0):
    """Trefoil sprig pointing along angle a, with a short stem."""
    lobes = [circle(*polar(cx, cy, r * 0.42, a + off), r * 0.38) for off in (-60, 0, 60)]
    stem = strip([polar(cx, cy, 0, a), polar(cx, cy, -r * 0.75, a)], r * 0.16)
    return unary_union(lobes + [stem]).difference(circle(cx, cy, r * 0.12))


def flor(cx, cy, r, k=6, a=0.0, gap=10):
    """Flower: k round petals around a disc, separated by white reserve."""
    centre = circle(cx, cy, r * 0.3)
    pr = r * 0.34
    petals = [circle(*polar(cx, cy, r - pr, a + i * 360 / k), pr) for i in range(k)]
    petals = unary_union(petals).difference(circle(cx, cy, r * 0.3 + gap))
    eyes = unary_union([circle(*polar(cx, cy, r - pr, a + i * 360 / k), pr * 0.28) for i in range(k)])
    return unary_union([petals.difference(eyes), centre.difference(circle(cx, cy, r * 0.12))])


def sol(cx, cy, r, k=16, a=0.0, gap=10):
    """Sun: disc ringed by alternating long and short rays."""
    disc = circle(cx, cy, r * 0.42)
    rays = []
    for i in range(k):
        t = a + i * 360 / k
        L = r if i % 2 == 0 else r * 0.78
        p0 = polar(cx, cy, r * 0.42 + gap, t - 360 / k * 0.33)
        p1 = polar(cx, cy, L, t)
        p2 = polar(cx, cy, r * 0.42 + gap, t + 360 / k * 0.33)
        rays.append(Polygon([p0, p1, p2]))
    face = disc.difference(ring(cx, cy, r * 0.28, 10))
    return unary_union(rays + [face])


def cruz(cx, cy, r, a=0.0, w=14):
    """Cross pattée: four flared arms with a hollow heart."""
    arms = []
    for i in range(4):
        t = a + 90 * i
        p0 = polar(cx, cy, r * 0.12, t - 30)
        p1 = polar(cx, cy, r, t - 17)
        p2 = polar(cx, cy, r * 0.86, t)
        p3 = polar(cx, cy, r, t + 17)
        p4 = polar(cx, cy, r * 0.12, t + 30)
        arms.append(Polygon([p0, p1, p2, p3, p4]))
    body = unary_union(arms + [circle(cx, cy, r * 0.22)])
    return body.difference(ring(cx, cy, r * 0.3, w * 0.8))


def losango(cx, cy, r, w=16, a=0.0):
    """Diamond: outlined rhombus with a solid diamond inside."""
    outer = diamond(cx, cy, r, r, a)
    return unary_union([outline(outer, w), diamond(cx, cy, r * 0.45, r * 0.45, a)])


def coracao(cx, cy, s, a=0.0):
    """Heart, point toward angle a."""
    l1 = circle(cx - s * 0.28, cy - s * 0.18, s * 0.3)
    l2 = circle(cx + s * 0.28, cy - s * 0.18, s * 0.3)
    tri = Polygon([(cx - s * 0.56, cy - s * 0.08), (cx + s * 0.56, cy - s * 0.08), (cx, cy + s * 0.62)])
    h = unary_union([l1, l2, tri])
    return rot(h, a - 90, cx, cy)


def folha(cx, cy, length, a=0.0, w=None):
    """Leaf with a reserved midrib."""
    width = length * 0.42 if w is None else w
    leaf = vesica(cx, cy, length, width, a)
    rib = strip([polar(cx, cy, length * 0.12, a), polar(cx, cy, length * 0.8, a)], max(4, length * 0.045))
    return leaf.difference(rib)


def meia_lua(cx, cy, r, a=0.0):
    """Half-moon (crescent) opening toward angle a."""
    return circle(cx, cy, r).difference(circle(*polar(cx, cy, r * 0.45, a), r * 0.85))


def concha(cx, cy, r, a=0.0, k=7):
    """Scallop shell: half fan with rounded lobes and reserved ribs, hinge at (cx,cy)."""
    half = circle(cx, cy, r).intersection(box(cx - r, cy - r, cx + r, cy))
    lobes = unary_union([circle(*polar(cx, cy, r * 0.92, 180 + (i + 0.5) * 180 / k), r * 0.18)
                         for i in range(k)])
    body = unary_union([half.intersection(circle(cx, cy, r * 0.92)), lobes.intersection(box(cx - 2 * r, cy - 2 * r, cx + 2 * r, cy))])
    ribs = unary_union([strip([polar(cx, cy, r * 0.22, 180 + i * 180 / k), polar(cx, cy, r * 1.2, 180 + i * 180 / k)],
                              max(4, r * 0.05)) for i in range(1, k)])
    hinge = circle(cx, cy, r * 0.2)
    g = body.difference(ribs).difference(hinge)
    return rot(g, a + 90, cx, cy)


def leque(cx, cy, r, a=0.0, sweep=90, k=5):
    """Fan: a sector of radius r split into blades, scalloped edge, hinge reserved."""
    blades = []
    for i in range(k):
        t0 = a - sweep / 2 + i * sweep / k
        t1 = t0 + sweep / k
        tm = (t0 + t1) / 2
        pts = [polar(cx, cy, r * 0.2, t0 + 2), polar(cx, cy, r * 0.2, t1 - 2)]
        pts += [polar(cx, cy, r * 0.88, t1 - 2.5), polar(cx, cy, r * 0.88, t0 + 2.5)]
        blade = Polygon([pts[0], pts[1], pts[2], pts[3]])
        tip = circle(*polar(cx, cy, r * 0.88, tm), r * 0.88 * math.sin(math.radians(sweep / k / 2)) * 0.85)
        blades.append(unary_union([blade, tip]).difference(circle(cx, cy, r * 0.2)))
    return unary_union(blades)


def pinha(cx, cy, length, a=0.0):
    """Pinecone: teardrop body with reserved chevron scales, tip toward angle a."""
    w = length * 0.5
    body = unary_union([ellipse(cx + length * 0.38, cy, length * 0.4, w / 2),
                        Polygon([(cx + length * 0.2, cy - w * 0.38), (cx + length, cy), (cx + length * 0.2, cy + w * 0.38)])])
    cuts = []
    for i in range(1, 5):
        x = cx + length * (0.12 + i * 0.16)
        cuts.append(strip([(x - length * 0.1, cy - w * 0.55), (x, cy), (x - length * 0.1, cy + w * 0.55)], max(4, length * 0.04), "flat"))
    return rot(body.difference(unary_union(cuts)), a, cx, cy)


def espiral(cx, cy, r, a=0.0, turns=1.6, w=14):
    """Spiral volute: a tapering buffered curve ending in a dot."""
    pts = []
    n = 120
    for i in range(n + 1):
        t = i / n
        ang = a + t * turns * 360
        rad = r * (1 - 0.82 * t)
        pts.append(polar(cx, cy, rad, ang))
    curl = strip(pts, w)
    end = circle(*pts[-1], w * 0.9)
    return unary_union([curl, end])


def cata_vento(cx, cy, r, k=4, a=0.0, gap=8):
    """Pinwheel: k curved blades turning one way, hub reserved."""
    blades = []
    for i in range(k):
        t = a + i * 360 / k
        c = polar(cx, cy, r * 0.5, t)
        disc = circle(*c, r * 0.5)
        half = rot(box(cx, cy - 2 * r, cx + 2 * r, cy), t, cx, cy)
        blades.append(disc.intersection(half))
    g = unary_union(blades)
    return g.difference(circle(cx, cy, r * 0.16)).union(circle(cx, cy, r * 0.08))


def onda(p0, p1, amp, w, waves=3):
    """Wave: a sinuous strip between p0 and p1."""
    (x0, y0), (x1, y1) = p0, p1
    L = math.hypot(x1 - x0, y1 - y0)
    ux, uy = (x1 - x0) / L, (y1 - y0) / L
    nx, ny = -uy, ux
    pts = []
    n = 160
    for i in range(n + 1):
        t = i / n
        off = amp * math.sin(t * waves * 2 * math.pi)
        pts.append((x0 + ux * L * t + nx * off, y0 + uy * L * t + ny * off))
    return strip(pts, w)


# --------------------------------------------------------------------------
# Lace bands (Renda) between two points
# --------------------------------------------------------------------------

def renda(p0, p1, kind, size, w=12, n=None):
    (x0, y0), (x1, y1) = p0, p1
    L = math.hypot(x1 - x0, y1 - y0)
    ang = math.degrees(math.atan2(y1 - y0, x1 - x0))
    if n is None:
        n = max(2, int(L // (size * 2.1)))
    step = L / n
    parts = []
    for i in range(n):
        t = (i + 0.5) / n
        cx, cy = x0 + (x1 - x0) * t, y0 + (y1 - y0) * t
        if kind == "circulos":
            parts.append(ring(cx, cy, size, w))
            parts.append(circle(cx, cy, size * 0.28))
        elif kind == "duplos":
            parts.append(ring(cx, cy, size, w))
            parts.append(ring(cx, cy, size * 0.5, w * 0.8))
        elif kind == "losangos":
            parts.append(outline(diamond(cx, cy, step * 0.5 - w * 0.4, size, ang), w * 0.85))
            parts.append(diamond(cx, cy, step * 0.17, size * 0.34, ang))
        elif kind == "contas":  # beads
            parts.append(circle(cx, cy, size * 0.55))
    if kind == "contas":
        parts.append(strip([p0, p1], w * 0.5))
    return unary_union(parts)


def clean(g, tol=0.1):
    """Normalise a geometry: drop specks, fix validity, simplify within tol px."""
    g = g.buffer(0)
    if g.is_empty:
        return g
    g = g.simplify(tol, preserve_topology=True)
    polys = [p for p in (g.geoms if hasattr(g, "geoms") else [g]) if isinstance(p, Polygon) and p.area > 12]
    out = []
    for p in polys:
        holes = [h for h in p.interiors if Polygon(h).area > 12]
        out.append(Polygon(p.exterior, holes))
    return unary_union(out) if out else Polygon()


def as_polys(g):
    if g.is_empty:
        return []
    if isinstance(g, Polygon):
        return [g]
    if isinstance(g, MultiPolygon):
        return list(g.geoms)
    return [p for p in getattr(g, "geoms", []) if isinstance(p, Polygon)]
