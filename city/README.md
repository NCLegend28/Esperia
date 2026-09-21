# Esperia city — prototype base (v8, 2026-09-21)

`esperia-city.html` is the visual base for the city interface. Self-contained: three.js r128 from cdnjs, everything else inline. Open in a browser; no build step.

## What it establishes

- **Block 0** — one board is one city block. 13×13 lots, zoned in rings from the centre: City Hall → residential → commerce → industrial → ports on all four edges. Block 0 stays the capital when a new block docks to a port.
- **Board as geology** — traces are streets, vias at intersections, pads under lots, ring roads brighter at zone seams, gold edge connectors are ports.
- **Seven inspectable buildings** (`BUILDINGS`) with divisions mapped to floors: City Hall, Research, Library, Quant Desk, Evaluation Lab, Editorial House, Ops & Reliability.
- **48 agents** (`agents`) with stable identity: name, designator, role, building/division/desk, per-run model, calls/tools/jobs/blocked. They live in the residential ring and commute to their building when a job dispatches.
- **Three views**: city → building (floor-stack cutaway) → floor (separate scene: pixel-art top-down room on the left, stats/project/roster/log on the right) → agent (stats) from any level.

## Seams for the next steps

| Replace this | To get |
| --- | --- |
| `layoutFloor(b, f)` → tile grid + furniture list | Architect-agent room shapes and layouts |
| `PROJECTS`, agent stats, `TOOLLINES`, the dispatch timer | Real data from `tool-calls.sqlite`, the job journal, review verdicts |
| `genResidential / genCommerce / genIndustrial` | Hand-authored block library |
| `BUILDINGS[].env` (one rectangle) | Non-rectangular footprints |

Everything in the right-hand data column already has a real source in the CLI; the generator is shaped like the ledger on purpose. Traffic, jobs and stats in this file are simulated — the header says so.

Debug hook: `window.__esperia` exposes `selectBuilding`, `selectFloor`, `selectAgent`, `back`, `dispatch`, `buildings`, `agents`, `state()`.
