import { studio, pushLog } from "./state.svelte";
import type { Param } from "./types";

async function jget(url: string) {
  const r = await fetch(url);
  if (!r.ok) throw new Error((await r.json().catch(() => ({})))?.error || r.statusText);
  return r.json();
}
async function jpost(url: string, body?: any, method = "POST") {
  const r = await fetch(url, {
    method,
    headers: { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!r.ok) throw new Error((await r.json().catch(() => ({})))?.error || r.statusText);
  return r.json();
}

function paramDefaults(schema: Param[]): Record<string, any> {
  const out: Record<string, any> = {};
  for (const p of schema) out[p.name] = p.default;
  return out;
}

export const api = {
  async boot() {
    const [list, area, pens] = await Promise.all([
      jget("/api/pfm/list"),
      jget("/api/area"),
      jget("/api/pens"),
    ]);
    studio.pfms = list.pfms;
    studio.backend = list.backend;
    studio.area = area.area;
    studio.presets = area.presets;
    studio.drawingSet = pens.drawing_set;
    studio.libraries = pens.libraries;
    await this.selectPfm(studio.pfmId);
    await this.refreshVersions();
  },

  async selectPfm(id: string) {
    studio.pfmId = id;
    const sch = await jget(`/api/pfm/${id}/schema`);
    studio.schema = sch.params;
    studio.params = { ...paramDefaults(sch.params), ...studio.params };
    // drop params not in the new schema
    const keep: Record<string, any> = {};
    for (const p of sch.params) keep[p.name] = studio.params[p.name] ?? p.default;
    studio.params = keep;
  },

  async uploadImage(file: File) {
    const fd = new FormData();
    fd.append("file", file);
    const r = await fetch("/api/image", { method: "POST", body: fd });
    const j = await r.json();
    if (!r.ok) throw new Error(j.error || "upload failed");
    studio.imageUrl = j.data_url;
    studio.imageName = j.name;
    studio.imageW = j.width;
    studio.imageH = j.height;
    pushLog(`Loaded image ${j.name} (${j.width}×${j.height})`);
  },

  async saveArea() {
    if (!studio.area) return;
    await jpost("/api/area", studio.area);
  },

  async savePens() {
    if (!studio.drawingSet) return;
    await jpost("/api/pens", studio.drawingSet);
  },

  async loadLibrary(name: string) {
    const j = await jget(`/api/pens/library/${encodeURIComponent(name)}`);
    if (studio.drawingSet) studio.drawingSet.pens = j.pens;
    await this.savePens();
  },

  async process() {
    if (!studio.imageUrl) {
      pushLog("Load an image first");
      return;
    }
    studio.processing = true;
    studio.status = "Processing";
    studio.progress = 0;
    await this.saveArea();
    await this.savePens();
    await jpost("/api/process", {
      pfm_id: studio.pfmId,
      params: studio.params,
      area: studio.area,
      drawing_set: studio.drawingSet,
    }).catch((e) => {
      studio.processing = false;
      studio.status = "Error";
      pushLog("Process error: " + e.message);
    });
  },

  async refreshVersions() {
    const j = await jget("/api/versions");
    studio.versions = j.versions;
  },

  async saveVersion(name: string, notes: string) {
    await jpost("/api/versions", { name, notes });
    await this.refreshVersions();
  },

  async deleteVersion(id: string) {
    await jpost(`/api/versions/${id}`, undefined, "DELETE");
    await this.refreshVersions();
  },

  async rateVersion(id: string, rating: number) {
    await jpost(`/api/versions/${id}`, { rating }, "PATCH");
    await this.refreshVersions();
  },

  async moveVersion(id: string, direction: number) {
    await jpost(`/api/versions/${id}/move`, { direction });
    await this.refreshVersions();
  },

  async clearVersions() {
    await jpost("/api/versions/clear");
    await this.refreshVersions();
  },

  async loadVersion(id: string) {
    const j = await jpost(`/api/versions/${id}/load`);
    studio.pfmId = j.pfm_id;
    studio.schema = j.schema;
    studio.params = j.params;
    studio.area = j.area;
    studio.drawingSet = j.drawing_set;
    pushLog("Loaded version");
    await this.process();
  },

  exportUrl(split = false) {
    return split ? "/api/export?split=1" : "/api/export";
  },

  async plot() {
    await jpost("/api/plot").catch((e) => pushLog("Plot error: " + e.message));
  },

  async stop() {
    await jpost("/api/stop").catch(() => {});
  },
};

// ── Server-Sent Events: live process + plot progress ────────────────────────────
export function connectStream() {
  const es = new EventSource("/api/stream");
  es.onmessage = (ev) => {
    let m: any;
    try {
      m = JSON.parse(ev.data);
    } catch {
      return;
    }
    if (m.t === "ping") return;
    if (m.t === "proc") handleProc(m);
    else if (m.t === "log") pushLog(m.msg);
    else if (m.t === "state") {
      studio.status = cap(m.state);
      studio.plotting = m.state === "plotting" || m.state === "homing" || m.state === "parsing";
    } else if (m.t === "progress") {
      if (m.total) studio.progress = m.done / m.total;
    } else if (m.t === "error") {
      pushLog("⚠ " + m.msg);
      studio.status = "Error";
    }
  };
  es.onerror = () => {
    /* browser auto-reconnects */
  };
  return es;
}

function handleProc(m: any) {
  if (m.state === "running") {
    studio.processing = true;
    studio.status = "Processing";
  } else if (m.state === "progress") {
    studio.progress = m.frac ?? 0;
    studio.status = "Processing · " + (m.stage ?? "");
  } else if (m.state === "done") {
    studio.processing = false;
    studio.progress = 1;
    studio.status = "Ready";
    studio.previewSvg = m.svg;
    studio.stats = {
      total: m.total,
      length_mm: m.length_mm,
      backend: m.backend,
      per_pen: m.per_pen,
    };
    pushLog(`Generated ${m.total} shapes · ${m.length_mm} mm · ${m.backend}`);
  } else if (m.state === "error") {
    studio.processing = false;
    studio.status = "Error";
    pushLog("Process error: " + m.msg);
  }
}

function cap(s: string) {
  return s ? s[0].toUpperCase() + s.slice(1) : s;
}
