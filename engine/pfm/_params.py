"""Reusable parameter groups for samplers and styles."""

from __future__ import annotations

from ..params import Param

SEED = [Param("seed", "int", 0, group="General", help="Random seed for reproducible output")]

VORONOI_SAMPLER = [
    Param("point_density", "int", 500, group="Voronoi Sampling", min=1, max=1200),
    Param("point_limit", "int", 0, group="Voronoi Sampling", min=0, max=1_000_000,
          help="Hard cap on points (0 = no limit)"),
    Param("luminance_power", "float", 5.0, group="Voronoi Sampling", min=1, max=50),
    Param("density_power", "float", 5.0, group="Voronoi Sampling", min=1, max=50),
    Param("voronoi_iterations", "int", 8, group="Voronoi Sampling", min=1, max=100),
    Param("voronoi_accuracy", "int", 80, group="Voronoi Sampling", min=1, max=100),
    Param("ignore_white", "bool", True, group="Voronoi Sampling"),
]

ADAPTIVE_SAMPLER = [
    Param("min_sample_radius", "float", 1.0, group="Adaptive Sampling", min=0.5, max=100),
    Param("max_sample_radius", "float", 6.0, group="Adaptive Sampling", min=0.5, max=100),
    Param("brightness", "float", 1.0, group="Adaptive Sampling", min=0, max=2),
    Param("contrast", "float", 1.0, group="Adaptive Sampling", min=0, max=2),
    Param("ignore_white", "bool", True, group="Adaptive Sampling"),
]

LBG_SAMPLER = [
    Param("stipple_radius_min", "float", 1.0, group="LBG Sampling", min=0.5, max=100),
    Param("stipple_radius_max", "float", 8.0, group="LBG Sampling", min=0.5, max=100),
    Param("density", "float", 50.0, group="LBG Sampling", min=0, max=100),
    Param("threshold", "float", 0.0, group="LBG Sampling", min=0, max=100),
    Param("max_iterations", "int", 20, group="LBG Sampling", min=1, max=100),
]

POISSON_SAMPLER = [
    Param("min_radius", "float", 2.0, group="Poisson Sampling", min=0.5, max=100,
          help="Minimum centre-to-centre spacing in the darkest areas"),
    Param("max_radius", "float", 10.0, group="Poisson Sampling", min=0.5, max=150,
          help="Spacing used in the lightest areas"),
    Param("candidates", "int", 30, group="Poisson Sampling", min=4, max=100,
          help="Rejection-sample attempts per active point before giving up"),
    Param("point_limit", "int", 0, group="Poisson Sampling", min=0, max=200_000,
          help="Hard cap on points (0 = no limit)"),
    Param("ignore_white", "bool", True, group="Poisson Sampling"),
]

SAMPLER_PARAMS = {
    "voronoi": VORONOI_SAMPLER,
    "adaptive": ADAPTIVE_SAMPLER,
    "lbg": LBG_SAMPLER,
    "poisson": POISSON_SAMPLER,
}


def style_params(style: str) -> list[Param]:
    if style == "stippling":
        return [Param("stipple_size", "float", 30.0, group="Stippling", min=1, max=100)]
    if style == "dashes":
        return [
            Param("stipple_size", "float", 30.0, group="Dashes", min=1, max=100),
            Param("distortion", "float", 40.0, group="Dashes", min=0, max=100),
        ]
    if style == "shapes":
        return [
            Param("shape_type", "enum", "circle", group="Shapes",
                  choices=["circle", "square", "star", "triangle", "cross", "lp", "random"]),
            Param("align_rotation", "bool", False, group="Shapes"),
            Param("min_rotation", "angle", 0.0, group="Shapes", min=0, max=360),
            Param("max_rotation", "angle", 0.0, group="Shapes", min=0, max=360),
            Param("fill_size", "float", 100.0, group="Shapes", min=1, max=400),
        ]
    if style == "triangulation":
        return [Param("triangulate_corners", "bool", False, group="Triangulation")]
    if style == "tree":
        return [Param("create_curves", "bool", False, group="Tree")]
    if style == "diagram":
        return [Param("voronoi_style", "enum", "classic", group="Diagram",
                      choices=["classic", "smooth"])]
    if style == "tsp":
        return [Param("merge_tsp_paths", "bool", True, group="TSP")]
    return []


STYLE_LABELS = {
    "stippling": "Stippling",
    "dashes": "Dashes",
    "shapes": "Shapes",
    "triangulation": "Triangulation",
    "tree": "Tree",
    "diagram": "Diagram",
    "tsp": "TSP",
}

FAMILY_LABELS = {"voronoi": "Voronoi", "adaptive": "Adaptive", "lbg": "LBG", "poisson": "Poisson"}

STYLE_ORDER = ["stippling", "dashes", "shapes", "triangulation", "tree", "diagram", "tsp"]
