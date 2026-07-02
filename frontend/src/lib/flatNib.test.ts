import { nibHalfWidth, flatNibOutline } from "./flatNib.js";

function assertEqual(actual: unknown, expected: unknown, label: string) {
  if (actual !== expected) {
    throw new Error(`${label}: expected ${String(expected)}, got ${String(actual)}`);
  }
}

function assertClose(actual: number, expected: number, label: string) {
  if (Math.abs(actual - expected) > 1e-9) {
    throw new Error(`${label}: expected ${expected}, got ${String(actual)}`);
  }
}

// Perpendicular: nib held at 90deg across horizontal travel (dir 0) lays
// down its full width -> half-width is nibWidthMm / 2.
assertClose(nibHalfWidth(0, 4, 90), 2, "perpendicular nib gives full half-width");

// Parallel: nib held at 0deg along horizontal travel (dir 0) collapses to
// the 0.05mm floor instead of vanishing.
assertClose(nibHalfWidth(0, 4, 0), 0.05, "parallel nib collapses to the floor");

// Right-angle corner: closes cleanly, no NaN.
const corner = flatNibOutline(
  [
    [0, 0],
    [10, 0],
    [10, 10],
  ],
  4,
  30,
);
assertEqual(corner.startsWith("M"), true, "corner outline starts with M");
assertEqual(corner.endsWith("Z"), true, "corner outline ends with Z");
assertEqual(corner.includes("NaN"), false, "corner outline has no NaN");

// Per-segment constant width (no per-vertex averaging that tapered straight
// edges toward corners). L-shape at angle 0: the horizontal run stays a thin
// hairline end-to-end; the vertical run stays full nib width end-to-end.
const L = flatNibOutline(
  [
    [0, 0],
    [10, 0],
    [10, 10],
  ],
  4,
  0,
);
assertEqual((L.match(/M/g) || []).length, 2, "one quad per segment");
// horizontal segment (dir 0, parallel to nib) -> 0.05 half-width, uniform
assertEqual(L.includes("M0,0.05 L10,0.05"), true, "horizontal edge is a uniform thin hairline");
// vertical segment (dir 90, perpendicular) -> full 2mm half-width (x = 10 ± 2)
assertEqual(L.includes("M8,0 L8,10 L12,10 L12,0"), true, "vertical edge is uniform full nib width");

console.log("flat nib ok");
