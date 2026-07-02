<script lang="ts">
  import { studio } from "../../lib/state.svelte";
  import { api } from "../../lib/api";
  import type { Pen } from "../../lib/types";
  import NumStep from "../NumStep.svelte";

  async function save() {
    await api.savePens();
    recalcGenerator();
  }

  // Editing the pens re-maps the generator's pen cycle: recompute the selected
  // generate layer in place (like auto-redraw). Skipped mid generator-switch so an
  // unapplied generator change is never applied, and while a job is in flight.
  function recalcGenerator() {
    const sel = studio.selectedLayer;
    if (
      sel?.kind === "generate" &&
      sel.source?.generator_id === studio.generatorId &&
      !studio.processing
    ) {
      void api.generate();
    }
  }

  function addPen() {
    studio.drawingSet?.pens.push({
      name: "Pen " + ((studio.drawingSet?.pens.length ?? 0) + 1),
      type: "Custom",
      colour: "#888888",
      weight: 1,
      stroke_mm: 0.5,
      enabled: true,
      nib_shape: "round",
      start_angle_deg: 0,
    });
    save();
  }
  function removePen(i: number) {
    studio.drawingSet?.pens.splice(i, 1);
    save();
  }
  function pct(p: Pen): number {
    const layer = studio.stats?.per_pen.find((x) => x.name === p.name);
    const total = studio.stats?.total || 0;
    return layer && total ? Math.round((layer.count / total) * 100) : 0;
  }
  async function loadLib(e: Event) {
    const select = e.target as HTMLSelectElement;
    const name = select.value;
    select.value = "";
    if (name) {
      await api.loadLibrary(name);
      recalcGenerator();
    }
  }
</script>

{#if studio.drawingSet}
  <div class="col">
    <div class="row">
      <select onchange={loadLib} title="Load a pen library">
        <option value="">Library…</option>
        {#each studio.libraries as lib}<option value={lib}>{lib}</option>{/each}
      </select>
      <button class="icon" title="Add pen" onclick={addPen}>＋</button>
    </div>

    <div class="pens">
      {#each studio.drawingSet.pens as pen, i (i)}
        <div class="pen" class:off={!pen.enabled}>
          <input
            type="checkbox"
            bind:checked={pen.enabled}
            onchange={save}
            title="Enabled"
          />
          <input type="color" bind:value={pen.colour} onchange={save} />
          <input class="name" bind:value={pen.name} onchange={save} />
          <NumStep
            class="w"
            min={0}
            step={0.5}
            bind:value={pen.weight}
            onchange={save}
            title="Weight (share of shapes)"
          />
          <button
            type="button"
            class="nib-toggle"
            class:active={pen.nib_shape === "flat"}
            aria-pressed={pen.nib_shape === "flat"}
            title={pen.nib_shape === "flat"
              ? "Flat/chisel nib — calligraphic preview (click for round)"
              : "Round nib — click for flat/chisel nib preview"}
            onclick={() => {
              pen.nib_shape = pen.nib_shape === "flat" ? "round" : "flat";
              save();
            }}
          >✒</button>
          <label
            class="sz"
            title={pen.nib_shape === "flat"
              ? "Nib width (mm) — Pilot Parallel ≈ 1.5–6mm"
              : "Pen size (mm) — reflected in the preview stroke width"}
          >
            <NumStep min={0.05} step={0.1} bind:value={pen.stroke_mm} onchange={save} />
            <span>mm</span>
          </label>
          <span class="pct">{pct(pen)}%</span>
          <button class="icon del" title="Remove" onclick={() => removePen(i)}>✕</button>
          {#if pen.nib_shape === "flat"}
            <div class="nib-row">
              <span class="ang-label">Angle</span>
              <label class="sz ang" title="Nib angle (°)">
                <NumStep
                  min={0}
                  max={179}
                  step={5}
                  bind:value={pen.start_angle_deg}
                  onchange={save}
                  title="Nib angle (°)"
                />
                <span>°</span>
              </label>
            </div>
          {/if}
        </div>
      {/each}
    </div>

    <div class="grid2">
      <div class="f">
        <label>Distribution</label>
        <select bind:value={studio.drawingSet.distribution_type} onchange={save}>
          <option value="luminance">Luminance</option>
          <option value="even">Even weighted</option>
          <option value="random">Random weighted</option>
          <option value="single">Single pen</option>
        </select>
      </div>
      <div class="f">
        <label>Order</label>
        <select bind:value={studio.drawingSet.distribution_order} onchange={save}>
          <option value="darkest">Darkest first</option>
          <option value="lightest">Lightest first</option>
          <option value="displayed">Displayed</option>
          <option value="reversed">Reversed</option>
        </select>
      </div>
    </div>
  </div>
{/if}

<style>
  .pens {
    display: flex;
    flex-direction: column;
    gap: 3px;
    margin: 6px 0;
  }
  .pen {
    display: grid;
    grid-template-columns: auto 28px minmax(0, 1fr) 40px auto 60px 30px auto;
    gap: 5px;
    align-items: center;
    background: var(--panel-2);
    border: 1px solid var(--line);
    border-radius: 4px;
    padding: 3px 5px;
  }
  .sz {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    align-items: center;
    gap: 3px;
  }
  .sz span {
    font-size: 10px;
    color: var(--text-dim);
  }
  .nib-row {
    grid-column: 1 / -1;
    display: flex;
    align-items: center;
    gap: 5px;
    padding: 2px 0 0 2px;
  }
  .ang-label {
    font-size: 10px;
    color: var(--text-dim);
  }
  .sz.ang {
    width: 80px;
    flex: 0 0 auto;
  }
  .nib-toggle {
    padding: 0 3px;
    height: 18px;
    border: 1px solid var(--line);
    border-radius: 3px;
    background: transparent;
    color: var(--text-dim);
    font-size: 13px;
    line-height: 1;
    cursor: pointer;
  }
  .nib-toggle:hover {
    color: var(--text);
    border-color: var(--accent);
  }
  .nib-toggle.active {
    color: var(--accent);
    border-color: var(--accent);
    background: color-mix(in srgb, var(--accent) 22%, transparent);
  }
  .pen.off {
    opacity: 0.45;
  }
  .name {
    width: 100%;
  }
  .pct {
    font-size: 11px;
    color: var(--text-dim);
    text-align: right;
  }
  .del {
    color: var(--text-dim);
    padding: 2px 5px;
  }
  .grid2 {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8px;
  }
  .f {
    display: flex;
    flex-direction: column;
    gap: 3px;
  }
  .f label {
    font-size: 11px;
  }
  select {
    width: 100%;
  }
</style>
