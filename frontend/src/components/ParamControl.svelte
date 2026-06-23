<script lang="ts">
  import type { Param } from "../lib/types";

  let { param, value = $bindable() }: { param: Param; value: any } = $props();

  const isNumeric = $derived(
    param.type === "float" || param.type === "int" || param.type === "angle",
  );
</script>

<div class="ctrl">
  <label for={param.name} title={param.help}>{param.label}</label>
  {#if param.type === "bool"}
    <input id={param.name} type="checkbox" bind:checked={value} />
  {:else if param.type === "enum"}
    <select id={param.name} bind:value>
      {#each param.choices ?? [] as opt}
        <option value={opt}>{opt}</option>
      {/each}
    </select>
  {:else if isNumeric}
    <div class="num">
      {#if param.min !== null && param.max !== null}
        <input
          type="range"
          min={param.min}
          max={param.max}
          step={param.step ?? (param.type === "int" ? 1 : 0.01)}
          bind:value
        />
      {/if}
      <input
        class="numbox"
        type="number"
        min={param.min ?? undefined}
        max={param.max ?? undefined}
        step={param.step ?? (param.type === "int" ? 1 : 0.01)}
        bind:value
      />
    </div>
  {/if}
</div>

<style>
  .ctrl {
    display: grid;
    grid-template-columns: 1fr;
    gap: 3px;
    margin-bottom: 8px;
  }
  label {
    font-size: 11px;
  }
  .num {
    display: grid;
    grid-template-columns: 1fr 56px;
    gap: 6px;
    align-items: center;
  }
  .numbox {
    width: 100%;
  }
  select {
    width: 100%;
  }
</style>
