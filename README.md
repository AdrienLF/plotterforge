# raster-to-plotter-svg

Converts a raster image into a plotter-ready SVG of filled circles. Transparency is respected — clear areas produce no dots. A live GUI lets you tune every parameter before exporting.

![screenshot placeholder](docs/screenshot.png)

## Plotter Studio (web app)

A professional, DrawingBotV3-style studio lives in `engine/` (the conversion
engine) + `frontend/` (a Svelte 5 SPA) + `web/server.py` (Flask API + plotter
driver). It offers a library of configurable **Path Finding Modules**, a
**Drawing Area** model, multi-pen **Drawing Sets**, and snapshot **Version
Control** — with optional GPU acceleration.

```sh
# Windows:  setup-windows.bat      then  start-studio.bat
# macOS:    ./setup-macos.command  then  ./start-studio.command
```

Setup prepares everything once (locked PyTorch, SAM2, checkpoint, frontend); the
launchers are offline and just start the prepared server. See **Full setup** and
**Launch** below.

For frontend development with hot-reload: `cd frontend && npm run dev` (proxies
`/api` to the Flask server).

- **Path Finding Modules (first wave, ~23):** Voronoi / LBG / Adaptive samplers ×
  Stippling, Dashes, Shapes, Triangulation, Tree, Diagram, TSP styles, plus the
  ported Grid Halftone and Random Stipple. Every module's settings are
  auto-generated from a typed schema (`engine/params.py`).
- **GPU-first:** setup installs the platform PyTorch build (CUDA on Windows, MPS
  on macOS). `engine/accel.py` uses Torch for the heavy nearest-site /
  weighted-centroid stages when available, falling back to numpy/scipy only when
  GPU support is not available. The status bar shows the active backend.
- **Integration:** a module produces a `Drawing` → `engine/svg_io.py` writes a
  multi-layer mm SVG → the existing `_plot_worker` in `web/server.py` plots it,
  unchanged. Projects/versions are stored under `~/.plotter_studio/`.

## Requirements

- Windows 10/11 with an NVIDIA GPU and current driver, or macOS with MPS-capable hardware
- [uv](https://docs.astral.sh/uv/)
- Node.js and npm

Python 3.13 is installed and managed by uv. Conda is not used.

## Full setup

Windows: `setup-windows.bat`

macOS: `./setup-macos.command`

Full setup installs the platform PyTorch build, pinned SAM2, the default checkpoint,
frontend dependencies, and verifies a real segmentation inference before succeeding.

## Launch

Windows: `start-studio.bat`

macOS: `./start-studio.command`

Launch is offline and never installs, syncs, builds, downloads, or kills processes.
Rerun the platform setup script after dependency or frontend changes.

## Recovery

- **`uv` or Node.js not found** — install them, then rerun the platform setup script.
- **`Run setup-windows.bat first.` / `Run ./setup-macos.command first.`** — the `.venv`
  is missing or stale; rerun the platform setup script to rebuild it from the lock.
- **`Port 7438 is already in use by PID …`** — another studio is running; stop that PID
  and relaunch (launchers never kill the port owner).
- **CUDA/MPS unavailable** — `web.env_check` reports it; check your GPU driver (Windows)
  or that you are on MPS-capable hardware (macOS), then rerun setup.
- **`Plotter Studio setup is incomplete: missing …`** — SAM2, Torch, or the checkpoint
  is absent at runtime; rerun the platform setup script (the server never installs it).

## Legacy GUI

```sh
uv run python main.py
```

1. **Load image** — PNG, JPG, BMP, TIFF, WebP. Images with an alpha channel are supported; transparent pixels are skipped.
2. **Choose an algorithm** and tune its parameters (see below).
3. **Set physical width (mm)** to match the paper you'll plot on. Height is derived from the image aspect ratio.
4. Press **▶ Preview** to compute and render the dots.
5. Press **Export SVG…** to save.

## Algorithms

### Grid halftone

Dots are placed on a regular grid. Each cell's average brightness determines the dot radius — dark cells get large dots, bright cells get small ones.

| Parameter | Description |
|---|---|
| Grid spacing (px) | Distance between dot centres. Smaller = finer detail, more dots. |
| Min dot radius (px) | Radius used for the lightest cells. Set to 0 to leave bright areas empty. |
| Max dot radius (px) | Radius used for the darkest cells. Should stay below half the grid spacing to avoid overlap. |

### Random stipple

Dots are scattered randomly across the image. Darker areas attract proportionally more dots. All dots share the same radius, matching a fixed pen-tip diameter.

| Parameter | Description |
|---|---|
| Dot count | Total number of dots to place. More dots = denser, finer result. |
| Dot radius (px) | Radius of every dot. Set this to match your pen tip (see tip below). |
| Position jitter (px) | Random offset added to each dot's position. Breaks up the pixel-grid look at high dot counts. |

### Matching dot radius to pen size

The SVG is output in millimetres. To size dots so they just touch without overlapping, set dot radius to half your pen tip width in the units of the source image:

```
dot_radius_px = (pen_tip_mm / output_width_mm) * image_width_px / 2
```

## SVG output

The exported file uses `mm` units and a `viewBox` matching the requested physical dimensions. Every dot is a `<circle>` element with `fill="black"`. Load the file directly into Inkscape, LightBurn, or your plotter's control software and set the pen stroke to match.

## Wireless plotting from Inkscape

The iDraw H A3 lives on the Raspberry Pi (`pi-atelier`, USB `/dev/ttyACM0`), but
you can still drive it from **Inkscape + the UUNA TEK extension on the Mac**
wirelessly. A `socat` bridge over Tailscale gives the Mac a virtual serial port
(`~/.idraw-tty`) that is really the Pi's USB port, and a small patch lets the
extension accept that virtual port.

Full one-time setup (Pi service, Mac LaunchAgent, extension patch) is in
[`bridge/README.md`](bridge/README.md). Once that's done, day-to-day connecting is:

1. **Make sure the bridge is up** (it auto-starts at login):
   ```sh
   launchctl list | grep idraw     # second column 0 = running
   ls -l ~/.idraw-tty              # the virtual serial port exists
   ```
   If it isn't running: `launchctl load ~/Library/LaunchAgents/com.idraw.bridge.plist`
2. **In Inkscape**, open the UUNA TEK / iDraw extension → **Setup** tab.
3. Set the connection to **"use a specified port"** (not "first available") and
   enter the port:
   ```
   /Users/adrien/.idraw-tty
   ```
4. Run **Apply / Plot** as usual. Homing, jogging and plotting all work exactly as
   over USB.

Notes:
- The plotter must be powered on and connected to the Pi, and Tailscale must be up
  on both machines.
- While the bridge is running it holds the Pi's serial port, so the Flask web UI
  (`web/`) can't be used at the same time — stop the bridge to switch (see
  `bridge/README.md`).
- If Inkscape says **"Failed to connect to iDraw2 …"** after an extension update,
  re-apply the patch: `python3 bridge/patch-idraw-extension.py`.

## Project layout

```
engine/        Plotter Studio engine: PFMs, samplers, styles, pens, drawing area,
               version control, GPU/CPU backend, SVG output
frontend/      Svelte 5 SPA (Photoshop-style UI); `npm run build` → web/static/app
web/           Flask API + plotter driver (serves the SPA, runs the engine, plots)
main.py        Legacy GUI application (customtkinter)
stipple.py     legacy grid_halftone()/random_stipple() — superseded by engine/pfm/grid.py
svg_export.py  legacy export_svg() — superseded by engine/svg_io.py
pyproject.toml uv project manifest (engine + web deps; `cuda`/`mps` + `sam2` extras add Torch/SAM2)
uv.lock        locked dependency tree
bridge/        wireless serial bridge: drive the plotter from Mac Inkscape (see bridge/README.md)
```
