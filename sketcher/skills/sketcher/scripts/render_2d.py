#!/usr/bin/env python3
"""
render_2d.py — turn a Sketcher plan JSON into a to-scale 2D floor-plan SVG.

Design contract (see references/schema.md):
  - Plan units are METERS. Floor is the XZ plane, Y is up. Points are [x, z].
  - We draw in MILLIMETRES so the SVG viewBox equals real bounds; a viewer
    scaling the SVG to fit a container never distorts the geometry.
  - North points UP: we map world z -> page y by (maxZ - z). The "one Y flip"
    from the design is done arithmetically here rather than via an SVG
    transform, purely so <text> labels stay upright (a flipped <g> renders
    text upside-down — the classic trap).
  - Strokes use vector-effect="non-scaling-stroke" so a 1.5px wall line stays
    1.5px crisp no matter how the browser scales the viewBox to fit.

Usage:
  python render_2d.py plan.json > plan.svg
  python render_2d.py plan.json -o plan.svg
"""
import json, sys, math, argparse

MM = 1000.0            # meters -> millimetres
MARGIN = 500.0         # mm of whitespace around the bounds

# ---- projection ----------------------------------------------------------

class Proj:
    """World mm (x right, z up) -> page mm (x right, y down, north up)."""
    def __init__(self, minx, maxx, minz, maxz):
        self.vx = minx - MARGIN
        self.top = maxz + MARGIN          # world z that maps to page y = 0
        self.w = (maxx - minx) + 2 * MARGIN
        self.h = (maxz - minz) + 2 * MARGIN
    def pt(self, x, z):                    # x,z already in mm
        return (x - self.vx, self.top - z)

def bounds(plan):
    xs, zs = [], []
    for w in plan.get("walls", []):
        for p in (w["a"], w["b"]):
            xs.append(p[0]); zs.append(p[1])
    for r in plan.get("rooms", []):
        for p in r["polygon"]:
            xs.append(p[0]); zs.append(p[1])
    if not xs:                             # no walls/rooms: fall back to furniture
        for f in plan.get("furniture", []):
            xs.append(f["pos"][0]); zs.append(f["pos"][1])
    if not xs:
        xs, zs = [0, 5], [0, 5]
    return min(xs)*MM, max(xs)*MM, min(zs)*MM, max(zs)*MM

# ---- small SVG helpers ---------------------------------------------------

def esc(s): return str(s).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")

def poly(pts, fill, stroke="none", sw=0, opacity=1.0, extra=""):
    d = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    s = f'<polygon points="{d}" fill="{fill}"'
    if stroke != "none":
        s += f' stroke="{stroke}" stroke-width="{sw}" vector-effect="non-scaling-stroke"'
    if opacity != 1.0: s += f' fill-opacity="{opacity}"'
    if extra: s += " " + extra
    return s + "/>"

def line(p1, p2, stroke, sw, dash=None, cap="butt"):
    s = (f'<line x1="{p1[0]:.1f}" y1="{p1[1]:.1f}" x2="{p2[0]:.1f}" y2="{p2[1]:.1f}" '
         f'stroke="{stroke}" stroke-width="{sw}" stroke-linecap="{cap}" '
         f'vector-effect="non-scaling-stroke"')
    if dash: s += f' stroke-dasharray="{dash}"'
    return s + "/>"

def circle(c, r, fill="none", stroke="#222", sw=1.2):
    return (f'<circle cx="{c[0]:.1f}" cy="{c[1]:.1f}" r="{r:.1f}" fill="{fill}" '
            f'stroke="{stroke}" stroke-width="{sw}" vector-effect="non-scaling-stroke"/>')

def text(p, s, size=110, anchor="middle", fill="#333", weight="normal"):
    return (f'<text x="{p[0]:.1f}" y="{p[1]:.1f}" font-size="{size}" '
            f'font-family="Helvetica,Arial,sans-serif" fill="{fill}" '
            f'font-weight="{weight}" text-anchor="{anchor}" '
            f'dominant-baseline="middle">{esc(s)}</text>')

def arc(cx, cy, r, a0, a1, stroke, sw, dash=None):
    """Arc in page space; a0,a1 in radians (page angles)."""
    x0, y0 = cx + r*math.cos(a0), cy + r*math.sin(a0)
    x1, y1 = cx + r*math.cos(a1), cy + r*math.sin(a1)
    large = 1 if abs(a1 - a0) > math.pi else 0
    sweep = 1 if a1 > a0 else 0
    s = (f'<path d="M {x0:.1f} {y0:.1f} A {r:.1f} {r:.1f} 0 {large} {sweep} '
         f'{x1:.1f} {y1:.1f}" fill="none" stroke="{stroke}" stroke-width="{sw}" '
         f'vector-effect="non-scaling-stroke"')
    if dash: s += f' stroke-dasharray="{dash}"'
    return s + "/>"

# ---- geometry ------------------------------------------------------------

def wall_quad(a, b, thick):
    """Poché rectangle for a wall a->b (mm) with thickness (mm)."""
    dx, dz = b[0]-a[0], b[1]-a[1]
    L = math.hypot(dx, dz) or 1.0
    nx, nz = -dz/L*thick/2, dx/L*thick/2      # perpendicular offset
    return [(a[0]+nx, a[1]+nz), (b[0]+nx, b[1]+nz),
            (b[0]-nx, b[1]-nz), (a[0]-nx, a[1]-nz)]

def lerp(a, b, t): return (a[0]+(b[0]-a[0])*t, a[1]+(b[1]-a[1])*t)

# ---- furniture symbol library -------------------------------------------
# Each symbol is a function(hw, hd) -> list of primitives in LOCAL mm
# (centred at origin, +x right, +z up). Primitives:
#   ("rect", x0,z0,x1,z1) | ("circle", cx,cz,r) | ("line", x0,z0,x1,z1)
# They are rotated in world, then projected. Unknown types -> labelled box.

def _rect(hw, hd): return [("rect", -hw, -hd, hw, hd)]
def sym_table_round(hw, hd): return [("circle", 0, 0, min(hw, hd))]
def sym_chair(hw, hd): return [("rect",-hw,-hd,hw,hd), ("rect",-hw,hd*0.5,hw,hd)]
def sym_sofa(hw, hd): return [("rect",-hw,-hd,hw,hd), ("rect",-hw,hd*0.4,hw,hd),
                              ("line",-hw,-hd,-hw,hd), ("line",hw,-hd,hw,hd)]
def sym_bed(hw, hd): return [("rect",-hw,-hd,hw,hd), ("rect",-hw,hd*0.55,hw,hd),
                             ("rect",-hw*0.7,hd*0.6,-hw*0.15,hd*0.95),
                             ("rect",hw*0.15,hd*0.6,hw*0.7,hd*0.95)]
def sym_desk(hw, hd): return [("rect",-hw,-hd,hw,hd), ("line",-hw,hd*0.4,hw,hd*0.4)]
def sym_counter(hw, hd): return [("rect",-hw,-hd,hw,hd)]
def sym_range(hw, hd): return [("rect",-hw,-hd,hw,hd),
                               ("circle",-hw*0.45,hd*0.45,min(hw,hd)*0.3),
                               ("circle",hw*0.45,hd*0.45,min(hw,hd)*0.3),
                               ("circle",-hw*0.45,-hd*0.45,min(hw,hd)*0.3),
                               ("circle",hw*0.45,-hd*0.45,min(hw,hd)*0.3)]
def sym_sink(hw, hd): return [("rect",-hw,-hd,hw,hd),
                             ("rect",-hw*0.6,-hd*0.6,hw*0.6,hd*0.6)]
def sym_fridge(hw, hd): return [("rect",-hw,-hd,hw,hd), ("line",-hw,hd*0.1,hw,hd*0.1)]
def sym_toilet(hw, hd): return [("rect",-hw*0.6,-hd,hw*0.6,-hd*0.3),
                                ("circle",0,hd*0.3,min(hw,hd)*0.7)]
def sym_treadmill(hw, hd): return [("rect",-hw,-hd,hw,hd),
                                   ("rect",-hw,hd*0.35,hw,hd),
                                   ("line",-hw,-hd,hw,-hd)]
def sym_bench(hw, hd): return [("rect",-hw*0.35,-hd,hw*0.35,hd),
                               ("line",-hw,hd,-hw,-hd),("line",hw,hd,hw,-hd)]
def sym_rack(hw, hd): return [("rect",-hw,-hd,hw,hd),("line",-hw,0,hw,0)]
def sym_planter(hw, hd): return [("circle",0,0,min(hw,hd)), ("circle",0,0,min(hw,hd)*0.6)]
def sym_column(hw, hd): return [("rect", -hw, -hd, hw, hd)]   # solid steel column
def sym_car(hw, hd): return [("rect",-hw,-hd,hw,hd),                 # body
                             ("rect",-hw*0.82,-hd*0.1,hw*0.82,hd*0.5),  # cabin
                             ("line",-hw*0.82,-hd*0.1,hw*0.82,-hd*0.1),  # windshield
                             ("line",-hw*0.82,hd*0.5,hw*0.82,hd*0.5)]    # rear glass

SYMBOLS = {
    "table_round": sym_table_round, "table_rect": _rect, "chair": sym_chair,
    "sofa": sym_sofa, "bed": sym_bed, "desk": sym_desk, "counter": sym_counter,
    "range": sym_range, "sink": sym_sink, "fridge": sym_fridge, "toilet": sym_toilet,
    "treadmill": sym_treadmill, "bench_press": sym_bench, "rack": sym_rack,
    "planter": sym_planter, "column": sym_column, "car": sym_car,
}

# per-type fill/stroke overrides (else white box with grey line).
# A furniture item may also carry its own "color" to override the fill.
FSTYLE = {
    "column": {"fill": "#2b2b2b", "stroke": "#000000"},
    "car":    {"fill": "#cf7b52", "stroke": "#5f3320"},
}

def draw_furniture(f, P):
    w, d = f["size"][0]*MM, f["size"][1]*MM
    hw, hd = w/2, d/2
    cx, cz = f["pos"][0]*MM, f["pos"][1]*MM
    rot = math.radians(f.get("rot", 0))
    cs, sn = math.cos(rot), math.sin(rot)
    def world(lx, lz):                     # local -> world (rotate CCW, translate)
        return (cx + lx*cs - lz*sn, cz + lx*sn + lz*cs)
    prims = SYMBOLS.get(f["type"], _rect)(hw, hd)
    st = FSTYLE.get(f["type"], {})
    fill = f.get("color", st.get("fill", "#ffffff"))
    stroke = st.get("stroke", "#5b6b7a")
    out = []
    for pr in prims:
        if pr[0] == "rect":
            x0, z0, x1, z1 = pr[1:]
            corners = [world(x0,z0), world(x1,z0), world(x1,z1), world(x0,z1)]
            out.append(poly([P.pt(*c) for c in corners], fill, stroke, 1.2))
        elif pr[0] == "circle":
            out.append(circle(P.pt(*world(pr[1], pr[2])), pr[3], fill, stroke, 1.2))
        elif pr[0] == "line":
            out.append(line(P.pt(*world(pr[1], pr[2])), P.pt(*world(pr[3], pr[4])),
                            stroke, 1.0))
    if f["type"] not in SYMBOLS:            # label the fallback box
        out.append(text(P.pt(cx, cz), f["type"], size=90, fill="#5b6b7a"))
    return "".join(out)

# ---- openings ------------------------------------------------------------

def draw_door(dr, walls, P):
    w = walls.get(dr["wall"])
    if not w: return ""
    a = (w["a"][0]*MM, w["a"][1]*MM); b = (w["b"][0]*MM, w["b"][1]*MM)
    width = dr["width"]*MM; thick = w.get("thickness", 0.115)*MM
    dx, dz = b[0]-a[0], b[1]-a[1]; L = math.hypot(dx,dz) or 1
    ux, uz = dx/L, dz/L                     # along wall
    nx, nz = -uz, ux                        # perpendicular
    c = lerp(a, b, dr["t"])
    p0 = (c[0]-ux*width/2, c[1]-uz*width/2)
    p1 = (c[0]+ux*width/2, c[1]+uz*width/2)
    out = []
    # cut the wall: white rectangle over the opening
    cut = [(p0[0]+nx*thick/2, p0[1]+nz*thick/2), (p1[0]+nx*thick/2, p1[1]+nz*thick/2),
           (p1[0]-nx*thick/2, p1[1]-nz*thick/2), (p0[0]-nx*thick/2, p0[1]-nz*thick/2)]
    out.append(poly([P.pt(*c2) for c2 in cut], "#ffffff"))
    swing = dr.get("swing", "in")
    if swing == "slide":
        out.append(line(P.pt(*p0), P.pt(*p1), "#333", 2.5))
        return "".join(out)
    hinge = p0 if dr.get("hinge","a") == "a" else p1
    leaf_end_dir = -1 if hinge == p1 else 1
    side = 1 if swing in ("in","left") else -1
    # leaf: from hinge, width long, perpendicular into the room
    leaf = (hinge[0]+nx*side*width, hinge[1]+nz*side*width)
    out.append(line(P.pt(*hinge), P.pt(*leaf), "#333", 2.0))
    # swing arc from door plane to leaf
    hp = P.pt(*hinge)
    a_open = math.atan2(P.pt(*leaf)[1]-hp[1], P.pt(*leaf)[0]-hp[0])
    other = (hinge[0]+ux*leaf_end_dir*width, hinge[1]+uz*leaf_end_dir*width)
    a_closed = math.atan2(P.pt(*other)[1]-hp[1], P.pt(*other)[0]-hp[0])
    a0, a1 = sorted([a_closed, a_open])
    out.append(arc(hp[0], hp[1], width, a0, a1, "#9aa7b3", 1.0, dash="60,40"))
    return "".join(out)

def draw_window(win, walls, P):
    w = walls.get(win["wall"])
    if not w: return ""
    a = (w["a"][0]*MM, w["a"][1]*MM); b = (w["b"][0]*MM, w["b"][1]*MM)
    width = win["width"]*MM; thick = w.get("thickness", 0.23)*MM
    vthick = max(thick, 0.24*MM)            # emphasise thin storefront glazing
    dx, dz = b[0]-a[0], b[1]-a[1]; L = math.hypot(dx,dz) or 1
    ux, uz = dx/L, dz/L; nx, nz = -uz, ux
    c = lerp(a, b, win["t"])
    p0 = (c[0]-ux*width/2, c[1]-uz*width/2); p1 = (c[0]+ux*width/2, c[1]+uz*width/2)
    cut = [(p0[0]+nx*vthick/2, p0[1]+nz*vthick/2), (p1[0]+nx*vthick/2, p1[1]+nz*vthick/2),
           (p1[0]-nx*vthick/2, p1[1]-nz*vthick/2), (p0[0]-nx*vthick/2, p0[1]-nz*vthick/2)]
    out = [poly([P.pt(*c2) for c2 in cut], "#8fd6ee", opacity=0.95)]  # glass fill
    for s in (0.5, -0.5):                   # frame lines each face
        q0 = (p0[0]+nx*vthick*s, p0[1]+nz*vthick*s); q1 = (p1[0]+nx*vthick*s, p1[1]+nz*vthick*s)
        out.append(line(P.pt(*q0), P.pt(*q1), "#1789b5", 2.2))
    if win["width"] >= 2.0:                  # mullions for shopfront glazing
        n = max(2, int(round(win["width"] / 1.5)))
        for i in range(1, n):
            m = lerp(p0, p1, i / n)
            m0 = (m[0]+nx*vthick/2, m[1]+nz*vthick/2)
            m1 = (m[0]-nx*vthick/2, m[1]-nz*vthick/2)
            out.append(line(P.pt(*m0), P.pt(*m1), "#2f9ec4", 1.1))
    return "".join(out)

# ---- annotations: scale bar + north arrow --------------------------------

def scale_bar(P):
    # 1 m bar in the lower-left of the page
    x0 = P.vx + MARGIN*0.6 - P.vx          # page x for world x = vx+... simplified:
    px = MARGIN*0.5; py = P.h - MARGIN*0.45
    out = [line((px, py), (px+MM, py), "#333", 2.0)]
    for i in range(6):
        xx = px + i*MM/5
        out.append(line((xx, py-30), (xx, py+30), "#333", 1.5))
    out.append(text((px+MM/2, py-90), "1 metre", size=95, fill="#333"))
    return "".join(out)

def north_arrow(P):
    cx, cy = P.w - MARGIN*0.5, MARGIN*0.6
    pts = [(cx, cy-260), (cx-120, cy+140), (cx, cy+60), (cx+120, cy+140)]
    return (poly(pts, "#333") +
            text((cx, cy-360), "N", size=140, fill="#333", weight="bold"))

# ---- top-level render ----------------------------------------------------

def render(plan):
    minx, maxx, minz, maxz = bounds(plan)
    P = Proj(minx, maxx, minz, maxz)
    walls = {w["id"]: w for w in plan.get("walls", [])}
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {P.w:.0f} {P.h:.0f}" '
             f'width="100%" style="max-width:1100px;background:#fafaf7;font-family:Helvetica,Arial,sans-serif">']
    # rooms (floor fills, drawn first / underneath)
    for r in plan.get("rooms", []):
        pts = [P.pt(p[0]*MM, p[1]*MM) for p in r["polygon"]]
        parts.append(poly(pts, r.get("floor_color", "#f0ebe1"),
                          r.get("stroke_color", "#c9bfa8"), 1.4,
                          r.get("opacity", 1.0)))
        # centroid label + area
        cx = sum(p[0] for p in pts)/len(pts); cy = sum(p[1] for p in pts)/len(pts)
        area = abs(sum(r["polygon"][i][0]*r["polygon"][(i+1)%len(r["polygon"])][1]
                       - r["polygon"][(i+1)%len(r["polygon"])][0]*r["polygon"][i][1]
                       for i in range(len(r["polygon"]))))/2
        parts.append(text((cx, cy-70), r.get("name",""), size=130, fill="#6b5d48", weight="bold"))
        parts.append(text((cx, cy+90), f"{area:.1f} m²", size=100, fill="#8a7c66"))
        if r.get("road_centerline"):        # dashed lane divider down the long axis
            xs = [p[0]*MM for p in r["polygon"]]; zs = [p[1]*MM for p in r["polygon"]]
            x0, x1 = min(xs), max(xs); z0, z1 = min(zs), max(zs)
            if (z1 - z0) >= (x1 - x0):
                xm = (x0 + x1) / 2
                parts.append(line(P.pt(xm, z0+400), P.pt(xm, z1-400), "#f4e6a8", 3.0, dash="260,200"))
            else:
                zm = (z0 + z1) / 2
                parts.append(line(P.pt(x0+400, zm), P.pt(x1-400, zm), "#f4e6a8", 3.0, dash="260,200"))
    # walls: thin (<=0.08 m) walls are storefront glazing -> tinted glass band;
    # everything thicker is solid masonry poché.
    for w in plan.get("walls", []):
        a = (w["a"][0]*MM, w["a"][1]*MM); b = (w["b"][0]*MM, w["b"][1]*MM)
        th = w.get("thickness", 0.115)
        if th <= 0.08:
            q = wall_quad(a, b, max(th, 0.22)*MM)   # widen visually so glass reads
            parts.append(poly([P.pt(*c) for c in q], "#8fd6ee", "#1789b5", 2.2, 0.95))
        else:
            q = wall_quad(a, b, th*MM)
            sw = 1.6 if w.get("exterior") else 1.0
            parts.append(poly([P.pt(*c) for c in q], "#2b2b2b", "#000", sw))
    # openings
    for dr in plan.get("doors", []): parts.append(draw_door(dr, walls, P))
    for win in plan.get("windows", []): parts.append(draw_window(win, walls, P))
    # furniture
    for f in plan.get("furniture", []): parts.append(draw_furniture(f, P))
    # annotations
    parts.append(scale_bar(P)); parts.append(north_arrow(P))
    name = plan.get("meta", {}).get("name", "")
    if name:
        parts.append(text((MARGIN*0.5, MARGIN*0.35), name, size=150,
                          anchor="start", fill="#333", weight="bold"))
    parts.append('</svg>')
    return "\n".join(parts)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("plan")
    ap.add_argument("-o", "--out")
    a = ap.parse_args()
    with open(a.plan) as fh: plan = json.load(fh)
    svg = render(plan)
    if a.out:
        with open(a.out, "w") as fh: fh.write(svg)
        print(f"wrote {a.out} ({len(svg)} bytes)")
    else:
        sys.stdout.write(svg)

if __name__ == "__main__":
    main()
