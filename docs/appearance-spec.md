# Esperia appearance and interaction specification

Version: 0.1 · 2026-09-17 · Status: planning draft

Confirmed owner direction: no deadline; first usable release is a working research team with a simple, live city view. Detailed visual polish follows later.

Purpose: define what Esperia looks like and how the owner navigates it. The [functional specification](functional-spec.md) defines behavior; [TASKS](../TASKS.md) defines implementation work. This document separates the established city concept from proposed details that still need owner review.

## 1. Established concept

Source: [original build specification](build-spec.md), City model and Modular architecture.

- Esperia is a navigable city. Buildings represent projects or shared capabilities; floors represent divisions; offices represent agents.
- City Hall contains the mayor, city-wide job board, budget ledger and approval inbox.
- Agent identity persists when its underlying model changes.
- An office exposes the current assignment, active model, tools/actions, sources, artifacts, progress and blockers.
- Movement and animation reflect recorded execution events. Idle/rate-limited agents may visit homes or leisure buildings. Animation never triggers inference or implies nonexistent work.
- Ordinary accessible panels provide the same inspection and decision functions as the city.
- The city displays execution state; opening or closing the interface must not control a server job's lifetime.

No existing mockups, visual assets, palette, typography or detailed camera specification were found in this repository. Do not invent a claim that the owner approved those details. Preserve any additional reference supplied later under a documented reference path before visual implementation.

## 2. City layout

Confirmed first-release places: **City Hall, a research building and the Library**. These are navigation concepts, not a mandate to create separate services or processes. Analysis and operations initially live in panels within these buildings; separate facilities and leisure spaces are later possibilities.

| Place | Owner purpose | Content and phase |
| --- | --- | --- |
| City Hall | Set priorities, assign work, inspect blockers and make decisions | Mayor conversation, jobs, review inbox, budget/usage |
| Research building | Observe an investigation and inspect its evidence | Research team, task board, report versions |
| Library | Find what the city already knows | Discipline rooms/racks, viewable public-source documents/files, research notes, accepted reports and stale-evidence notices |
| Analysis lab (later separate building) | Inspect reproducible numerical work | Inputs, calculation runs, results and limitations |
| Operations office (later separate building) | Understand availability and resource use | Worker health, waiting states, connector status, usage |
| Homes/leisure spaces (later) | Make inactive states legible and personable | Event-driven idle/waiting presentation; no background model activity |

Start with these views backed by real records. Additional buildings, departments and agents are proposed through the mayor and become active only after owner approval and an actual capability exists.

## 3. Proposed screen composition

V-01 City overview: navigable scene plus a persistent, plain-language status strip showing active work, blocked work, decisions awaiting review and current resource allowance.

V-02 Navigation: select City Hall, a building, a division, then an agent. A breadcrumb and searchable list provide direct access without traversing the scene. Camera reset and reduced-motion controls remain visible.

V-03 Inspection panel: opening an office or task reveals a readable panel without losing the city location. Suggested tabs are Overview, Activity, Evidence, Notes, Calculations and Report. Show only supported tabs for the selected record.

V-04 Mayor input: natural-language assignment box with visible scope, execution preference and limits. The scoping result shows which entities and sources were chosen before the owner mistakes a representative sample for complete coverage.

V-05 Review inbox: show the concrete report/action, its version, supporting evidence and blockers before presenting a decision. Disabled acceptance must explain the blocker. A research acceptance control must never imply authority to trade or send messages.

V-06 Evidence comparison: open a claim next to its source excerpt, document date, original link and relevant calculation. Show conflicting claims side by side; do not collapse disagreement into an unexplained confidence number.

## 4. State presentation

| Recorded state | Presentation | Owner action |
| --- | --- | --- |
| Queued | Waiting assignment and position when known | Inspect, reprioritize or cancel where supported |
| Running | Current step and most recent event | Inspect evidence/progress; request cancellation when safe |
| Waiting for a tool or provider | Reason and earliest known retry time | Inspect; choose an explicit alternative if appropriate |
| Blocked | Specific missing input, failed check or uncertain outcome | Supply evidence, reconcile or request repair |
| Awaiting owner | Reviewed report or concrete approval request | Read and accept/reject the exact version |
| Accepted/rejected/cancelled | Stable history with decision provenance | Inspect; create explicitly linked follow-up work |
| Disconnected/stale UI | Last event time and reconnection indicator | Reconnect; never present stale state as live |

The current ledger has fewer states. Additional waiting/cancellation states are proposed and must first be implemented in the execution model. Do not invent them in the interface independently.

## 5. Visual direction

Owner direction, September 17: “city skylines-esque but blocky,” with enough architectural detail for architecture agents to create distinctive buildings. This establishes the inspiration and blocky form language; a specific camera, palette or asset set has not been selected.

Proposed interpretation for visual prototyping:

- City-scale composition with blocky building volumes and recognizable silhouettes.
- Detail comes from layered volumes, setbacks, windows, facades, roofs, terraces and landscaping. Blocky does not require every building to be a plain cube or identical voxel asset.
- A coherent scale and material language lets buildings vary without making the city difficult to read.
- Begin with a small, simple live city; retain room for richer agent-designed architecture later. Architecture-agent building creation is a future capability, not included in the current release estimate.
- Confirmed scope: architecture agents design Esperia’s in-city buildings. Proposed designs should follow the blocky city direction while allowing distinctive forms and details.
- Camera exploration supports the city experience; large research documents remain in conventional reading panels.
- Status is represented by labels/icons as well as color. Calm activity should not obscure warnings or pending decisions.
- Model/backend names appear in an agent's details, not throughout every navigation control.
- Camera/projection, palette, typography, avatar style and degree of animation remain open within the confirmed blocky city direction. React Three Fiber remains a proposed implementation choice. Establish the visual result before choosing the rendering approach.

    
## 6. Accessibility and responsive behavior

V-07 All first-release tasks must be possible using keyboard-accessible panels, without relying on 3D movement or color alone. Include focus order, readable zoom, reduced motion and useful loading/error/empty states.

V-08 Desktop prioritizes the city and inspection panel. Narrow screens prioritize task/review panels with an optional simplified city. Voice and elaborate mobile city navigation are later proposals, not first-release dependencies.

V-09 No decorative progress percentages unless an actual measurable denominator exists. Display completed steps, current activity and remaining planned tasks instead.

## 7. Visual acceptance gate

- Owner reviews a reference sheet and annotated screen flow before art implementation.
- An actual research job changes the correct city/office state through persisted events.
- The owner can reach the report, its sources and any blockers from the job without searching files.
- Reconnection does not duplicate agents or activity; stale state is explicitly labeled.
- The accessible panel route can create/inspect work and review a report independently of the scene.
- No placeholder jobs, fabricated chatter or simulated model work appears in the usable release.

## 8. Open visual decisions

D-01: inspiration confirmed as Cities: Skylines-esque but blocky; any additional mockups and exact traits remain to be collected.
D-02: camera, materials and acceptable first-release detail within the confirmed art direction.
D-03: priority desktop viewport and whether mobile approval is needed for the pilot.

Track decisions in the [roadmap](roadmap.md). Open details do not erase the established city concept.

## 9. Library and owner controls

V-10 Library navigation: city → Library → discipline room/rack → document. A searchable catalog provides the same route without scene navigation. Support cross-disciplinary collections without duplicating the underlying file. Discipline names and collections follow real work, not a fixed built-in roster.

V-11 Reading view: display the stored document itself with source/date/version details and links to related research. Public-source PDFs and readable text open in the viewer; unsupported formats have an explicit download/open-source option. Distinguish original files, extracted text and generated summaries. Access status is visible; public-source material does not make the application publicly accessible.

V-12 City Hall: distinguish routine delegated work from proposals awaiting financing/expansion approval. Show the exact proposed scope, agents, resources and costs. Provide owner override, reassignment and stop controls with a decision history. An agent's office retains identity and history when its active model changes.

A future University houses evaluated teaching and practice. Multiple strategy-team buildings and an internal economy remain later concepts, outside the initial three-building city.
