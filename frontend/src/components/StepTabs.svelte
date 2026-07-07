<script lang="ts">
  import { studio } from "../lib/state.svelte";

  type Step = "composition" | "generate" | "plot";
  let { onSelect }: { onSelect: (step: Step) => void } = $props();

  const steps: { id: Step; label: string }[] = [
    { id: "composition", label: "Compose" },
    { id: "generate", label: "Generate" },
    { id: "plot", label: "Plot" },
  ];
</script>

<div class="steptabs" role="tablist" aria-label="Workflow step">
  {#each steps as step, i (step.id)}
    <button
      role="tab"
      aria-selected={studio.step === step.id}
      class:active={studio.step === step.id}
      onclick={() => onSelect(step.id)}
    >
      <span class="num">{i + 1}</span>
      <span class="label">{step.label}</span>
    </button>
    {#if i < steps.length - 1}<span class="arrow">›</span>{/if}
  {/each}
</div>

<style>
  .steptabs {
    display: flex;
    align-items: center;
    gap: 2px;
    height: 100%;
    padding: 0 10px;
    background: var(--panel-2);
    border-bottom: 1px solid var(--line);
  }
  button {
    display: flex;
    align-items: center;
    gap: 7px;
    background: none;
    border: none;
    border-radius: 5px;
    color: var(--text-dim);
    padding: 4px 11px;
    height: 24px;
  }
  button:hover {
    background: var(--header);
    color: var(--text);
  }
  button.active {
    background: var(--accent);
    color: #fff;
  }
  .num {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 16px;
    height: 16px;
    border-radius: 50%;
    background: rgba(255, 255, 255, 0.12);
    font-size: 10px;
    font-weight: 700;
  }
  button.active .num {
    background: rgba(255, 255, 255, 0.28);
  }
  .label {
    font-size: 12px;
    font-weight: 600;
  }
  .arrow {
    color: var(--text-dim);
    font-size: 14px;
    margin: 0 2px;
  }
</style>
