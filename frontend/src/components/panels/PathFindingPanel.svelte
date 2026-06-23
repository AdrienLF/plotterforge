<script lang="ts">
  import { studio } from "../../lib/state.svelte";
  import { api } from "../../lib/api";
  import ParamControl from "../ParamControl.svelte";

  const families = $derived.by(() => {
    const m = new Map<string, typeof studio.pfms>();
    for (const p of studio.pfms) {
      if (!m.has(p.family)) m.set(p.family, []);
      m.get(p.family)!.push(p);
    }
    return [...m.entries()];
  });

  // group params by their `group` field, preserving order
  const groups = $derived.by(() => {
    const m = new Map<string, typeof studio.schema>();
    for (const p of studio.schema) {
      if (!m.has(p.group)) m.set(p.group, []);
      m.get(p.group)!.push(p);
    }
    return [...m.entries()];
  });

  async function onSelect(e: Event) {
    await api.selectPfm((e.target as HTMLSelectElement).value);
  }
</script>

<div class="col">
  <select class="pfm-select" value={studio.pfmId} onchange={onSelect}>
    {#each families as [family, pfms]}
      <optgroup label={family.toUpperCase()}>
        {#each pfms as p}
          <option value={p.id}>{p.name}</option>
        {/each}
      </optgroup>
    {/each}
  </select>

  <button
    class="primary start"
    disabled={studio.processing || !studio.imageUrl}
    onclick={() => api.process()}
  >
    {studio.processing ? "Processing…" : "▶ Start"}
  </button>

  {#each groups as [group, params]}
    <div class="group">
      <div class="group-title">{group}</div>
      {#each params as p (p.name)}
        <ParamControl param={p} bind:value={studio.params[p.name]} />
      {/each}
    </div>
  {/each}
</div>

<style>
  .pfm-select {
    width: 100%;
  }
  .start {
    width: 100%;
    padding: 6px;
  }
  .group {
    border-top: 1px solid var(--line);
    padding-top: 8px;
    margin-top: 4px;
  }
  .group-title {
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: var(--accent);
    margin-bottom: 6px;
  }
</style>
