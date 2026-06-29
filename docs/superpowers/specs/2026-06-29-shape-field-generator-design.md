# Shape Field Generator Design

## Goal

Add a second Generate algorithm, **Shape Field**, for building intricate plotter-ready patterns from configurable layers of geometric shapes distributed across a tiled field. The user selects it from the existing Generate algorithm menu and edits it through a dedicated editor on the Generate page.

## User Experience

Selecting **Shape Field** keeps the existing target-layer selector, Generate button, and Auto redraw toggle. The generic flat parameter list is replaced by a dedicated editor with four sections:

1. **Field** — layout, rows, columns, spacing, origin, and combination mode.
2. **Shape stack** — dynamic add, duplicate, remove, enable, and reorder controls.
3. **Evolution** — deterministic field modulation plus seeded random variation.
4. **Output** — page, margins, and the existing generator framework transforms.

The shape stack supports a dynamic number of layers rather than fixed slots. Each card has a stable ID and controls for shape type, size, rotation, X/Y offset, repetition count, repeat scale, and repeat rotation. Shape-specific controls appear only when relevant:

- **Circle:** curve segments.
- **Polygon:** sides.
- **Star:** points and inner-radius ratio.
- **Diamond:** aspect ratio.
- **Cross:** arm width.
- **Spiral:** turns and curve segments.
- **Wave:** cycles, amplitude, and curve segments.

Changes participate in the existing debounced Auto redraw behavior. The complete configuration is stored in `layer.source.params`, so projects and versions restore the editor exactly.

## Pattern Grammar

### Layouts

The selectable field layouts are:

- **Square:** aligned rows and columns.
- **Brick:** every second row shifts by half a cell.
- **Hex:** alternating rows use hexagonal horizontal and vertical spacing.
- **Triangular:** alternating positions form an equilateral triangular lattice.
- **Jittered:** a square field with deterministic seeded position displacement.

Rows and columns define a finite field within the configured page. Spacing and field rotation determine the lattice; page margins clip the final geometry through the existing framework.

### Combination modes

- **Nested:** every enabled shape layer is centered in every tile.
- **Alternating:** tiles cycle through enabled shape layers, drawing one layer per tile.
- **Connected:** nested shapes are drawn and neighboring tile centers are joined according to the selected lattice topology.
- **Overlapping:** shape layers alternate between tile centers and neighbor-edge midpoints, creating interlocking cross-tile motifs.

### Repetition

Each layer may emit concentric or progressive copies. `repeat_count`, `repeat_scale`, and `repeat_rotation` create nested, expanding, shrinking, or twisting families without requiring duplicate layer cards.

## Evolution and Randomness

A field modulation function produces a normalized value for every tile. The source is selectable from **none, row, column, radial, wave,** and **seeded noise**. Frequency and phase tune periodic sources. A target selector applies the value to **scale, rotation, offset,** or a combined transformation, with one global amount.

Seeded random controls are additive and independently parameterized:

- position jitter;
- rotation jitter;
- scale jitter;
- tile dropout probability.

The same complete parameter set and seed must always produce byte-for-byte equivalent line geometry. Changing the seed must change any enabled random or noise effect.

## Architecture

### Backend generator

Create `engine/shape_field.py` to own:

- the `ShapeLayer` defaults and normalization;
- lattice point generation;
- modulation and seeded variation;
- primitive polyline generation;
- combination-mode assembly;
- a `shape_field(params, seed)` entry point returning `(lines, page_width_cm, page_height_cm)`.

Keep `engine/generate.py` responsible for the shared registry and existing Spokes & Circles generator. Register Shape Field as `shape_field` with display name `Shape Field`, editor metadata `shape_field`, scalar schema parameters, default shape-layer data, and a dedicated normalizer.

The generation worker will use a generator-specific normalizer when present; otherwise it keeps the current generic `validate` path. The Shape Field normalizer validates scalar schema values and sanitizes the `shape_layers` list. Invalid layer entries fall back to safe defaults and unknown keys are discarded. Layer count is not independently capped; the output budget below limits the total work while preserving dynamic add/remove behavior.

To keep Auto redraw responsive, generation rejects configurations whose estimated output exceeds 50,000 polylines (`tiles × emitted layers × repeats`, plus connectors) with a clear error asking the user to reduce rows, columns, layers, or repeats.

### API contract

`GET /api/generate/shape_field/schema` will add `editor: "shape_field"`, a complete `defaults.shape_layers` array containing circle, star, and wave starter layers, and the supported `shape_types` list. Existing generator responses remain valid because these fields are additive. Its `params` array contains the scalar field, evolution, random, page, and framework schemas. `POST /api/generate` remains unchanged and receives the full scalar parameter map plus `shape_layers`.

### Frontend state and editor

Extend generator state with the schema's `editor`, `defaults`, and `shape_types` metadata. `api.selectGenerator` preserves scalar values as it does today and initializes or retains `shape_layers` only for Shape Field.

Create `frontend/src/components/generate/ShapeFieldEditor.svelte`. `GeneratePanel.svelte` renders it when `studio.generatorEditor === "shape_field"`; other generators keep the existing generic grouped controls. The editor reuses `ParamControl` for scalar settings and owns immutable shape-stack edits so Svelte reactivity and the existing `paramsKey` Auto redraw comparison observe every change.

Shape layers are stored directly under `studio.genParams.shape_layers`. No second save endpoint or parallel state store is introduced.

## Geometry Rules

- All output is finite 2D polylines in generator centimeters.
- Circle, polygon, star, diamond, and cross paths are explicitly closed.
- Spiral and wave paths are open.
- Shape size is relative to field spacing; values above one are allowed for deliberate overlap.
- Connected mode emits each undirected lattice edge once.
- Framework margin clipping, distortion, perspective, final scale, and centimeter-to-millimeter conversion run exactly as they do for Spokes & Circles.

## Error Handling

- Empty shape stacks generate a clear `Shape Field needs at least one enabled shape layer` error.
- Invalid layout, mode, modulation, target, or shape values fall back to documented defaults.
- Non-finite numeric values fall back to their defaults before geometry is created.
- Excessive output is rejected before allocating the full geometry list.
- A shape with zero effective scale is skipped rather than emitting degenerate paths.

## Testing

Backend unit tests will cover:

- generator registration, schema metadata, and defaults;
- all seven primitive types and closed/open path contracts;
- all five layouts;
- all four combination modes;
- repeat scale/rotation behavior;
- each modulation source and target;
- seeded determinism, changed-seed variation, jitter, and dropout;
- shape-layer normalization and the 50,000-polyline guard;
- framework compatibility and non-empty SVG generation through the API worker.

Frontend tests will cover:

- selecting Shape Field chooses the dedicated editor;
- add, duplicate, remove, enable, and reorder operations update `genParams.shape_layers`;
- shape-specific controls follow the selected type;
- generator switching does not leak structured parameters into Spokes & Circles;
- Auto redraw observes nested shape-layer changes;
- a Generate-page end-to-end flow creates a non-empty Shape Field layer and restores its configuration.

## Scope Boundaries

This feature does not add arbitrary scripting, filled shapes, per-shape pen assignment, freehand paths, user-imported SVG motifs, or changes to the general `Param` type system. Those can be considered after the dedicated editor proves the structured workflow.
