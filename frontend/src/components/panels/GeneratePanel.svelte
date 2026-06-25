<script lang="ts">
  // Placeholder for the upcoming generative-drawing step: rule-based geometry
  // (circles, spokes, etc.) drawn directly onto the canvas.
</script>

<div class="generate col">
  <p class="lead">Generative drawing</p>
  <p class="muted">
    Build a drawing from rules instead of an image — circles, spokes, radial and
    grid patterns, and more. Coming soon.
  </p>
  <ul class="muted">
    <li>Place primitives (circles, lines, spokes)</li>
    <li>Drive size / spacing / count by rules</li>
    <li>Combine with Path Finding output</li>
  </ul>
</div>

<style>
  .generate {
    gap: 8px;
  }
  .lead {
    margin: 0;
    font-weight: 600;
    color: var(--text);
  }
  p {
    margin: 0;
    font-size: 12px;
    line-height: 1.4;
  }
  ul {
    margin: 4px 0 0;
    padding-left: 18px;
    font-size: 12px;
    line-height: 1.6;
  }
</style>
