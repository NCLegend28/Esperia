# Esperia building grammar — v0.2

**A building is a kit of parts.** A building spec is a JSON document: a *palette* of named colour slots and an ordered list of *parts*. The city renderer (`city/esperia-city.html`, `genSpec`) turns a spec into geometry today with boxes; a MagicaVoxel kit executes the same spec part-by-part tomorrow. Architecture agents write specs. The owner reviews renders. An approved spec is the versioned city asset (functional-spec F-18).

Everything named in the city — City Hall, Research, Library, Quant Desk, Evaluation Lab, Editorial House, Ops — is already a spec in this folder. Read `u1.json` first; it uses the most parts.

## Units and frame

- Units are board units. A lot is **14 × 14**, with 4-unit streets between lots.
- `x`, `z` are offsets from the **lot centre**. `y` is height above the board (the plinth top is usually `1.2` or `0.6`).
- Parts are laid down in order. The **first non-plinth part** marks where the "hideable" building begins: everything from there on disappears in cutaway; the plinth stays.
- Keep total height under ~50 and footprint inside the lot. The renderer does not clip.

## Palette slots

Every colour in a spec is a slot name, resolved through the palette. This is what keeps a hundred agent-designed buildings looking like one city: agents choose *which slot*, the city decides *which colour*.

| Slot | Meaning | Convention |
| --- | --- | --- |
| `plinth` | the pad the building sits on | dark, `#1a1d28` |
| `structure` | primary mass | desaturated, per district (commerce blues/violets, industrial greens, civic slate) |
| `trim` | secondary mass, setbacks, roof plates | slightly off `structure` |
| `metal` | pylons, masts, spreaders | `#8f97a6` |
| `glass` | window colour when lit | white `#eef2ff`, cyan, or amber for civic/library |
| `neonA` / `neonB` | signage and edge light | cyan `#3fd8f0`, magenta `#ff5fd2`; amber `#ffb45c` and green `#7dffb0` are district accents |
| `gold` | contact fingers, seals | `#d8ad55` |
| `white` | beacons, the civic seal | `#eef2ff` |

A spec may add slots. Unknown slot → falls back to `structure`.

## Parts

| Type | Fields | What it makes |
| --- | --- | --- |
| `plinth` | `w d h [slot]` | The pad. Always first. Not hidden in cutaway. |
| `volume` | `x z y w d h slot [glass] [edges] [corner]` | A box. `glass` = `{slot, density, cw, ch, from}` window grid on all four faces. `edges` = neon strip around the top perimeter. `corner` = one vertical neon strip down the +x+z corner. |
| `fins` | `x z y axis count pitch t d h [wave] slot [alt] [glassOn glass]` | A row of thin slabs (heatsink). `wave` varies height per fin. `alt` alternates colour. `glassOn:"last"` puts windows on the outer fin. |
| `slabs` | `x z y count pitch w h t slot [foot] [glass]` | Parallel upright plates (DIMM/memory bank). `foot` adds a contact strip at the base. |
| `pylons` | `x z y spread size h slot [cap]` | Four corner posts at ±spread/2. `cap` lights the tops. |
| `strip` | `x z y axis len [t] slot` | A single neon bar. Two crossed strips make a seal. |
| `mast` | `x z y h [slot] [beacon beaconSize]` | A thin pole with a light on top. |
| `facade_lights` | `side y h count pitch slots[]` | Vertical neon fins along one façade (`n s e w`), cycling through `slots`. |
| `cylinder` | `x z y r h slot [cap]` | A tank/silo. |
| `setback` | `x z w d h slot [glass] [edges] [corner]` | A volume stacked on top of everything before it — `y` is computed (top of the plinth/volumes/fins/slabs/cylinders so far, or of the previous setback). Three in a row make a wedding-cake tower. |
| `sign` | `side text [y] [h=2.4] [slot=neonA] [panel=plinth] [w] [x or z]` | A dark panel on one façade with lit 3×5 pixel letters. `A–Z 0–9 - ·` and space, 12 characters max. Reads left→right from outside. |
| `bridge` | `x z x2 z2 y [t=1] [slot=metal] [strip]` | An axis-aligned bar between two points (share `x` or `z`) — walkway, duct, beam. `strip` lights its top. |
| `antenna_array` | `x z y [count=3] [pitch=1.5] [h=4] [axis=x] [slot=metal] [tip=neonB]` | A row of thin masts with lit tips, slightly uneven heights. |

A part exists in three places at once — `genSpec` in the page, `voxkit/grammar.py` + `voxkit/raster.py`, and this table. A part in one and not the others is a bug. The architects' mutation templates (`_template_part`) know all thirteen.

## Divisions and project (optional)

A spec may also carry who works in the building. The page builds one floor per division, desks for its offices, and hires agents from a reserve pool of 24 to fill them.

```json
"divisions": [ { "name": "Signal intake", "role": "Signal researcher", "offices": 3 } ],
"project":   { "title": "First broadcast", "stage": "Divisions assigned", "backend": "ollama · qwen2.5:7b", "budget": "0 / 12 calls" }
```

`offices` is 1–6. Set these with the MCP's `assign_divisions` (the owner's call), not inside an architect's proposal — architects design the shell, the owner staffs it.

## How the agents use it

```
brief (division, ring, footprint, mood) → architecture agent → spec.json
→ city renderer preview (boxes)  ─┐
→ MagicaVoxel MCP builds the kit ─┴→ owner reviews → approved spec is versioned in city/kit/
```

The agent never emits geometry. It emits a spec. That keeps designs reviewable, diffable, and rebuildable when the kit improves.

## Mapping to a MagicaVoxel kit

One `.vox` per part *type*, parametrised: the MCP builds a `volume` by filling `w×h×d` voxels in the `structure` palette index and carving the window grid in `glass`; `fins` is `count` thin volumes; and so on. Slots map to MagicaVoxel palette indices — reserve indices 1–8 for the slots above so every kit part shares one palette. Emissive slots (`glass`, `neonA`, `neonB`, `white`) get MagicaVoxel's emissive material so bloom picks them up on export.

Scale: 1 board unit = 4 voxels is a good starting density (a 14-unit lot = 56 voxels).

## Example — City Hall (`u1.json`)

Plinth → one wide low `volume` with a dense cyan glass band → four `pylons` with lit caps → a roof `volume` with `edges` → two crossed `strip`s in `white` for the civic seal → a `mast` with a beacon → alternating magenta/cyan `facade_lights` on the west and south faces. Ten parts, no geometry written by hand.
