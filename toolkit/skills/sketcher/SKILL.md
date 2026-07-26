---
name: sketcher
description: >-
  Turn room dimensions, a napkin brief, or "help me lay out this space" into an
  accurate, to-scale 2D floor plan (SVG) with real furniture, doors, windows,
  and clearance/code sanity checks. Use this whenever the user wants to design,
  sketch, plan, lay out, or visualize a physical space — a restaurant, cafe,
  kitchen, gym, coworking floor, office, shop, apartment, or any room — even if
  they don't say "floor plan": phrases like "how should I arrange", "where
  should the tables go", "draw my space", "plan the layout", "is this big
  enough", "will it fit", "design the interior", or giving raw dimensions of a
  room all trigger it. Also use to sanity-check an existing layout against
  accessibility and egress clearances (ADA/IBC or India NBC 2016). Produces a
  JSON plan + rendered SVG you can open in a browser. NOT for pixel-photoreal
  renders (it writes the prompt for an image AI to do that) and NOT for CAD/DWG
  output.
---

# Sketcher

Sketcher turns a spatial brief into a **to-scale, code-aware 2D floor plan**. It exists because a layperson describing a space ("15 by 10 metre shell, I want a 40-cover restaurant with an open kitchen") can't picture whether it fits, flows, or meets exit rules — Sketcher makes that concrete and drawable.

The engine is **schema-first**: everything flows through one JSON plan (`references/schema.md`). Read that file before authoring a plan — the coordinate convention (meters, floor on XZ, Y up, north-up rendering) is the one thing that trips people up. Get the JSON right and rendering is a single script call.

## What you can do today (Phase 1)

- **Author a plan** as JSON matching the schema.
- **Render it to 2D SVG** — poché walls, real furniture symbols, door swing arcs, windows, room labels with computed areas, a 1-metre scale bar, and a north arrow.
- **Lint it** against ADA/IBC or India NBC 2016 clearances — exit-door width, egress capacity, room connectivity, furniture overlaps/wall-collisions, and the kitchen work-triangle.
- **Load the example-cafe preset** (`assets/presets/example-cafe.json`) as a starting point for a small F&B space.

Isometric 2.5D, interactive Three.js 3D, and photoreal render-prompt lanes are **planned but not built yet** — the schema already reserves what they need (wall `height`, furniture `size[2]`, window `sill`/`head`), so they bolt on without breaking existing plans. If the user asks for 3D today, say the 3D lane is a later phase and offer the accurate 2D plan now.

## The workflow

Don't jump straight to JSON. A good plan comes from thinking like a designer first — walk the **8-step space-planning method** in `references/standards.md`. In practice:

1. **Quantify the program with the user in prose** — how many covers/desks/people, what activities, what's the real footprint. Pull per-person areas and clearances from `references/standards.md` and reality-check that the program even fits *before* drawing. This is the highest-leverage step; skipping it is how bad layouts happen.
2. **Author the JSON plan** per `references/schema.md`. Start walls (the shell), then rooms (zones), then doors/windows, then furniture. For a small F&B space, copy `assets/presets/example-cafe.json` and edit.
3. **Lint it**: `python3 scripts/lint_plan.py plan.json`. Resolve every 🔴 ERROR (they're egress/reference problems). ⚠ WARNings are judgment calls — surface them to the user, don't silently "fix" a spread-out kitchen if the user has a reason.
4. **Render it**: `python3 scripts/render_2d.py plan.json -o plan.svg`. Then actually show it — open in a browser or screenshot it — so the user sees the space. Don't just hand over a JSON file.
5. **Iterate** on the user's reaction. It's their space; they drive.

## Running the tools

```bash
# lint (exit 0 = no errors; prints ERROR/WARN/INFO with sources)
python3 scripts/lint_plan.py plan.json

# render to SVG
python3 scripts/render_2d.py plan.json -o plan.svg
```

Both are stdlib-only Python 3 — no pip installs. Paths are relative to the skill directory; use absolute paths when running from elsewhere.

## Authoring tips that avoid the common traps

- **Meters, always.** If the user talks in feet, convert on the way in and tell them you did. A plan in feet renders 3.3× too small.
- **Walls are the skeleton.** Doors and windows anchor to a wall by `id` and a fraction `t` along it, so they ride along if you move the wall. Windows only go on `exterior: true` walls — the linter enforces it.
- **`use` on rooms drives the linter.** Prefer the known vocabulary (`dining`, `kitchen`, `gym`, `coworking`, `circulation`, `toilet`, `storage`, `entry`) so occupant-load and clearance checks fire correctly.
- **Unknown furniture types don't crash** — they render as a labeled box. But adding a real symbol to `SYMBOLS` in `scripts/render_2d.py` is cheap and makes plans read far better.
- **Always emit the disclaimer**: clearance checks are planning heuristics, not a building-code certification — a licensed architect must approve the real drawing. Say this whenever you present a plan, especially for assembly-occupancy spaces like restaurants and cafes.

## Reference files

- `references/schema.md` — the plan JSON contract. **Read before authoring.**
- `references/standards.md` — clearance numbers (ADA/IBC + India NBC 2016), per-person areas, and the 8-step space-planning method.
- `assets/presets/example-cafe.json` — small cafe starter preset (~60 sq m; built to be re-measured and edited for a real space).
