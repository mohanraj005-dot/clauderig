# Sketcher Plan Schema (v1)

Every Sketcher drawing — 2D now, isometric / 3D / render-prompt later — reads from **one JSON file**. Get this right and every render lane is just a projection of the same data. The schema is deliberately small; resist adding keys until a lane actually needs them.

## Coordinate system (read this first)

- **Units are meters.** Always. A 4.2 m wall is `4.2`, never `4200` and never `14` (feet). If a user gives feet, convert on the way in and note it.
- **The floor is the XZ plane. Y is up.** `x` runs left→right, `z` runs "north"→"south" across the floor, `y` is height off the floor. 2D plans only use x/z; y exists so the 3D lane bolts on later without a schema migration.
- A point on the floor is `[x, z]`. A size is `[width, depth, height]` = `[Δx, Δz, Δy]`.
- Angles are **degrees, counter-clockwise**, 0° = furniture facing +x.

Why XZ-floor / Y-up instead of the more intuitive XY-floor? Because the 3D lane (Three.js) uses Y-up by convention, and having the 2D and 3D lanes share coordinates verbatim is worth one moment of "wait, z is the floor axis." The 2D renderer flips z so north points up on the page — you never think about it.

## Top-level shape

```json
{
  "meta": { "name": "...", "units": "m", "jurisdiction": "IN-NBC-2016", "occupancy": "assembly" },
  "walls": [ ... ],
  "rooms": [ ... ],
  "doors": [ ... ],
  "windows": [ ... ],
  "furniture": [ ... ]
}
```

`meta.jurisdiction` drives which clearance table the linter uses: `IN-NBC-2016` (India) or `US-ADA-IBC`. `meta.occupancy` (`assembly` | `business` | `mercantile` | `residential`) selects egress factors. Both default sensibly if omitted, but the linter is only as honest as these two fields.

## walls

The skeleton. Everything else references walls or sits inside the boundary they form.

```json
{ "id": "w1", "a": [0, 0], "b": [6.0, 0], "height": 3.0, "thickness": 0.23, "exterior": true }
```

- `a`, `b` — endpoints on the floor, `[x, z]`. A wall is a 2-point segment; L-shapes are multiple walls sharing an endpoint.
- `thickness` — meters. Indian brick exterior ≈ 0.23, interior partition ≈ 0.115. This drives the poché (the filled black wall body in plan).
- `exterior` — windows may only sit on `exterior: true` walls; the renderer draws exterior walls heavier.
- `height` — for the 3D lane; ignored in 2D.

Walls are drawn as filled polygons (poché), not center-lines, so `thickness` is load-bearing information, not decoration.

## rooms

Polygons that get a floor fill and a label. Rooms are **descriptive** — they don't have to perfectly tile the walls; they exist to color-code zones and anchor labels/area calcs.

```json
{ "id": "r1", "name": "Dining", "use": "dining", "polygon": [[0,0],[6,0],[6,4],[0,4]], "floor_color": "#f4ece0" }
```

- `polygon` — ordered `[x,z]` vertices, implicitly closed.
- `use` — free-ish text but prefer the linter's known vocabulary: `dining`, `kitchen`, `gym`, `coworking`, `circulation`, `toilet`, `storage`, `entry`. The linter maps `use` → clearance rules.
- Area is computed (shoelace), not stored — never let a stored area drift from the polygon.

## doors

```json
{ "id": "d1", "wall": "w3", "t": 0.5, "width": 1.0, "swing": "in", "hinge": "a" }
```

- `wall` — the wall id this door sits in.
- `t` — position along the wall as a fraction `0..1` from `a` to `b`. So the door's center is `lerp(a, b, t)`. Using a fraction (not an absolute point) means doors ride along if a wall moves.
- `width` — clear opening, meters. **1.0 is the NBC single-door minimum for assembly** — the linter flags anything narrower.
- `swing` — `in` | `out` | `left` | `right` | `slide`. `in`/`out` swing perpendicular to the wall; `hinge` (`a` or `b`) picks which end the arc pivots on.
- The renderer draws the leaf + a swing arc showing the clearance zone that must stay empty.

## windows

Same wall-anchoring as doors, but **exterior walls only** (the linter enforces this).

```json
{ "id": "win1", "wall": "w1", "t": 0.35, "width": 1.5, "sill": 0.9, "head": 2.1 }
```

- `sill` / `head` — heights off the floor (meters), for the 3D lane. 2D ignores them.

## furniture

```json
{ "id": "f1", "type": "table_round", "pos": [3.0, 2.0], "size": [1.2, 1.2, 0.75], "rot": 0 }
```

- `type` — selects the plan symbol. Known types render as real symbols; unknown types fall back to a labeled rectangle (never fails). Current library: `table_round`, `table_rect`, `chair`, `sofa`, `bed`, `desk`, `counter`, `range` (cooktop), `sink`, `fridge`, `toilet`, `treadmill`, `bench_press`, `rack`, `planter`. Extend the library in `scripts/render_2d.py` (`SYMBOLS`) — don't invent schema keys for it.
- `pos` — center point `[x, z]`.
- `size` — `[w, d, h]` in meters. `h` is for 3D.
- `rot` — degrees CCW about the center.

## Design rule for future lanes

When you add the isometric, Three.js, or render-prompt lane, **do not change this schema** — read it and project it. If a lane genuinely needs new data (e.g. material for photoreal prompts), add an **optional** key with a safe default so old plans still render. The whole point of one schema is that a plan authored today still renders in every lane you build tomorrow.
