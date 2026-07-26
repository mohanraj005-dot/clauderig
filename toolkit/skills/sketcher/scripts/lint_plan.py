#!/usr/bin/env python3
"""
lint_plan.py — sanity-check a Sketcher plan against clearance & code heuristics.

This is NOT a code-compliance certifier — it's a fast "does this layout make
sense" pass so Sketcher catches obvious problems (a 0.7 m exit door, furniture
buried in a wall, a room no door reaches) before showing a drawing. See
references/standards.md for the numbers and their sources.

Exit code 0 = no ERRORs (warnings allowed); 1 = at least one ERROR.

Usage: python lint_plan.py plan.json
"""
import json, sys, math, argparse
from collections import defaultdict

def load(p):
    with open(p) as f: return json.load(f)

# clearance tables keyed by jurisdiction
DOORMIN = {"IN-NBC-2016": 1.0, "US-ADA-IBC": 0.815}     # metres, single exit/door
CORRIDOR_MIN = {"IN-NBC-2016": 1.5, "US-ADA-IBC": 0.915}
EGRESS_FACTOR = 75.0                                     # persons per metre (NBC)
# rough per-person area (m²) by room use -> occupant load estimate
LOAD_AREA = {"dining": 1.4, "assembly": 0.65, "gym": 4.6, "coworking": 7.0,
             "kitchen": 9.3, "circulation": 0, "toilet": 0, "storage": 0, "entry": 0}

def polygon_area(poly):
    n = len(poly)
    return abs(sum(poly[i][0]*poly[(i+1)%n][1] - poly[(i+1)%n][0]*poly[i][1]
                   for i in range(n)))/2

def furniture_corners(f):
    w, d = f["size"][0]/2, f["size"][1]/2
    cx, cz = f["pos"]; rot = math.radians(f.get("rot", 0))
    cs, sn = math.cos(rot), math.sin(rot)
    out = []
    for lx, lz in [(-w,-d),(w,-d),(w,d),(-w,d)]:
        out.append((cx+lx*cs-lz*sn, cz+lx*sn+lz*cs))
    return out

def aabb(corners):
    xs=[c[0] for c in corners]; zs=[c[1] for c in corners]
    return min(xs),min(zs),max(xs),max(zs)

def aabb_overlap(a, b, tol=0.02):
    return not (a[2]<=b[0]+tol or b[2]<=a[0]+tol or a[3]<=b[1]+tol or b[3]<=a[1]+tol)

def seg_point_dist(px, pz, a, b):
    ax,az=a; bx,bz=b; dx,dz=bx-ax,bz-az
    L2=dx*dx+dz*dz
    if L2==0: return math.hypot(px-ax,pz-az)
    t=max(0,min(1,((px-ax)*dx+(pz-az)*dz)/L2))
    return math.hypot(px-(ax+t*dx), pz-(az+t*dz))

def lint(plan):
    issues=[]   # (level, code, msg)
    def err(c,m): issues.append(("ERROR",c,m))
    def warn(c,m): issues.append(("WARN",c,m))
    def info(c,m): issues.append(("INFO",c,m))

    juris = plan.get("meta",{}).get("jurisdiction","IN-NBC-2016")
    dmin = DOORMIN.get(juris, 1.0)
    walls = {w["id"]: w for w in plan.get("walls",[])}

    # 1. door widths + windows-on-exterior-only
    # Exit doors (on exterior walls) must meet the egress minimum. Interior
    # doors only need a usable clear passage — holding them to the exit width
    # would false-flag every toilet/store door, so they get a softer 0.8 m rule.
    INTERIOR_MIN = 0.8
    ext_doors_width = 0.0
    for d in plan.get("doors",[]):
        if d["wall"] not in walls:
            err("door.orphan", f"door {d.get('id','?')} references missing wall {d['wall']}")
            continue
        is_exit = walls[d["wall"]].get("exterior")
        if is_exit:
            ext_doors_width += d["width"]
            if d["width"] < dmin - 1e-6:
                err("door.width", f"exit door {d.get('id','?')} is {d['width']} m — below {juris} egress minimum {dmin} m")
        elif d["width"] < INTERIOR_MIN - 1e-6:
            warn("door.width", f"interior door {d.get('id','?')} is {d['width']} m — under {INTERIOR_MIN} m usable clear width")
    for wdw in plan.get("windows",[]):
        w = walls.get(wdw["wall"])
        if not w:
            err("window.orphan", f"window {wdw.get('id','?')} references missing wall {wdw['wall']}")
        elif not w.get("exterior"):
            err("window.interior", f"window {wdw.get('id','?')} is on interior wall {wdw['wall']} — windows go on exterior walls only")

    # 2. egress capacity: occupant load / 75 <= exterior door width
    total_load = 0.0
    for r in plan.get("rooms",[]):
        per = LOAD_AREA.get(r.get("use",""), None)
        if per and per>0:
            total_load += polygon_area(r["polygon"]) / per
    if total_load>0:
        need = total_load/EGRESS_FACTOR
        if ext_doors_width < need - 1e-6:
            warn("egress.capacity",
                 f"~{total_load:.0f} occupants need ≥{need:.2f} m of exit-door width; "
                 f"plan has {ext_doors_width:.2f} m on exterior walls")
        else:
            info("egress.capacity",
                 f"~{total_load:.0f} occupants, {ext_doors_width:.2f} m exit width (need {need:.2f} m) — ok")

    # 3. connectivity: every room polygon should have a door within reach of an edge
    if plan.get("rooms") and plan.get("doors"):
        door_pts=[]
        for d in plan.get("doors",[]):
            w=walls.get(d["wall"])
            if not w: continue
            a,b=w["a"],w["b"]; t=d["t"]
            door_pts.append((a[0]+(b[0]-a[0])*t, a[1]+(b[1]-a[1])*t))
        for r in plan.get("rooms",[]):
            if r.get("use") in ("circulation","entry"): continue
            poly=r["polygon"]; n=len(poly); reachable=False
            for dp in door_pts:
                for i in range(n):
                    if seg_point_dist(dp[0],dp[1],poly[i],poly[(i+1)%n])<0.35:
                        reachable=True; break
                if reachable: break
            if not reachable:
                warn("connectivity", f"room '{r.get('name',r.get('id'))}' has no door on/near its boundary — is it reachable?")

    # 4. furniture overlaps (each other) and furniture buried in walls
    furns=plan.get("furniture",[])
    boxes=[(f, aabb(furniture_corners(f))) for f in furns]
    for i in range(len(boxes)):
        for j in range(i+1,len(boxes)):
            if aabb_overlap(boxes[i][1],boxes[j][1]):
                warn("furniture.overlap",
                     f"'{boxes[i][0].get('id','?')}' and '{boxes[j][0].get('id','?')}' overlap")
    for f,_ in boxes:
        cx,cz=f["pos"]
        for w in plan.get("walls",[]):
            d=seg_point_dist(cx,cz,w["a"],w["b"])
            if d < w.get("thickness",0.115)/2 + 0.05:
                warn("furniture.in_wall",
                     f"'{f.get('id','?')}' centre sits inside/against wall {w['id']}")
                break

    # 5. program-clearance spot checks (kitchen triangle, gym spacing)
    kitchen_key = {"sink":None,"range":None,"fridge":None}
    for f in furns:
        if f["type"] in kitchen_key and kitchen_key[f["type"]] is None:
            kitchen_key[f["type"]]=f["pos"]
    if all(kitchen_key.values()):
        legs=[("sink","range"),("range","fridge"),("sink","fridge")]
        perim=0
        for x,y in legs:
            dxz=math.hypot(kitchen_key[x][0]-kitchen_key[y][0], kitchen_key[x][1]-kitchen_key[y][1])
            perim+=dxz
            if dxz>2.7: warn("kitchen.triangle", f"{x}↔{y} is {dxz:.1f} m (>2.7 m ideal max)")
        if perim>7.9: warn("kitchen.triangle", f"work-triangle perimeter {perim:.1f} m (>7.9 m ideal max)")
        info("kitchen.triangle", f"work-triangle perimeter {perim:.1f} m")

    return issues

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("plan"); a=ap.parse_args()
    issues=lint(load(a.plan))
    order={"ERROR":0,"WARN":1,"INFO":2}
    issues.sort(key=lambda x:order[x[0]])
    icons={"ERROR":"🔴","WARN":"⚠ ","INFO":"✅"}
    if not issues:
        print("✅ no issues found"); sys.exit(0)
    for lvl,code,msg in issues:
        print(f"{icons[lvl]} [{code}] {msg}")
    errs=sum(1 for i in issues if i[0]=="ERROR")
    print(f"\n{errs} error(s), {sum(1 for i in issues if i[0]=='WARN')} warning(s)")
    sys.exit(1 if errs else 0)

if __name__=="__main__":
    main()
