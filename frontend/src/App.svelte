<script lang="ts">
  import { onMount } from "svelte";
  import { studio } from "./lib/state.svelte";
  import { api, connectStream } from "./lib/api";
  import MenuBar from "./components/MenuBar.svelte";
  import ToolRail from "./components/ToolRail.svelte";
  import Viewport from "./components/Viewport.svelte";
  import StatusBar from "./components/StatusBar.svelte";
  import Panel from "./components/Panel.svelte";
  import PathFindingPanel from "./components/panels/PathFindingPanel.svelte";
  import DrawingAreaPanel from "./components/panels/DrawingAreaPanel.svelte";
  import PensPanel from "./components/panels/PensPanel.svelte";
  import VersionsPanel from "./components/panels/VersionsPanel.svelte";

  let viewport = $state<Viewport>();
  let fileInput: HTMLInputElement;

  onMount(() => {
    api.boot().catch((e) => console.error(e));
    const es = connectStream();
    return () => es.close();
  });

  function pickImage() {
    fileInput.click();
  }
  async function onFile(e: Event) {
    const f = (e.target as HTMLInputElement).files?.[0];
    if (f) await api.uploadImage(f);
    (e.target as HTMLInputElement).value = "";
  }
</script>

<div class="app-grid">
  <div class="area-menu"><MenuBar onImport={pickImage} /></div>
  <div class="area-rail"><ToolRail onImport={pickImage} onFit={() => viewport?.fit()} /></div>
  <div class="area-viewport"><Viewport bind:this={viewport} /></div>
  <div class="area-dock dock scroll">
    <Panel title="Path Finding"><PathFindingPanel /></Panel>
    <Panel title="Drawing Area" open={false}><DrawingAreaPanel /></Panel>
    <Panel title="Pens"><PensPanel /></Panel>
    <Panel title="Versions"><VersionsPanel /></Panel>
  </div>
  <div class="area-status"><StatusBar /></div>
</div>

<input
  bind:this={fileInput}
  type="file"
  accept="image/*"
  onchange={onFile}
  style="display:none"
/>

<style>
  .dock {
    background: var(--panel);
    border-left: 1px solid var(--line);
    height: 100%;
  }
</style>
