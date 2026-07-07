<script lang="ts">
  // Floating toolbar shown while painting a field mask on the Viewport canvas.
  import { studio } from "../lib/state.svelte";

  let {
    onClear,
    onSave,
    onCancel,
  }: {
    onClear: () => void;
    onSave: () => void;
    onCancel: () => void;
  } = $props();
</script>

{#if studio.fieldPaint}
  <div class="field-paint-bar" role="toolbar" aria-label="Field mask painting">
    <strong>Paint field mask</strong>
    <label>
      brush
      <input type="range" min="5" max="200" step="1" bind:value={studio.fieldPaint.brush} />
    </label>
    <label>
      value
      <input
        type="range"
        min="0"
        max="1"
        step="0.05"
        bind:value={studio.fieldPaint.value}
        title="Black (low) to white (high)"
      />
      <span class="swatch" style:background={`rgb(${Math.round(studio.fieldPaint.value * 255)},${Math.round(studio.fieldPaint.value * 255)},${Math.round(studio.fieldPaint.value * 255)})`}></span>
    </label>
    <input class="name" type="text" bind:value={studio.fieldPaint.name} placeholder="Mask name" />
    <button type="button" onclick={onClear}>Clear</button>
    <button type="button" onclick={onCancel}>Cancel</button>
    <button type="button" class="primary" onclick={onSave}>Save</button>
  </div>
{/if}

<style>
  .field-paint-bar {
    position: fixed;
    left: 50%;
    bottom: 24px;
    transform: translateX(-50%);
    z-index: 45;
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 8px 14px;
    border: 1px solid var(--line);
    background: var(--panel);
    box-shadow: 0 12px 40px rgba(0, 0, 0, 0.45);
    font-size: 11px;
    white-space: nowrap;
  }
  label {
    display: inline-flex;
    align-items: center;
    gap: 6px;
  }
  input[type="range"] {
    width: 90px;
  }
  .swatch {
    width: 14px;
    height: 14px;
    border: 1px solid var(--line);
    display: inline-block;
  }
  .name {
    width: 110px;
  }
</style>
