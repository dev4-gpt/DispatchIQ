import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { AlertTriangle, CalendarClock, ClipboardCheck, FlaskConical, Map as MapIcon, RefreshCw, Siren, Users, X } from "lucide-react";
import { useDispatch } from "@/state/useDispatch";
import { hhmm, visibleSnapshot, type View } from "@/state/dispatch";
import { changesByJob, index } from "@/lib/schedule";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { RouteMap } from "@/components/RouteMap";
import { ScheduleBoard } from "@/components/ScheduleBoard";
import { MetricsStrip } from "@/components/MetricsStrip";
import { TechnicianList } from "@/components/TechnicianList";
import { WorkforcePanel } from "@/components/WorkforcePanel";
import { TYPE_ORDER, WORKER, workerType } from "@/lib/workers";
import { JobInspector } from "@/components/JobInspector";
import { ProposalPanel } from "@/components/ProposalPanel";
import { ScenarioControls } from "@/components/ScenarioControls";

function useLayout() {
  const q = () => (window.innerWidth >= 1280 ? "desktop" : window.innerWidth >= 900 ? "tablet" : "mobile");
  const [mode, setMode] = useState<"desktop" | "tablet" | "mobile">(q);
  useEffect(() => {
    const on = () => setMode(q());
    window.addEventListener("resize", on);
    return () => window.removeEventListener("resize", on);
  }, []);
  return mode;
}

function Panel({ title, actions, children, className, id }: { title: string; actions?: ReactNode; children: ReactNode; className?: string; id?: string }) {
  return (
    <section id={id} tabIndex={-1} aria-label={title} className={cn("flex min-h-0 flex-col overflow-hidden rounded-[12px] border border-line bg-panel", className)}>
      <header className="flex h-10 shrink-0 items-center justify-between gap-2 border-b border-line px-3">
        <h2 className="text-[13px] font-semibold">{title}</h2>
        {actions}
      </header>
      <div className="min-h-0 flex-1">{children}</div>
    </section>
  );
}

export default function App() {
  const { state, dispatch, transport, backend, preview, commit, reject, reset, refresh } = useDispatch();
  const layout = useLayout();
  const snap = visibleSnapshot(state);
  const view = useMemo(() => (snap ? index(snap) : null), [snap]);
  const committed = useMemo(() => (state.snapshot ? index(state.snapshot) : null), [state.snapshot]);
  const proposedIdx = useMemo(() => (state.proposal?.proposed_snapshot ? index(state.proposal.proposed_snapshot) : null), [state.proposal]);
  const changes = useMemo(() => changesByJob(state.proposal), [state.proposal]);
  const showChanges = state.view === "proposed" && !!state.proposal?.proposed_snapshot;

  const selectTech = useCallback((id: string) => dispatch({ type: "selectTech", id }), [dispatch]);
  const selectJob = useCallback((id: string) => dispatch({ type: "selectJob", id }), [dispatch]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape" && layout === "desktop") dispatch({ type: "closeInspector" }); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [dispatch, layout]);

  const s = state.snapshot;
  const now = s?.now_min ?? 0;
  const available = s?.technicians.filter((t) => t.availability === "available").length ?? 0;
  const inProgress = s?.jobs.filter((j) => j.status === "in_progress").length ?? 0;
  const emergencies = s?.jobs.filter((j) => j.emergency).length ?? 0;
  const fixture = transport?.kind === "dev-fixture";

  const inspectorBody = committed && (
    <div className="space-y-5 p-4">
      {state.error && state.error.scope !== "load" && (
        <div role="alert" className="flex items-start gap-2 rounded-md border border-emergency/30 bg-emergency-soft p-2.5 text-[12px] text-emergency">
          <AlertTriangle className="mt-0.5 size-3.5 shrink-0" />
          <div className="flex-1">{state.error.message}</div>
          <button aria-label="Dismiss error" onClick={() => dispatch({ type: "clearError" })}><X className="size-3.5" /></button>
        </div>
      )}
      {state.busy === "previewing" && (
        <p role="status" className="flex items-center gap-2 text-[12.5px] text-muted"><RefreshCw className="size-3.5 animate-spin" /> Evaluating technicians and insertion slots…</p>
      )}
      {state.proposal && (
        <ProposalPanel proposal={state.proposal} strategy={state.proposalStrategy} committed={committed} stale={state.proposalStale} busy={state.busy}
          onApprove={commit} onReject={reject} onRefresh={refresh} onSelectJob={selectJob} />
      )}
      {state.selectedJob && (
        <JobInspector jobId={state.selectedJob} committed={committed} proposed={proposedIdx} proposal={state.proposal} />
      )}
      {!state.proposal && !state.selectedJob && state.busy !== "previewing" && (
        <div className="space-y-2 text-[12.5px] text-muted">
          <p>Select a job on the map or timeline to inspect it, or introduce an emergency to preview a re-plan.</p>
          <p>Nothing changes in the committed schedule until a dispatcher approves a proposal.</p>
        </div>
      )}
    </div>
  );

  const viewTabs = (
    <Tabs value={state.view} onValueChange={(v) => dispatch({ type: "view", view: v as View })}>
      <TabsList aria-label="Schedule version">
        <TabsTrigger value="baseline"><span className="max-[899px]:hidden">Start of day</span><span className="min-[900px]:hidden">Start</span></TabsTrigger>
        <TabsTrigger value="committed">Committed</TabsTrigger>
        <TabsTrigger value="proposed" disabled={!state.proposal?.proposed_snapshot} data-testid="view-proposed">Proposed</TabsTrigger>
      </TabsList>
    </Tabs>
  );

  const mapPanel = view && (
    <Panel id="map" title="Map" className="h-full" actions={<span className="text-[11px] text-muted">Click a technician or job</span>}>
      <RouteMap view={view} changes={changes} showChanges={showChanges} selectedTech={state.selectedTech}
        selectedJob={state.selectedJob} onSelectTech={selectTech} onSelectJob={selectJob} />
    </Panel>
  );
  const boardPanel = view && committed && (
    <Panel id="schedule" title={layout === "mobile" ? `Schedule · rev ${snap?.revision}` : `Schedule · ${state.view === "baseline" ? "start of day" : state.view} · rev ${snap?.revision}`} className="h-full" actions={viewTabs}>
      <ScheduleBoard view={view} committed={committed} changes={changes} showChanges={showChanges}
        selectedTech={state.selectedTech} selectedJob={state.selectedJob} onSelectTech={selectTech} onSelectJob={selectJob} />
    </Panel>
  );

  const inspectorOpen = state.inspectorOpen || !!state.proposal || state.busy === "previewing";

  return (
    <div className="flex h-full flex-col overflow-x-hidden">
      <div aria-live="polite" className="sr-only" data-testid="announce">{state.announce}</div>
      {fixture && (
        <div role="note" className="flex items-center justify-center gap-2 bg-proposed px-3 py-1 text-[12px] font-medium text-white" data-testid="fixture-banner">
          <FlaskConical className="size-3.5" /> Development fixture: in-browser stand-in for the dispatch API. Not backend results.
        </div>
      )}
      <header className="flex min-h-16 shrink-0 flex-wrap items-center gap-x-4 gap-y-2 border-b border-line bg-panel px-4 py-2 max-[899px]:px-3">
        <div className="flex items-center gap-2">
          <img src={`${import.meta.env.BASE_URL}favicon.svg`} alt="" className="size-7" />
          <div>
            <h1 className="text-[15px] font-semibold leading-tight">DispatchIQ</h1>
            <p className="tabular text-[11px] text-muted">{s ? `${s.date} · ${hhmm(now)} simulated` : "—"}</p>
          </div>
        </div>
        {s && (
          <div className="flex flex-wrap items-center gap-1.5 text-[12px]">
            <Badge tone="blue"><Users /> {available}/{s.technicians.length} available</Badge>
            {TYPE_ORDER.map((w) => {
              const n = s.technicians.filter((t) => workerType(t) === w).length;
              const I = WORKER[w].icon;
              return n ? <Badge key={w} data-testid={`mix-${w}`}><I /> {n} {w === "agent" ? (n === 1 ? "AI agent" : "AI agents") : n === 1 ? WORKER[w].label.toLowerCase() : WORKER[w].plural.toLowerCase()}</Badge> : null;
            })}
            <Badge><CalendarClock /> {inProgress} in progress</Badge>
            <Badge tone={emergencies ? "red" : "neutral"}><Siren /> {emergencies} emergencies</Badge>
            <Badge tone="neutral" className="tabular">rev {s.revision}</Badge>
          </div>
        )}
        <div className="ml-auto flex flex-wrap items-center gap-x-3 gap-y-2 max-[899px]:ml-0 max-[899px]:w-full max-[899px]:justify-between">
          <span className={cn("flex items-center gap-1.5 text-[12px]", backend.ok ? "text-ok" : "text-emergency")} data-testid="backend-status">
            <span className={cn("size-2 rounded-full", backend.ok ? "bg-ok" : "bg-emergency")} /> {backend.label}
          </span>
          <ScenarioControls snapshot={s} busy={state.busy} hasOpenProposal={!!state.proposal && !state.proposalStale && state.proposal.status === "ready"}
            onPreview={(e, st) => preview(e, st)} onReset={reset} />
        </div>
      </header>

      {state.error?.scope === "load" && (
        <div role="alert" className="m-4 flex items-center gap-3 rounded-[12px] border border-emergency/30 bg-emergency-soft p-3 text-[13px] text-emergency" data-testid="load-error">
          <AlertTriangle className="size-4" /> {state.error.message}
          <Button size="sm" onClick={refresh}><RefreshCw /> Retry</Button>
        </div>
      )}
      {!s && state.busy === "loading" && <p role="status" className="p-6 text-muted">Loading committed schedule…</p>}

      {view && committed && s && (
        layout === "mobile" ? (
          <div className="flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto p-3">
            <MetricsStrip committed={s.metrics} proposal={state.proposal} strategy={state.proposalStrategy} />
            <Tabs defaultValue="timeline" className="flex flex-col">
              <TabsList className="self-start">
                <TabsTrigger value="timeline"><CalendarClock /> Timeline</TabsTrigger>
                <TabsTrigger value="map"><MapIcon /> Map</TabsTrigger>
                <TabsTrigger value="details"><ClipboardCheck /> Details{state.proposal ? " •" : ""}</TabsTrigger>
              </TabsList>
              <TabsContent value="timeline" className="mt-2 h-[560px]">{boardPanel}</TabsContent>
              <TabsContent value="map" className="mt-2 h-[460px]">{mapPanel}</TabsContent>
              <TabsContent value="details" className="mt-2 space-y-3 rounded-[12px] border border-line bg-panel">
                {inspectorBody}
                <div className="border-t border-line p-2"><WorkforcePanel view={view} /></div>
              </TabsContent>
            </Tabs>
          </div>
        ) : (
          <div className={cn("grid min-h-0 flex-1 gap-3 p-3", layout === "desktop"
            ? inspectorOpen ? "grid-cols-[200px_minmax(0,1fr)_340px]" : "grid-cols-[200px_minmax(0,1fr)]"
            : "grid-cols-[minmax(0,1fr)]")}>
            {layout === "desktop" && (
              <nav aria-label="Workspace" className="flex min-h-0 flex-col overflow-hidden rounded-[12px] border border-line bg-panel">
                <div className="space-y-0.5 border-b border-line p-2">
                  {[["map", MapIcon, "Map"], ["schedule", CalendarClock, "Schedule"]].map(([id, Icon, label]) => {
                    const I = Icon as typeof MapIcon;
                    return (
                      <button key={id as string} onClick={() => document.getElementById(id as string)?.focus()}
                        className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-[13px] hover:bg-canvas">
                        <I className="size-4 text-muted" /> {label as string}
                      </button>
                    );
                  })}
                </div>
                <div className="min-h-0 flex-1 space-y-3 overflow-y-auto p-2">
                  <WorkforcePanel view={view} />
                  <TechnicianList view={view} selectedTech={state.selectedTech} onSelectTech={selectTech} />
                </div>
              </nav>
            )}
            <main className="grid min-h-0 grid-rows-[auto_minmax(180px,2fr)_minmax(260px,3fr)] gap-3">
              <MetricsStrip committed={s.metrics} proposal={state.proposal} strategy={state.proposalStrategy} />
              {mapPanel}
              {boardPanel}
            </main>
            {layout === "desktop" && inspectorOpen && (
              <aside aria-label="Inspector" className="relative min-h-0 overflow-y-auto rounded-[12px] border border-line bg-panel" data-testid="inspector">
                <button aria-label="Close inspector (Escape)" onClick={() => dispatch({ type: "closeInspector" })}
                  className="absolute right-2 top-2 z-10 rounded p-1 text-muted hover:bg-canvas"><X className="size-4" /></button>
                {inspectorBody}
              </aside>
            )}
            {layout === "tablet" && (
              <Dialog open={inspectorOpen} onOpenChange={(o) => !o && dispatch({ type: "closeInspector" })}>
                <DialogContent side="right" title={state.proposal ? "Proposal" : "Details"} aria-describedby={undefined}>
                  <div className="min-h-0 flex-1 overflow-y-auto" data-testid="inspector">{inspectorBody}</div>
                </DialogContent>
              </Dialog>
            )}
          </div>
        )
      )}
    </div>
  );
}
