import { useEffect, useRef } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import type { Change } from "@/api/types";
import { hhmm } from "@/state/dispatch";
import type { Indexed } from "@/lib/schedule";

interface Props {
  view: Indexed;
  changes: Map<string, Change>;
  showChanges: boolean;
  selectedTech: string | null;
  selectedJob: string | null;
  onSelectTech: (id: string) => void;
  onSelectJob: (id: string) => void;
}

const BLUE = "#1d4ed8", AMBER = "#b45309", RED = "#c81e1e", SLATE = "#94a3b8", INK = "#17212f";
const ll = (p: { x_km: number; y_km: number }): L.LatLngExpression => [p.y_km, p.x_km];

/**
 * Offline schematic of the synthetic city grid (Leaflet CRS.Simple, 1 unit = 1 km).
 * No tiles, no geocoding, no road routing: lines show estimated visit order only.
 */
export function RouteMap({ view, changes, showChanges, selectedTech, selectedJob, onSelectTech, onSelectJob }: Props) {
  const el = useRef<HTMLDivElement>(null);
  const map = useRef<L.Map | null>(null);
  const layer = useRef<L.LayerGroup | null>(null);
  const fitted = useRef(false);

  useEffect(() => {
    if (!el.current || map.current) return;
    map.current = L.map(el.current, { crs: L.CRS.Simple, minZoom: 2, maxZoom: 7, zoomSnap: 0.25, attributionControl: false });
    layer.current = L.layerGroup().addTo(map.current);
    const ro = new ResizeObserver(() => map.current?.invalidateSize());
    ro.observe(el.current);
    return () => { ro.disconnect(); map.current?.remove(); map.current = null; fitted.current = false; };
  }, []);

  useEffect(() => {
    const m = map.current, g = layer.current;
    if (!m || !g) return;
    g.clearLayers();
    const pts = [...view.snap.technicians.map((t) => t.location), ...view.snap.jobs.map((j) => j.location)];
    const maxX = Math.max(...pts.map((p) => p.x_km)), maxY = Math.max(...pts.map((p) => p.y_km));
    const W = Math.ceil((maxX + 1) / 5) * 5, H = Math.ceil((maxY + 1) / 5) * 5;
    // Street-grid schematic: service area (every 1 km, stronger every 5 km) plus faint surrounding blocks so the
    // panel reads as a city rather than a small square in empty space.
    const P = 40;
    for (let x = -P; x <= W + P; x++) {
      const inside = x >= 0 && x <= W;
      L.polyline([[-P, x], [H + P, x]], { color: "#dfe3ea", weight: inside && x % 5 === 0 ? 1 : 0.5, opacity: inside ? 1 : 0.6, interactive: false }).addTo(g);
    }
    for (let y = -P; y <= H + P; y++) {
      const inside = y >= 0 && y <= H;
      L.polyline([[y, -P], [y, W + P]], { color: "#dfe3ea", weight: inside && y % 5 === 0 ? 1 : 0.5, opacity: inside ? 1 : 0.6, interactive: false }).addTo(g);
    }
    L.rectangle([[0, 0], [H, W]], { color: "#b8c2d0", weight: 1, fill: true, fillColor: "#ffffff", fillOpacity: 0.55, interactive: false }).addTo(g);
    if (!fitted.current) { m.fitBounds([[-0.5, -0.5], [H + 0.5, W + 0.5]], { padding: [12, 12] }); fitted.current = true; }

    // Routes: home -> jobs in schedule order. Selected technician on top in blue.
    for (const t of view.snap.technicians) {
      const route = view.routes.get(t.id) ?? [];
      if (!route.length) continue;
      const path = [ll(t.location), ...route.map((a) => ll(view.jobs.get(a.job_id)!.location))];
      const sel = selectedTech === t.id;
      const changed = showChanges && route.some((a) => changes.has(a.job_id));
      L.polyline(path, {
        color: sel ? BLUE : changed ? AMBER : SLATE, weight: sel ? 3.5 : changed ? 2.5 : 1.25,
        opacity: sel ? 0.95 : changed ? 0.85 : 0.55, dashArray: changed && !sel ? "6 5" : undefined,
      }).on("click", () => onSelectTech(t.id)).addTo(g);
    }

    // Jobs.
    for (const j of view.snap.jobs) {
      const a = view.byJob.get(j.id);
      const ch = showChanges ? changes.get(j.id) : undefined;
            const color = j.emergency ? RED : ch ? AMBER : a?.frozen ? "#64748b" : a ? BLUE : AMBER;
      const marker = L.circleMarker(ll(j.location), {
        radius: j.emergency ? 8 : selectedJob === j.id ? 7 : 5.5, color: selectedJob === j.id ? INK : "#fff", weight: 2,
        fillColor: color, fillOpacity: a || j.emergency ? 0.95 : 0.6, className: `job-marker job-${j.id}`,
      });
      const tip = `${j.id} · ${j.customer.name}` + (a ? ` · ${hhmm(a.start_min)}` : " · unassigned") + (ch ? ` · ${ch.kind}` : "");
      marker.bindTooltip(tip, { direction: "top", offset: [0, -6], permanent: !!(j.emergency || selectedJob === j.id), className: "text-[11px]" });
      marker.on("click", () => onSelectJob(j.id)).addTo(g);
    }

    // Technician start locations.
    for (const t of view.snap.technicians) {
      const sel = selectedTech === t.id;
      const icon = L.divIcon({
        className: "",
        html: `<div style="width:22px;height:22px;border-radius:5px;background:${sel ? BLUE : "#fff"};color:${sel ? "#fff" : INK};border:1.5px solid ${t.availability === "available" ? BLUE : RED};display:flex;align-items:center;justify-content:center;font:600 10px system-ui">${t.name.slice(0, 2)}</div>`,
        iconSize: [22, 22], iconAnchor: [11, 11],
      });
      L.marker(ll(t.location), { icon, keyboard: true, title: `${t.name} start location` })
        .on("click", () => onSelectTech(t.id)).addTo(g);
    }
  }, [view, changes, showChanges, selectedTech, selectedJob, onSelectTech, onSelectJob]);

  return (
    <div className="relative h-full min-h-[200px]">
      <div ref={el} className="absolute inset-0" role="application" aria-label="Synthetic city map of technicians and jobs" data-testid="route-map" />
      <div className="pointer-events-none absolute right-2 top-2 z-[500] max-w-[60%] rounded bg-panel/90 px-2 py-1 text-[11px] text-muted shadow-sm">
        Synthetic city · 1 km grid · estimated travel, not road routing
      </div>
    </div>
  );
}
