<script lang="ts">
  import { studio } from "../../lib/state.svelte";
  import { api } from "../../lib/api";

  let name = $state("");

  async function save() {
    await api.saveVersion(name, "");
    name = "";
  }
  function when(ts: number) {
    return new Date(ts * 1000).toLocaleString();
  }
</script>

<div class="col">
  <div class="row save">
    <input placeholder="Version name…" bind:value={name} />
    <button
      class="primary"
      disabled={!studio.stats}
      title="Save current drawing as a version"
      onclick={save}>＋ Save</button
    >
  </div>

  {#if studio.versions.length === 0}
    <p class="muted empty">No versions yet. Process a drawing and save it.</p>
  {/if}

  <div class="list">
    {#each studio.versions as v, i (v.id)}
      <div class="ver">
        <img
          class="thumb"
          alt={v.name}
          src={`/api/version-thumb/${v.id}`}
          onclick={() => api.loadVersion(v.id)}
          role="presentation"
        />
        <div class="meta">
          <div class="name" title={v.pfm_id}>{v.name}</div>
          <div class="stars">
            {#each [1, 2, 3, 4, 5] as s}
              <button
                class="star"
                class:on={v.rating >= s}
                onclick={() => api.rateVersion(v.id, s)}>★</button
              >
            {/each}
          </div>
          <div class="date muted">{when(v.timestamp)}</div>
        </div>
        <div class="actions">
          <button class="icon" title="Load" onclick={() => api.loadVersion(v.id)}>👁</button>
          <button class="icon" title="Up" onclick={() => api.moveVersion(v.id, -1)} disabled={i === 0}>▲</button>
          <button class="icon" title="Down" onclick={() => api.moveVersion(v.id, 1)} disabled={i === studio.versions.length - 1}>▼</button>
          <button class="icon del" title="Delete" onclick={() => api.deleteVersion(v.id)}>✕</button>
        </div>
      </div>
    {/each}
  </div>

  {#if studio.versions.length}
    <button class="danger clear" onclick={() => api.clearVersions()}>Clear all</button>
  {/if}
</div>

<style>
  .save input {
    flex: 1;
  }
  .empty {
    font-size: 12px;
    padding: 4px 0;
  }
  .list {
    display: flex;
    flex-direction: column;
    gap: 6px;
    margin-top: 6px;
  }
  .ver {
    display: grid;
    grid-template-columns: 64px 1fr auto;
    gap: 8px;
    background: var(--panel-2);
    border: 1px solid var(--line);
    border-radius: 5px;
    padding: 6px;
  }
  .thumb {
    width: 64px;
    height: 64px;
    object-fit: contain;
    background: #fff;
    border-radius: 3px;
    cursor: pointer;
  }
  .meta {
    display: flex;
    flex-direction: column;
    gap: 2px;
    min-width: 0;
  }
  .name {
    font-weight: 600;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .date {
    font-size: 10px;
  }
  .stars {
    display: flex;
  }
  .star {
    background: none;
    border: none;
    color: #55555c;
    padding: 0 1px;
    font-size: 13px;
  }
  .star.on {
    color: #f0c040;
  }
  .actions {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }
  .actions .icon {
    padding: 1px 5px;
    font-size: 11px;
    min-width: 0;
  }
  .del {
    color: var(--danger);
  }
  .clear {
    margin-top: 8px;
  }
</style>
