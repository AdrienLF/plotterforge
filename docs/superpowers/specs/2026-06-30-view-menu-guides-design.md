# View Menu and Viewer Guides Design

## Context

The viewport always renders persistent construction overlays: an A4 boundary, A4 center lines, and full-sheet center lines. Layer bounds have a separate checkbox inside the Layers panel, even though both are viewer-display preferences. The application needs a familiar top-bar **View** menu that groups these overlays and lets the artwork be inspected without construction guides.

## Menu behavior

Add **View** after **Drawing** in the existing top menu bar. It uses the same controlled-menu behavior as File, Project, and Drawing:

- only one menu is open at a time;
- hovering another summary switches to it while a menu is open;
- clicking outside or pressing Escape closes it;
- choosing an item toggles its setting and closes the menu.

The View menu contains two checkmarked toggle items:

- **Show guides**
- **Show bounds**

Each item exposes its current state with `aria-pressed` and a fixed-width checkmark slot, so labels stay aligned when a setting is off. Both settings default to on and remain session-level UI preferences rather than project data.

## State and rendering

Add `showGuides = $state(true)` beside the existing `showLayerBounds` state. `showLayerBounds` remains the underlying state name; only its control moves.

When **Show guides** is off, the viewport does not render:

- the dashed A4 boundary;
- the vertical and horizontal A4 center lines inside it;
- the vertical and horizontal full-sheet center lines.

The following remain visible and functional regardless of **Show guides**:

- temporary horizontal and vertical snap lines during layer dragging;
- the outer page/canvas edge and shadow;
- artwork and source imagery;
- region-selection feedback;
- crop, mask, selection, and transform overlays;
- layer bounds, which are controlled independently.

When **Show bounds** is off, layer bounds are hidden in every workflow step, including Composition. Selected-layer transform handles and editing overlays remain available, so hiding bounds does not prevent composition editing. The current Composition-only forced-bounds condition is removed.

## Component changes

- `frontend/src/lib/state.svelte.ts`: add `showGuides`, defaulting to true.
- `frontend/src/components/MenuBar.svelte`: add the View summary and two state-backed toggle items.
- `frontend/src/components/panels/CompositionPanel.svelte`: remove the existing Show bounds checkbox and simplify the top bar around the add-layer actions.
- `frontend/src/components/Viewport.svelte`: conditionally render persistent guides and obey `showLayerBounds` in every step.

No backend or persistence changes are required.

## Testing

Add a frontend contract test that verifies:

- `showGuides` exists and defaults to true;
- MenuBar binds both View toggles to the correct state;
- CompositionPanel no longer owns the Show bounds control;
- Viewport gates the persistent guide block and does not gate snap lines;
- layer-bound visibility no longer forces Composition bounds on.

Add a focused Playwright test with a project containing a visible layer. It opens View, confirms both toggles are on, disables guides, and verifies the A4 and sheet-center guide elements disappear while the artwork remains. It then reopens View, disables bounds, and verifies layer-bound styling is removed. The test also confirms selecting an item closes the menu.
