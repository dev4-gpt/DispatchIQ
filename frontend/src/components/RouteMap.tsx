import { useEffect, useRef, useState } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import type { Change, Job } from "@/api/types";
import { hhmm } from "@/state/dispatch";
import type { Indexed } from "@/lib/schedule";
import { Dialog, DialogContent } from "@/components/ui/dialog";

interface Props {
  view: Indexed;
  changes: Map<string, Change>;
  showChanges: boolean;
  selectedTech: string | null;
  selectedJob: string | null;
  onSelectTech: (id: string) => void;
  onSelectJob: (id: string) => void;
}

const BLUE = "#285cd7",
  AMBER = "#965600";
const ll = (p: { x_km: number; y_km: number }): L.LatLngExpression => [
  p.y_km,
  p.x_km,
];

/**
 * Offline schematic of the synthetic city grid (Leaflet CRS.Simple, 1 unit = 1 km).
 * No tiles, no geocoding, no road routing: lines show estimated visit order only.
 */
export function RouteMap({
  view,
  changes,
  showChanges,
  selectedTech,
  selectedJob,
  onSelectTech,
  onSelectJob,
}: Props) {
  const el = useRef<HTMLDivElement>(null);
  const map = useRef<L.Map | null>(null);
  const layer = useRef<L.LayerGroup | null>(null);
  const fitted = useRef(false);
  const [zoom, setZoom] = useState(0);
  const [clusterJobs, setClusterJobs] = useState<string[] | null>(null);
  const pickedClusterJob = useRef(false);

  useEffect(() => {
    if (!el.current || map.current) return;
    map.current = L.map(el.current, {
      crs: L.CRS.Simple,
      minZoom: 1,
      maxZoom: 7,
      zoomSnap: 0.25,
      attributionControl: false,
    });
    layer.current = L.layerGroup().addTo(map.current);
    map.current.on("zoomend", () => setZoom(map.current?.getZoom() ?? 0));
    const ro = new ResizeObserver(() => map.current?.invalidateSize());
    ro.observe(el.current);
    return () => {
      ro.disconnect();
      map.current?.remove();
      map.current = null;
      fitted.current = false;
    };
  }, []);

  useEffect(() => {
    const m = map.current,
      g = layer.current;
    if (!m || !g) return;
    g.clearLayers();
    const pts = [
      ...view.snap.technicians.map((t) => t.location),
      ...view.snap.jobs.map((j) => j.location),
    ];
    const maxX = Math.max(...pts.map((p) => p.x_km)),
      maxY = Math.max(...pts.map((p) => p.y_km));
    const W = Math.ceil((maxX + 1) / 5) * 5,
      H = Math.ceil((maxY + 1) / 5) * 5;
    // Street-grid schematic: service area (every 1 km, stronger every 5 km) plus faint surrounding blocks so the
    // panel reads as a city rather than a small square in empty space.
    const P = 40;
    for (let x = -P; x <= W + P; x++) {
      const inside = x >= 0 && x <= W;
      L.polyline(
        [
          [-P, x],
          [H + P, x],
        ],
        {
          color: "#dfe3ea",
          weight: inside && x % 5 === 0 ? 1 : 0.5,
          opacity: inside ? 1 : 0.6,
          interactive: false,
        },
      ).addTo(g);
    }
    for (let y = -P; y <= H + P; y++) {
      const inside = y >= 0 && y <= H;
      L.polyline(
        [
          [y, -P],
          [y, W + P],
        ],
        {
          color: "#dfe3ea",
          weight: inside && y % 5 === 0 ? 1 : 0.5,
          opacity: inside ? 1 : 0.6,
          interactive: false,
        },
      ).addTo(g);
    }
    L.rectangle(
      [
        [0, 0],
        [H, W],
      ],
      {
        color: "#b8c2d0",
        weight: 1,
        fill: true,
        fillColor: "#ffffff",
        fillOpacity: 0.55,
        interactive: false,
      },
    ).addTo(g);
    if (!fitted.current) {
      m.fitBounds(
        [
          [-1, -1],
          [H + 1, W + 1],
        ],
        { paddingTopLeft: [40, 35], paddingBottomRight: [30, 15] },
      );
      fitted.current = true;
    }

    // Routes: home -> jobs in schedule order. Selected technician on top in blue.
    for (const t of view.snap.technicians) {
      const route = view.routes.get(t.id) ?? [];
      if (!route.length) continue;
      const path = [
        ll(t.location),
        ...route.map((a) => ll(view.jobs.get(a.job_id)!.location)),
      ];
      const sel = selectedTech === t.id;
      const changed = showChanges && route.some((a) => changes.has(a.job_id));
      if (!sel && !changed) continue;
      L.polyline(path, {
        color: changed ? AMBER : BLUE,
        weight: 2,
        opacity: 0.8,
        dashArray: changed ? "6 5" : undefined,
      })
        .on("click", () => onSelectTech(t.id))
        .addTo(g);
    }

    // Nearby points cluster at this zoom. Selected items stay at their exact coordinate.
    const groups: Job[][] = [];
    for (const j of view.snap.jobs) {
      const point = m.latLngToContainerPoint(ll(j.location));
      const group =
        j.id === selectedJob || j.emergency
          ? undefined
          : groups.find(
              (items) =>
                items[0].id !== selectedJob &&
                !items[0].emergency &&
                m
                  .latLngToContainerPoint(ll(items[0].location))
                  .distanceTo(point) < 24,
            );
      if (group) group.push(j);
      else groups.push([j]);
    }
    for (const jobs of groups) {
      const j =
        jobs.find((x) => x.id === selectedJob) ??
        jobs.find((x) => x.emergency) ??
        jobs[0];
      const chosen = jobs.some((x) => x.id === selectedJob);
      const changed = showChanges && jobs.some((x) => changes.has(x.id));
      const label = document.createElement("span");
      label.className = `map-job-marker${chosen ? " selected" : ""}${j.emergency ? " emergency" : changed ? " changed" : ""}`;
      label.textContent = j.emergency
        ? "!"
        : jobs.length > 1
          ? String(jobs.length)
          : "";
      const icon = L.divIcon({
        className: `job-marker ${jobs.map((x) => `job-${x.id}`).join(" ")}`,
        html: label,
        iconSize: [jobs.length > 1 ? 17 : 12, 17],
        iconAnchor: [jobs.length > 1 ? 8 : 6, 8],
      });
      const marker = L.marker(ll(j.location), {
        icon,
        keyboard: true,
        title: `${jobs.length} appointment(s) in this area`,
      }).addTo(g);
      marker
        .getElement()
        ?.setAttribute(
          "aria-label",
          jobs.length === 1
            ? `${j.id}, ${j.customer.name}, job location`
            : `${jobs.length} appointments in this area. Open job list.`,
        );
      const tooltip = document.createElement("span");
      const a = view.byJob.get(j.id);
      tooltip.textContent =
        chosen || j.emergency || jobs.length === 1
          ? `${j.id} · ${j.customer.name}${a ? ` · ${hhmm(a.start_min)}` : " · unassigned"}`
          : `${jobs.length} appointments in this area`;
      marker.bindTooltip(tooltip, {
        direction: "top",
        offset: [0, -10],
        permanent: j.emergency || chosen,
      });
      marker.on("click", () => {
        if (jobs.length === 1) onSelectJob(j.id);
        else {
          pickedClusterJob.current = false;
          setClusterJobs(jobs.map((job) => job.id));
        }
      });
    }

    // Base labels sit to the left of each point; alternating offsets avoid dense-label collisions.
    const occupied: L.Point[] = [];
    for (const t of view.snap.technicians) {
      const sel = selectedTech === t.id;
      const node = document.createElement("div");
      node.className = `map-base-marker${sel ? " selected" : ""}`;
      node.textContent = sel ? t.name.slice(0, 2) : t.name.slice(0, 1);
      const point = m.latLngToContainerPoint(ll(t.location));
      let anchorX = 35,
        anchorY = 11;
      while (
        occupied.some(
          (p) =>
            p.distanceTo(
              L.point(point.x - anchorX + 9, point.y - anchorY + 9),
            ) < 20,
        )
      ) {
        anchorX += 20;
        anchorY += 2;
      }
      occupied.push(L.point(point.x - anchorX + 9, point.y - anchorY + 9));
      if (anchorX > 35)
        L.polyline(
          [
            ll(t.location),
            m.containerPointToLatLng([
              point.x - anchorX + 9,
              point.y - anchorY + 9,
            ]),
          ],
          { color: "#b4c0d2", weight: 0.5, interactive: false },
        ).addTo(g);
      const icon = L.divIcon({
        className: "",
        html: node,
        iconSize: [18, 18],
        iconAnchor: [anchorX, anchorY],
      });
      const baseMarker = L.marker(ll(t.location), {
        icon,
        keyboard: true,
        title: `${t.name} start location`,
      })
        .on("click", () => onSelectTech(t.id))
        .addTo(g);
      baseMarker
        .getElement()
        ?.setAttribute("aria-label", `${t.name}, technician base`);
    }
  }, [
    view,
    changes,
    showChanges,
    selectedTech,
    selectedJob,
    onSelectTech,
    onSelectJob,
    zoom,
  ]);

  return (
    <div className="relative h-full">
      <div
        ref={el}
        className="absolute inset-0"
        role="application"
        aria-label="Synthetic city map of technicians and jobs"
        data-testid="route-map"
      />
      <div className="pointer-events-none absolute bottom-2 left-3 z-[500] text-[9px] text-muted">
        Square: technician base · Circle: jobs (grouped nearby) · Estimated
        visit order
      </div>
      <Dialog
        open={clusterJobs !== null}
        onOpenChange={(open) => !open && setClusterJobs(null)}
      >
        <DialogContent
          title="Appointments in this area"
          description="Nearby points are grouped at this map zoom. Select an appointment to see its exact location and schedule."
          onCloseAutoFocus={(event) => {
            event.preventDefault();
            if (!pickedClusterJob.current) el.current?.focus();
          }}
        >
          <div className="map-popup-jobs cluster-job-list">
            {clusterJobs?.map((id) => {
              const job = view.jobs.get(id);
              const assignment = view.byJob.get(id);
              if (!job) return null;
              return (
                <button
                  key={id}
                  onClick={() => {
                    pickedClusterJob.current = true;
                    setClusterJobs(null);
                    onSelectJob(id);
                  }}
                >
                  <span>
                    <strong>{id}</strong> · {job.customer.name}
                  </span>
                  <small>
                    {assignment
                      ? `${view.techs.get(assignment.technician_id)?.name ?? assignment.technician_id} · ${hhmm(assignment.start_min)}–${hhmm(assignment.end_min)}`
                      : "Not assigned"}
                  </small>
                </button>
              );
            })}
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
