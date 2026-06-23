<script lang="ts">
  import { studio } from "../lib/state.svelte";

  const PX_PER_MM = 2.4;

  let zoom = $state(1);
  let tx = $state(0);
  let ty = $state(0);
  let vw = $state(0);
  let vh = $state(0);
  let dragging = false;
  let lastX = 0;
  let lastY = 0;
  let fitted = false;

  const page = $derived.by(() => {
    const a = studio.area;
    if (!a) return { w: 297, h: 420, bg: "#202020", canvas: "#fff" };
    const f = a.units === "cm" ? 10 : a.units === "in" ? 25.4 : a.units === "px" ? 25.4 / 96 : 1;
    let w = a.width * f, h = a.height * f;
    if (a.orientation === "landscape" && h > w) [w, h] = [h, w];
    if (a.orientation === "portrait" && w > h) [w, h] = [h, w];
    return { w, h, bg: a.background_colour, canvas: a.canvas_colour };
  });

  export function fit() {
    if (!vw || !vh) return;
    const s = Math.min(vw / (page.w * PX_PER_MM), vh / (page.h * PX_PER_MM)) * 0.9;
    zoom = s || 1;
    tx = (vw - page.w * PX_PER_MM * zoom) / 2;
    ty = (vh - page.h * PX_PER_MM * zoom) / 2;
  }

  // One-shot auto-fit once the viewport first has a measured size. After that
  // the user controls zoom/pan (and the Fit button re-runs fit() on demand).
  $effect(() => {
    if (!fitted && vw && vh) {
      fitted = true;
      fit();
    }
  });

  function onWheel(e: WheelEvent) {
    e.preventDefault();
    const factor = e.deltaY < 0 ? 1.1 : 1 / 1.1;
    const nz = Math.min(40, Math.max(0.05, zoom * factor));
    // zoom toward cursor
    const rx = e.offsetX, ry = e.offsetY;
    tx = rx - (rx - tx) * (nz / zoom);
    ty = ry - (ry - ty) * (nz / zoom);
    zoom = nz;
  }
  function onDown(e: PointerEvent) {
    dragging = true;
    lastX = e.clientX;
    lastY = e.clientY;
    (e.target as HTMLElement).setPointerCapture(e.pointerId);
  }
  function onMove(e: PointerEvent) {
    if (!dragging) return;
    tx += e.clientX - lastX;
    ty += e.clientY - lastY;
    lastX = e.clientX;
    lastY = e.clientY;
  }
  function onUp(e: PointerEvent) {
    dragging = false;
    (e.target as HTMLElement).releasePointerCapture?.(e.pointerId);
  }
</script>

<div
  class="viewport"
  style:background={page.bg}
  bind:clientWidth={vw}
  bind:clientHeight={vh}
  onwheel={onWheel}
  onpointerdown={onDown}
  onpointermove={onMove}
  onpointerup={onUp}
  role="presentation"
>
  <div class="stage" style:transform={`translate(${tx}px, ${ty}px) scale(${zoom})`}>
    <div
      class="page"
      style:width={`${page.w * PX_PER_MM}px`}
      style:height={`${page.h * PX_PER_MM}px`}
      style:background={page.canvas}
    >
      {#if studio.previewSvg}
        <div class="svgwrap">{@html studio.previewSvg}</div>
      {:else if studio.imageUrl}
        <img class="src" src={studio.imageUrl} alt="source" />
      {:else}
        <div class="placeholder">Import an image to begin</div>
      {/if}
    </div>
  </div>

  {#if studio.processing}
    <div class="busy">Processing… {Math.round(studio.progress * 100)}%</div>
  {/if}
</div>

<style>
  .viewport {
    position: relative;
    width: 100%;
    height: 100%;
    overflow: hidden;
    cursor: grab;
  }
  .viewport:active {
    cursor: grabbing;
  }
  .stage {
    position: absolute;
    top: 0;
    left: 0;
    transform-origin: 0 0;
  }
  .page {
    position: relative;
    box-shadow: 0 0 0 1px #000, 0 8px 40px rgba(0, 0, 0, 0.5);
  }
  .svgwrap {
    position: absolute;
    inset: 0;
  }
  .svgwrap :global(svg) {
    width: 100%;
    height: 100%;
    display: block;
  }
  .src {
    width: 100%;
    height: 100%;
    object-fit: contain;
    opacity: 0.85;
  }
  .placeholder {
    position: absolute;
    inset: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    color: #999;
  }
  .busy {
    position: absolute;
    bottom: 12px;
    left: 12px;
    background: rgba(0, 0, 0, 0.6);
    padding: 5px 10px;
    border-radius: 4px;
    font-size: 12px;
  }
</style>
