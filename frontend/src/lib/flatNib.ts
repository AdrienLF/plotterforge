// Preview-only approximation of the mark a flat/chisel calligraphy nib lays
// down. Used only to build the string shown in the on-screen <img> preview;
// it never touches `layer.svg`, the server's `compose_visible_svg` output,
// the exported SVG, or anything the plot pipeline parses. The plotter always
// draws the true centerline - the physical nib produces its own width.

import type { Pen } from "./types";

/**
 * Perpendicular half-width the nib lays down while travelling in `dirRad`
 * (page-frame radians), for a nib of width `nibWidthMm` held at a fixed
 * `startAngleDeg` (page-frame degrees): full width when the nib is
 * perpendicular to travel, a hairline when parallel. The 0.05 floor matches
 * the backend's minimum stroke width (`engine/svg_io.py`) so a nib held
 * parallel to travel still shows a hairline instead of vanishing.
 */
export function nibHalfWidth(dirRad: number, nibWidthMm: number, startAngleDeg: number): number {
  return Math.max(0.05, (nibWidthMm / 2) * Math.abs(Math.sin(dirRad - (startAngleDeg * Math.PI) / 180)));
}

function fmt(v: number): string {
  // Snap sub-nanometre floating dust (e.g. sin(pi) ~ 1e-16 from axis-aligned
  // segments) to 0, which also normalizes -0 - keeps coords like "12,0" instead
  // of "12,-0".
  const n = Math.abs(v) < 1e-9 ? 0 : v;
  let s = n.toFixed(4);
  if (s.includes(".")) {
    s = s.replace(/0+$/, "").replace(/\.$/, "");
  }
  return s;
}

/**
 * Turn a centerline polyline into a filled-outline path `d`, as if drawn by a
 * flat nib of width `nibWidthMm` held at fixed page angle `startAngleDeg`.
 * Pure geometry, no DOM - safe to unit test directly.
 *
 * Each segment becomes its own constant-width quad, the width set by THAT
 * segment's travel direction. A flat nib lays a constant width along any
 * straight run, so width must follow each segment - averaging incoming/outgoing
 * directions at a shared vertex made straight edges taper toward corners (a
 * horizontal edge at angle 0 thickened into its vertical neighbour). Every quad
 * is wound the same way, so the default nonzero fill unions the separate
 * subpaths without holes.
 *
 * ponytail: no corner-join fill - adjacent quads of unequal width leave a tiny
 * wedge gap on the outside of a turn, acceptable for a preview. Add per-vertex
 * join triangles only if the nicks show at wide nibs.
 */
export function flatNibOutline(
  points: [number, number][],
  nibWidthMm: number,
  startAngleDeg: number,
): string {
  const subpaths: string[] = [];
  for (let i = 0; i < points.length - 1; i++) {
    const [ax, ay] = points[i];
    const [bx, by] = points[i + 1];
    const dx = bx - ax;
    const dy = by - ay;
    if (dx === 0 && dy === 0) continue; // zero-length (duplicate point): no direction
    const dir = Math.atan2(dy, dx);
    const hw = nibHalfWidth(dir, nibWidthMm, startAngleDeg);
    const nx = Math.cos(dir + Math.PI / 2) * hw;
    const ny = Math.sin(dir + Math.PI / 2) * hw;
    subpaths.push(
      `M${fmt(ax + nx)},${fmt(ay + ny)} L${fmt(bx + nx)},${fmt(by + ny)} ` +
        `L${fmt(bx - nx)},${fmt(by - ny)} L${fmt(ax - nx)},${fmt(ay - ny)} Z`,
    );
  }
  return subpaths.join(" ");
}

const SVG_NS = "http://www.w3.org/2000/svg";
const INKSCAPE_NS = "http://www.inkscape.org/namespaces/inkscape";

function inkscapeAttr(el: Element, name: string): string | null {
  // DOMParser attribute access for namespaced attrs is fiddly: the qualified
  // name is usually "inkscape:xxx", but the server's compose step re-emits
  // each pen-stroke group through Python's ElementTree, which (whenever the
  // "inkscape" prefix hasn't already been registered elsewhere in that
  // process) serializes it with an auto-generated prefix like "ns1:xxx"
  // instead. getAttributeNS looks up by namespace URI rather than prefix, so
  // it finds the attribute regardless of which prefix Python happened to
  // pick - confirmed empirically against engine/composition.py's
  // compose_visible_svg output.
  return el.getAttribute(`inkscape:${name}`) ?? el.getAttributeNS(INKSCAPE_NS, name);
}

function findMatchingPen(
  label: string | null,
  strokeColour: string | null,
  enabledPens: Pen[],
): Pen | null {
  if (label) {
    const byName = enabledPens.find((p) => p.name === label);
    if (byName) return byName;
  }
  if (strokeColour) {
    // Pen colours aren't guaranteed unique - an ambiguous match is no match.
    const byColour = enabledPens.filter((p) => p.colour === strokeColour);
    if (byColour.length === 1) return byColour[0];
  }
  return null;
}

/** Parse a plain "M x,y L x,y ..." centerline `d` (the only shape our own generators emit). */
function parseCenterline(d: string): [number, number][] {
  const points: [number, number][] = [];
  const tokenRe = /[ML]\s*(-?\d+(?:\.\d+)?)[\s,]+(-?\d+(?:\.\d+)?)/g;
  let match: RegExpExecArray | null;
  while ((match = tokenRe.exec(d)) !== null) {
    points.push([parseFloat(match[1]), parseFloat(match[2])]);
  }
  return points;
}

/**
 * Rewrite the pen-stroke `<g>` groups of a composed layer SVG so flat-nib
 * pens render as filled variable-width outlines instead of a uniform round
 * stroke, approximating what the physical nib would lay down. Browser-only
 * (DOMParser/XMLSerializer - no new dependency).
 *
 * Fails safe: this is the app's first DOMParser use, so ANY parse or
 * transform error returns `svg` unchanged rather than risk a broken image.
 * This function only builds the string handed to the preview `<img>` src -
 * it never mutates `svg`'s backing store and its result is never written
 * back to `layer.svg` or any server-persisted state, so the exported/plotted
 * SVG is completely unaffected.
 */
export function renderFlatNibPreview(svg: string, pens: Pen[]): string {
  try {
    const enabledPens = pens.filter((p) => p.enabled);

    const doc = new DOMParser().parseFromString(svg, "image/svg+xml");
    if (doc.getElementsByTagName("parsererror").length > 0) {
      throw new Error("flatNib: failed to parse composed SVG");
    }

    // Identify a pen-stroke group by its label or unique stroke colour (per the
    // design), NOT by inkscape:groupmode="layer": single-pen generator output
    // (svg_io.lines_to_svg) is a plain <g stroke="…"> with no groupmode/label,
    // and gating on groupmode skipped it entirely so flat pens rendered as a
    // plain round stroke. findMatchingPen fails safe, so unmatched groups
    // (arbitrary imported content) are still left untouched below.
    const groups = Array.from(doc.getElementsByTagNameNS(SVG_NS, "g"));
    for (const g of groups) {
      const label = inkscapeAttr(g, "label");
      const strokeColour = g.getAttribute("stroke");
      const pen = findMatchingPen(label, strokeColour, enabledPens);
      if (!pen || pen.nib_shape !== "flat") continue;

      g.setAttribute("fill", pen.colour);
      g.setAttribute("stroke", "none");
      g.removeAttribute("stroke-width");

      const paths = Array.from(g.getElementsByTagNameNS(SVG_NS, "path"));
      for (const path of paths) {
        const d = path.getAttribute("d");
        if (!d) continue;
        const points = parseCenterline(d);
        const outline = flatNibOutline(points, pen.stroke_mm, pen.start_angle_deg);
        if (outline) path.setAttribute("d", outline);
      }
    }

    return new XMLSerializer().serializeToString(doc);
  } catch {
    return svg;
  }
}
