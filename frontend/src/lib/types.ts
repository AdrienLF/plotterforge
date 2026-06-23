export interface Param {
  name: string;
  type: "float" | "int" | "bool" | "enum" | "angle";
  default: any;
  label: string;
  group: string;
  min: number | null;
  max: number | null;
  step: number | null;
  choices: string[] | null;
  help: string;
}

export interface PfmInfo {
  id: string;
  name: string;
  family: string;
  style: string;
}

export interface Pen {
  name: string;
  type: string;
  colour: string;
  weight: number;
  stroke_mm: number;
  enabled: boolean;
}

export interface DrawingSetT {
  pens: Pen[];
  distribution_type: string;
  distribution_order: string;
}

export interface AreaT {
  use_original_sizing: boolean;
  units: string;
  width: number;
  height: number;
  orientation: string;
  pad_left: number;
  pad_right: number;
  pad_top: number;
  pad_bottom: number;
  scaling_mode: string;
  rescale_to_pen_width: boolean;
  rescale_mode: string;
  pen_width_mm: number;
  canvas_colour: string;
  background_colour: string;
  clipping: string;
}

export interface VersionT {
  id: string;
  name: string;
  pfm_id: string;
  rating: number;
  notes: string;
  timestamp: number;
  thumbnail: string;
}

export interface Stats {
  total: number;
  length_mm: number;
  backend: string;
  per_pen: { name: string; colour: string; count: number }[];
}
