<script lang="ts">
  import type { Snippet } from "svelte";

  let {
    title,
    open = $bindable(true),
    actions,
    children,
  }: {
    title: string;
    open?: boolean;
    actions?: Snippet;
    children?: Snippet;
  } = $props();
</script>

<section class="panel">
  <header>
    <button class="title" onclick={() => (open = !open)}>
      <span class="tri">{open ? "▾" : "▸"}</span>{title}
    </button>
    <div class="spacer"></div>
    {@render actions?.()}
  </header>
  {#if open}
    <div class="body">{@render children?.()}</div>
  {/if}
</section>

<style>
  .panel {
    border-bottom: 1px solid var(--line);
    background: var(--panel);
  }
  header {
    display: flex;
    align-items: center;
    background: var(--header);
    padding: 0 6px 0 0;
    height: 26px;
  }
  .title {
    background: none;
    border: none;
    color: var(--text);
    font-weight: 600;
    letter-spacing: 0.02em;
    text-transform: uppercase;
    font-size: 11px;
    padding: 0 8px;
    height: 100%;
    flex: 1;
    text-align: left;
  }
  .title:hover {
    background: #3c3c42;
  }
  .tri {
    color: var(--text-dim);
    margin-right: 6px;
    font-size: 10px;
  }
  .body {
    padding: 8px;
  }
</style>
