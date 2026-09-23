# esperia-voxkit — MCP server for the building grammar

Turns a building spec (`city/kit/GRAMMAR.md`) into a MagicaVoxel `.vox`, a glTF the city renderer can load, and a PNG preview. It writes real files — MagicaVoxel has no API, and the glTF path means the city never depends on the GUI.

## Install

Run it **from `city/mcp`** (or pass `--project city/mcp`). From the repo root, `uv` picks up Esperia's own `pyproject.toml`, which has no `esperia-voxkit` script, and fails with "Failed to spawn".

```sh
cd city/mcp
uv sync
uv run pytest -q                       # builds the kit specs end to end
uv run mypy --strict voxkit tests      # same bar as the main repo: strict, clean
uv run ruff check voxkit tests && uv run black --check voxkit tests
```

Layout: `voxkit/` is the package (`grammar`, `raster`, `vox`, `gltf`, `preview`, `server`); `server.py` at the root is only a launcher.

## Wire it up

Claude Desktop (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "esperia-voxkit": {
      "command": "uv",
      "args": ["--project", "/Users/mosley/projects/Esperia/city/mcp", "run", "esperia-voxkit"],
      "env": { "ESPERIA_KIT_DIR": "/Users/mosley/projects/Esperia/city/kit", "ESPERIA_BUILD_DIR": "/Users/mosley/projects/Esperia/city/build" }
    }
  }
}
```

Claude Code:

```sh
claude mcp add esperia-voxkit -- uv --project /Users/mosley/projects/Esperia/city/mcp run esperia-voxkit
```

## Tools

| Tool | Does |
| --- | --- |
| `grammar` | Part types, fields, palette slots, units, limits. Call first. |
| `list_kit` / `get_spec` | Browse and read approved specs (`u1`, `u3`, …). |
| `validate_spec` | Errors (must fix) and warnings (taste: off-lot, unknown slot). |
| `preview_building` | Just the isometric PNG. Fast; use it while iterating. |
| `build_building` | `.vox` + `.gltf` + `.png` + a timestamped copy of the spec in `city/build/<name>/`. |
| `approve_spec` | Save into `city/kit/` as a versioned city asset, build it, optionally place it (`lot=[col,row]`). Owner's call — refuses to overwrite unless told. |
| `place_building` / `free_lots` | Put a built model on a lot in the city page (refuses another building's lot), or list lots that are free. |
| `city_manifest` | What the page will load: every built model, its glTF, its lot. |
| `open_in_magicavoxel` | Opens a built `.vox` in the app (macOS `open -a MagicaVoxel`). |
| `architects` | The population: five founders with manifestos, taste vectors, wins, history. |
| `propose_round` | One design round for a brief: every architect proposes, the critic ranks. Returns candidates with PNG previews. Nothing enters the city. |
| `adopt_proposal` | The owner picks a winner: it joins the kit as `a1, a2, …`, gets built, optionally placed — and the architects drift. |
| `assign_divisions` | Staff a built model: divisions (name, role, offices) and an optional project. The page builds floors and desks and hires from a 24-agent reserve. Owner's call. |
| `novelty_of` | How unlike the kit a spec is, plus its measured features. |

Resource `esperia://grammar` serves `GRAMMAR.md`.

## The loop an architecture agent runs

1. `grammar` → learn parts and slots.
2. `get_spec("u1")` → see a real one.
3. Write a spec for the brief. `validate_spec`. Fix errors.
4. `preview_building` → look. Iterate.
5. `build_building` → hand the paths to the owner.
6. Owner says yes → `approve_spec(spec, "u11")`. The city picks it up from `city/kit/`.
7. Owner staffs it → `assign_divisions("u11", [{"name":"Signal intake","role":"Signal researcher","offices":3}])`. Reload the page: floors, desks, a roster, and agents who commute there.

The agent never emits geometry. It emits a spec.

## Seeing the models in the city

The page loads `city/build/manifest.json` and every placed glTF. Browsers won't fetch files from `file://`, so serve the folder:

```sh
cd ~/projects/Esperia && python3 -m http.server 8090 --directory city
open http://127.0.0.1:8090/esperia-city.html
```

Placed models replace the spec-rendered boxes on their lot; the header tag switches to "Models from city/build". The published artifact can't fetch, so it keeps the boxes.

## The architects — how emergence is meant to happen

Five founders, each with a manifesto and a **taste vector** over six measured features: height, mass, glow, rhythm, asymmetry, palette. A round works like this:

1. Every architect proposes several candidates by **mutating and crossing over the kit** (numeric drift, slot swaps, adding/removing parts, transplanting a part from a neighbour named in the brief). With `ESPERIA_MODEL_URL` set and `use_model=true`, they design with a local language model instead — see below.
2. Each keeps its best by its own taste. The **critic ranks in code**: `coherence × taste-fit + novelty`, where novelty is distance to the nearest building in the kit, blended with distance to the last three winners so one school can't win every round.
3. You adopt one. The winner's taste sharpens toward what won; the others **imitate a little**, plus a random walk. Each architect has a **signature** trait that imitation cannot erode — without that, ten rounds of imitation collapsed the whole population into "square and heavy". Lineage and the architect are written on the spec.

What that produced in a ten-round test: Vela (height) won four, Nomen (mass) four, Brise (asymmetry) two — three visible schools, with Brise's buildings leaning off-centre and Nomen's sitting square and heavy, cross-pollinated by transplants. Tamsin and Okoro didn't win but shifted the field. That's the emergence: it's in the drift, not in a prompt.

State lives in `city/agents/architects.json` and `city/agents/rounds/`. Delete the folder to reset the population to the founders.

Briefs that work: name the neighbours (`neighbours=["u3","a2"]`) so transplants come from the right place, and say what the building is *for*. Briefs that don't: "make something cool" — the critic can't score cool.

## Designing with a local model

```sh
ollama serve &                       # or anything OpenAI-compatible
ollama pull qwen2.5:7b
export ESPERIA_MODEL_URL=http://127.0.0.1:11434/v1 ESPERIA_MODEL=qwen2.5:7b
```

Restart the server with those set (in Claude Desktop, put them in the server's `env` block), then `propose_round(brief=..., use_model=true)`. Each architect gets its manifesto, taste, the grammar and the neighbours' specs, and is asked twice. Replies may be fenced, prefixed with prose, or a bare spec — all parse. If the endpoint is down or answers nonsense, that architect falls back to evolving the kit, so a round is never empty; the result's `model` field says whether a model was used. Every model spec goes through the same validator and critic as the evolved ones. `tests/test_llm.py` covers this against a stub endpoint; nothing has been run against a real Ollama yet.

## Conventions baked in

- 1 board unit = 4 voxels (`VOXELS_PER_UNIT`). A 14-unit lot is 56 voxels; MagicaVoxel's 256 limit gives ~60 units of height.
- Y-up in the grid and glTF; converted to MagicaVoxel's Z-up on write.
- Palette indices 1..n are assigned to slots in first-seen order per building. Emissive slots (`glass`, `neonA`, `neonB`, `white`, or the spec's `emissive` list) get a MagicaVoxel `_emit` material.
- glTF: two meshes, `structure` (lit, vertex colours) and `emissive` (`KHR_materials_unlit`, vertex colours). The city renderer should treat a mesh named `emissive` as a glow source.

## Pins

`mcp<2`: the 2.x SDK renamed `FastMCP` to `MCPServer` and changed other APIs. Migrate deliberately when there's a reason to; until then the pin keeps a clean `uv sync` working.

## Not done yet

- A real Ollama round. The path is tested against a stub; the first live run will show whether a 7B model writes usable specs or mostly falls back.
- Reserve pool is fixed at 24 agents on the page. Past that, `assign_divisions` warns and desks stay empty.
