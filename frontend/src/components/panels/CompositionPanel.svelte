<script lang="ts">
  import { api } from "../../lib/api";
  import { studio } from "../../lib/state.svelte";

  const layersTopFirst = $derived([...studio.composition.layers].reverse());

  async function setVisible(id: string, visible: boolean) {
    await api.patchLayer(id, { visible });
  }

  async function rename(id: string, name: string) {
    await api.patchLayer(id, { name });
  }

  async function moveSelected(axis: "x" | "y", value: number) {
    const layer = studio.selectedLayer;
    if (!layer || !Number.isFinite(value)) return;
    layer[axis] = value;
    await api.patchLayer(layer.id, { [axis]: value });
  }

  async function remove(id: string) {
    await api.deleteLayer(id);
  }
</script>

<div class="composition col">
  {#if studio.composition.layers.length}
    <div class="layers">
      {#each layersTopFirst as layer (layer.id)}
        <div
          class="layer"
          class:active={layer.id === studio.composition.selected_layer_id}
        >
          <input
            aria-label={`Toggle ${layer.name}`}
            type="checkbox"
            checked={layer.visible}
            onchange={(e) => setVisible(layer.id, (e.target as HTMLInputElement).checked)}
          />
          <button class="pick" onclick={() => api.selectLayer(layer.id)}>
            <span>{layer.name}</span>
            <em>{Math.round(layer.width)} x {Math.round(layer.height)} mm</em>
          </button>
          <input
            class="name"
            value={layer.name}
            aria-label={`Rename ${layer.name}`}
            onchange={(e) => rename(layer.id, (e.target as HTMLInputElement).value)}
          />
          <div class="actions">
            <button title="Move up" aria-label={`Move ${layer.name} up`} onclick={() => api.moveLayer(layer.id, 1)}>↑</button>
            <button title="Move down" aria-label={`Move ${layer.name} down`} onclick={() => api.moveLayer(layer.id, -1)}>↓</button>
            <button title="Duplicate" aria-label={`Duplicate ${layer.name}`} onclick={() => api.duplicateLayer(layer.id)}>⧉</button>
            <button class="danger-text" title="Delete" aria-label={`Delete ${layer.name}`} onclick={() => remove(layer.id)}>×</button>
          </div>
        </div>
      {/each}
    </div>
  {:else}
    <div class="empty">No layers</div>
  {/if}

  {#if studio.selectedLayer}
    <div class="position">
      <div class="f">
        <label for="layer-x">X</label>
        <input
          id="layer-x"
          type="number"
          step="0.1"
          value={studio.selectedLayer.x}
          onchange={(e) => moveSelected("x", Number((e.target as HTMLInputElement).value))}
        />
      </div>
      <div class="f">
        <label for="layer-y">Y</label>
        <input
          id="layer-y"
          type="number"
          step="0.1"
          value={studio.selectedLayer.y}
          onchange={(e) => moveSelected("y", Number((e.target as HTMLInputElement).value))}
        />
      </div>
    </div>
  {/if}
</div>

<style>
  .composition {
    gap: 10px;
  }
  .layers {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }
  .layer {
    display: grid;
    grid-template-columns: 20px minmax(0, 1fr);
    gap: 6px;
    align-items: center;
    border: 1px solid var(--line);
    background: var(--panel-2);
    padding: 5px;
  }
  .layer.active {
    border-color: var(--accent);
    background: #263346;
  }
  .pick {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    min-width: 0;
    border: 0;
    background: transparent;
    padding: 0;
  }
  .pick span {
    max-width: 100%;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .pick em {
    color: var(--text-dim);
    font-size: 10px;
    font-style: normal;
  }
  .name {
    grid-column: 2;
    width: 100%;
  }
  .actions {
    grid-column: 2;
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 4px;
  }
  .actions button {
    min-width: 0;
    padding: 2px 4px;
  }
  .danger-text {
    color: var(--danger);
  }
  .position {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8px;
    border-top: 1px solid var(--line);
    padding-top: 8px;
  }
  .f {
    display: flex;
    flex-direction: column;
    gap: 3px;
  }
  .f input {
    width: 100%;
  }
  .empty {
    color: var(--text-dim);
    font-size: 12px;
    padding: 6px 0;
  }
</style>
