# Space-Planning Standards & Clearances

Concrete numbers so Sketcher gives credible, code-aware layouts instead of vibes. These are **sanity-check thresholds, not a stamp of code compliance** — always tell the user a licensed architect signs off the real drawing. Values gathered for the two jurisdictions Sketcher supports; the linter reads `meta.jurisdiction` to pick.

> Disclaimer to surface in output: *"Clearance checks are planning heuristics, not a building-code certification. A licensed architect / structural engineer must approve the final drawing before construction."*

## India — NBC 2016 (default for Indian F&B/assembly spaces)

National Building Code of India 2016, Part 4 (Fire & Life Safety). Restaurants and gyms are **assembly occupancy** — the strict end of egress rules.

| Item | Threshold | Note |
|------|-----------|------|
| Single exit door, min width | **1.0 m** | Below this = flag. Assembly minimum. |
| Corridor / passage, min width | **1.5 m** | |
| Stair width — assembly/institutional | **1.5 m** | Residential can go to 1.0 m |
| Exit capacity factor | **75 persons per metre** of exit width | Drives how many/what width of exits an occupant load needs |
| Dead-end corridor limit | **6 m** sprinklered / **3 m** non-sprinklered | Beyond → a second exit is required |
| Assembly occupant load | check Part 4 tables by use | Restaurants load heavily — dining ≈ 1 person / 1.0–1.5 m² |

Rule of thumb the linter applies: occupant load ÷ 75 = total exit width in metres required; compare to the sum of door widths on exterior walls.

## USA — ADA 2010 + IBC (use when jurisdiction = US-ADA-IBC)

| Item | Threshold | Source |
|------|-----------|--------|
| Wheelchair turning circle | **1525 mm (60 in)** diameter, or T-shape equivalent | ADA §304 |
| Clear door opening | **815 mm (32 in)** at 90° open | ADA §404 / IBC §1010 egress min |
| Accessible route width | **915 mm (36 in)** continuous, may pinch to 815 mm for ≤610 mm | ADA |
| Door maneuvering clearance | **1525 mm (60 in)** | lets a wheelchair user turn while pulling the door |

The 32-in egress minimum exists because two people cannot pass simultaneously through a 30-in opening during an evacuation — it's an evacuation-throughput number, not an accessibility one.

## Program clearances (jurisdiction-independent ergonomics)

These aren't code — they're what makes a space *work*. The linter warns, it doesn't block.

### Restaurant / F&B
- **15–20 sq ft per cover** (1.4–1.9 m²) for the dining area — fine dining trends higher, fast-casual lower.
- Main aisles (server + patron traffic): **44–48 in (1.1–1.2 m)**.
- Between occupied chair backs: **~600 mm** so people can pass.

### Kitchen (work triangle)
- Each leg of sink ↔ cooktop ↔ fridge: **4–9 ft (1.2–2.7 m)**; total perimeter **< 26 ft (7.9 m)**.
- Specific legs: sink→oven 4–7 ft, sink→fridge 4–6 ft, oven→fridge 4–7 ft.
- Single-cook work aisle: **min 42 in (1.07 m)**; two cooks want 48 in.

### Gym / fitness
- **6 ft (1.83 m)** between patrons on cardio / free-weight / weight machines.
- Treadmill: **2 ft (0.6 m)** each side, **6 ft (1.83 m)** clear behind (run-off / fall zone).

### Coworking
- **75–95 sq ft/person** traditional; **~75 sq ft/workstation** typical coworking; **100–125 sq ft** per private desk; **80–200 sq ft/person** once you blend open + private + amenity.
- Circulation between desk rows: aim ≥ **900 mm**.

## The 8-step space-planning method

When a user hands you a brief or dimensions, walk this — it's how a designer actually thinks, and it keeps Sketcher from just dropping furniture into a box:

1. **Program** — list every activity and how many people/covers/desks. Quantify before you draw.
2. **Zone** — group by adjacency & noise: loud/service near entry & back-of-house, quiet/private deep. Bubble-diagram in your head first.
3. **Standards** — pull the per-person area and clearances above for each zone; multiply out the minimum area. Reality-check against the actual footprint *now*, before placing a single wall.
4. **Focal point** — every room needs one anchor (bar, feature wall, reception). Orient furniture toward it.
5. **Lighting layers** — note ambient + task + accent per zone (informs later 3D/render lanes; in 2D, annotate intent).
6. **Ergonomics** — place furniture, then verify aisles/triangle/turning-circle against step 3. Iterate.
7. **Code check** — run the linter; resolve egress-width and door-width flags before anything else.
8. **Render** — emit the 2D SVG (+ later lanes). Include scale bar, north arrow, and the disclaimer.

Do steps 1–3 in prose *with the user* before writing JSON — a plan built on an unquantified program is where bad layouts come from.
