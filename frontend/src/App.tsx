import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Activity,
  AlertTriangle,
  CalendarDays,
  CheckCheck,
  ChevronRight,
  ClipboardList,
  FlaskConical,
  LayoutDashboard,
  Map as MapIcon,
  Menu,
  Radio,
  RefreshCw,
  ShieldCheck,
  Users,
  X,
} from "lucide-react";
import { useDispatch } from "@/state/useDispatch";
import { hhmm, visibleSnapshot, type View } from "@/state/dispatch";
import { changesByJob, index } from "@/lib/schedule";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { RouteMap } from "@/components/RouteMap";
import { ScheduleBoard } from "@/components/ScheduleBoard";
import { JobInspector } from "@/components/JobInspector";
import { ProposalPanel } from "@/components/ProposalPanel";
import { ScenarioControls } from "@/components/ScenarioControls";
import {
  OperationsPages,
  TechnicianInspector,
  type Destination,
} from "@/components/OperationsPages";

const destinations = [
  { id: "overview", label: "Overview", icon: LayoutDashboard },
  { id: "dispatch", label: "Dispatch Board", icon: CalendarDays },
  { id: "jobs", label: "Jobs", icon: ClipboardList },
  { id: "technicians", label: "Technicians", icon: Users },
  { id: "activity", label: "Activity", icon: Activity },
] as const;

function useLayout() {
  const read = () =>
    window.innerWidth >= 1360
      ? "desktop"
      : window.innerWidth >= 768
        ? "tablet"
        : "mobile";
  const [layout, setLayout] = useState(read);
  useEffect(() => {
    const update = () => setLayout(read());
    window.addEventListener("resize", update);
    return () => window.removeEventListener("resize", update);
  }, []);
  return layout;
}

export default function App() {
  const {
    state,
    dispatch,
    transport,
    backend,
    preview,
    commit,
    reject,
    reset,
    refresh,
  } = useDispatch();
  const layout = useLayout();
  const [destination, setDestination] = useState<Destination>("dispatch");
  const [navOpen, setNavOpen] = useState(false);
  const [mobileView, setMobileView] = useState("timeline");
  const [mapExpanded, setMapExpanded] = useState(false);
  const snapshot = state.snapshot;
  const snap = visibleSnapshot(state);
  const view = useMemo(() => (snap ? index(snap) : null), [snap]);
  const committed = useMemo(
    () => (snapshot ? index(snapshot) : null),
    [snapshot],
  );
  const proposed = useMemo(
    () =>
      state.proposal?.proposed_snapshot
        ? index(state.proposal.proposed_snapshot)
        : null,
    [state.proposal],
  );
  const changes = useMemo(() => changesByJob(state.proposal), [state.proposal]);
  const showChanges = state.view === "proposed" && !!proposed;
  const selectTech = useCallback(
    (id: string) => dispatch({ type: "selectTech", id }),
    [dispatch],
  );
  const selectJob = useCallback(
    (id: string) => dispatch({ type: "selectJob", id }),
    [dispatch],
  );
  const inspectorOpen = state.inspectorOpen || state.busy === "previewing";
  const navigate = (id: Destination) => {
    setDestination(id);
    setNavOpen(false);
  };

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") dispatch({ type: "closeInspector" });
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [dispatch]);

  const available =
    snapshot?.technicians.filter((t) => t.availability === "available")
      .length ?? 0;
  const active =
    snapshot?.jobs.filter((j) => j.status === "in_progress").length ?? 0;
  const completed =
    snapshot?.jobs.filter((j) => j.status === "completed").length ?? 0;
  const fixture = transport?.kind === "dev-fixture";
  const pageTitle = destinations.find((d) => d.id === destination)!.label;
  const inspector = committed && (
    <>
      <header className="inspector-heading">
        <div>
          <span className="eyebrow">
            {state.proposal ? "Dispatcher decision" : "Selected details"}
          </span>
          <h2>
            {state.proposal
              ? "Review proposal"
              : state.selectedJob
                ? "Job details"
                : "Technician details"}
          </h2>
        </div>
        {layout === "desktop" && (
          <Button
            size="icon"
            variant="ghost"
            aria-label="Close inspector (Escape)"
            onClick={() => dispatch({ type: "closeInspector" })}
          >
            <X />
          </Button>
        )}
      </header>
      <div className="inspector-content">
        {state.busy === "previewing" ? (
          <div className="review-loading" role="status">
            <RefreshCw className="animate-spin" />
            <h3>Finding a place in the day</h3>
            <p>Checking skills, travel and existing commitments.</p>
            <p className="text-xs">The approved schedule stays in place.</p>
          </div>
        ) : state.proposal ? (
          <ProposalPanel
            proposal={state.proposal}
            strategy={state.proposalStrategy}
            committed={committed}
            stale={state.proposalStale}
            busy={state.busy}
            onApprove={commit}
            onReject={reject}
            onRefresh={refresh}
            onSelectJob={selectJob}
          />
        ) : state.selectedJob ? (
          <JobInspector
            jobId={state.selectedJob}
            committed={committed}
            proposed={proposed}
            proposal={state.proposal}
          />
        ) : state.selectedTech ? (
          <TechnicianInspector
            view={view ?? committed}
            id={state.selectedTech}
            onSelectJob={selectJob}
          />
        ) : (
          <p className="text-muted">
            Select an appointment to see its requirements and assignment.
          </p>
        )}
      </div>
    </>
  );

  const nav = (
    <>
      <a
        className="brand"
        href="#dispatch"
        onClick={(e) => {
          e.preventDefault();
          navigate("dispatch");
        }}
        aria-label="DispatchIQ home"
      >
        <img src={`${import.meta.env.BASE_URL}favicon.svg`} alt="" />
        <span>
          Dispatch<span className="brand-accent">IQ</span>
          <small>OPERATIONS WORKSPACE</small>
        </span>
      </a>
      <div className="workspace-label">
        <span className="workspace-avatar">D</span>
        <span>
          Demo service team<small>Synthetic operations</small>
        </span>
      </div>
      <nav aria-label="Main navigation" className="product-nav">
        {destinations.map((d) => (
          <button
            key={d.id}
            className={destination === d.id ? "nav-link selected" : "nav-link"}
            aria-current={destination === d.id ? "page" : undefined}
            onClick={() => navigate(d.id)}
          >
            <d.icon />
            {d.label}
            {d.id === "jobs" && snapshot && (
              <span className="nav-count">{snapshot.jobs.length}</span>
            )}
          </button>
        ))}
      </nav>
      <div className="rail-footer">
        <ShieldCheck />
        <strong>Human-approved dispatch</strong>
        <p>Every change stays a proposal until you approve it.</p>
        <span className="rail-version">Synthetic demo · v1</span>
      </div>
    </>
  );

  const versionTabs = (
    <Tabs
      value={state.view}
      onValueChange={(v) => dispatch({ type: "view", view: v as View })}
    >
      <TabsList aria-label="Schedule version">
        <TabsTrigger
          value="baseline"
          title="Snapshot captured when this page loaded or reset"
        >
          Loaded snapshot
        </TabsTrigger>
        <TabsTrigger value="committed">Approved</TabsTrigger>
        <TabsTrigger
          value="proposed"
          disabled={!proposed}
          data-testid="view-proposed"
        >
          Proposed
        </TabsTrigger>
      </TabsList>
    </Tabs>
  );

  return (
    <div className="application">
      <div aria-live="polite" className="sr-only" data-testid="announce">
        {state.announce}
      </div>
      <a href="#main" className="skip-link">
        Skip to workspace
      </a>
      <aside className="product-rail">{nav}</aside>
      <div className="application-body">
        {fixture && (
          <div
            className="fixture-banner"
            role="note"
            data-testid="fixture-banner"
          >
            <FlaskConical size={14} /> Development fixture — not backend results
          </div>
        )}
        <header className="app-header">
          <div className="breadcrumb">
            <Button
              className="menu-button"
              size="icon"
              variant="ghost"
              aria-label="Open navigation"
              onClick={() => setNavOpen(true)}
            >
              <Menu />
            </Button>
            <span className="breadcrumb-team">Workspace</span>
            <ChevronRight size={14} className="breadcrumb-team" />
            <span>{pageTitle}</span>
          </div>
          <div className="header-context">
            <span
              className={backend.ok ? "connection connected" : "connection"}
              data-testid="backend-status"
            >
              <i />
              {backend.ok
                ? fixture
                  ? "Dev fixture"
                  : "Connected"
                : "Connection unavailable"}
            </span>
            <span className="simulated-time">
              {snapshot
                ? `${hhmm(snapshot.now_min)} · Simulated day`
                : "Connecting"}
            </span>
          </div>
        </header>
        <main id="main" tabIndex={-1} className="workspace-main">
          <div className="page-heading">
            <div>
              <h1>{pageTitle}</h1>
              <p>
                {destination === "dispatch"
                  ? "Keep the day moving. Handle the unexpected."
                  : destination === "overview"
                    ? "Your service day, at a glance."
                    : destination === "jobs"
                      ? "Every appointment and the commitments behind it."
                      : destination === "technicians"
                        ? "Find the right skills and see today’s workload."
                        : "Events applied to the approved schedule."}
              </p>
            </div>
            <div className="page-actions">
              {state.proposal && (
                <Button
                  variant="primary"
                  size="sm"
                  onClick={() => dispatch({ type: "openInspector" })}
                  data-testid="review-proposal"
                >
                  Review proposal
                </Button>
              )}
              <ScenarioControls
                snapshot={snapshot}
                busy={state.busy}
                hasOpenProposal={
                  !!state.proposal &&
                  !state.proposalStale &&
                  state.proposal.status === "ready"
                }
                onPreview={(e, st) => {
                  setDestination("dispatch");
                  return preview(e, st);
                }}
                onReset={reset}
              />
            </div>
          </div>
          {state.error && (
            <div
              role="alert"
              className="error-banner"
              data-testid={
                state.error.scope === "load" ? "load-error" : "operation-error"
              }
            >
              <AlertTriangle size={17} />
              <span>{state.error.message}</span>
              {state.error.scope === "load" ? (
                <Button size="sm" onClick={refresh}>
                  Retry
                </Button>
              ) : (
                <Button
                  size="icon"
                  variant="ghost"
                  aria-label="Dismiss error"
                  onClick={() => dispatch({ type: "clearError" })}
                >
                  <X />
                </Button>
              )}
            </div>
          )}
          {state.announce &&
            state.busy === null &&
            !state.error &&
            /^(Approved|Proposal rejected|Scenario reset)/.test(
              state.announce,
            ) && (
              <div className="confirmation" role="status">
                <CheckCheck size={16} />
                {state.announce}
              </div>
            )}
          {!snapshot && (
            <div className="loading-workspace" role="status">
              {state.busy === "loading" ? (
                <>
                  <RefreshCw className="animate-spin" /> Loading today’s
                  schedule
                  <div className="skeleton-row" />
                  <div className="skeleton-row" />
                  <div className="skeleton-row" />
                </>
              ) : (
                <>
                  <Radio />
                  <h2>Connect to your dispatch service</h2>
                  <p>Retry when the local service is available.</p>
                </>
              )}
            </div>
          )}
          {view && committed && snapshot && (
            <>
              {destination === "dispatch" ? (
                <>
                  <div
                    className="operational-strip"
                    data-testid="metrics-strip"
                    aria-label="Current approved operations"
                  >
                    <div>
                      <Users />
                      <span>
                        On shift
                        <strong>
                          {available}
                          <small>
                            {" "}
                            / {snapshot.technicians.length} technicians
                          </small>
                        </strong>
                      </span>
                    </div>
                    <div>
                      <Radio />
                      <span>
                        In progress
                        <strong>
                          {active}
                          <small> appointments</small>
                        </strong>
                      </span>
                    </div>
                    <div className="secondary-metric">
                      <CheckCheck />
                      <span>
                        Completed
                        <strong>
                          {completed}
                          <small> / {snapshot.jobs.length} jobs</small>
                        </strong>
                      </span>
                    </div>
                    <div className="secondary-metric">
                      <ClipboardList />
                      <span>
                        Needs assignment
                        <strong
                          className={
                            snapshot.metrics.unassigned_jobs
                              ? "text-proposed"
                              : ""
                          }
                        >
                          {snapshot.metrics.unassigned_jobs}
                          <small> jobs</small>
                        </strong>
                      </span>
                    </div>
                    <span className="strip-validation">
                      <ShieldCheck size={14} />
                      {snapshot.validation.valid
                        ? "Schedule checked"
                        : "Needs review"}
                      <small className="tabular" data-testid="revision">
                        rev {snapshot.revision}
                      </small>
                    </span>
                  </div>
                  <div
                    className={`dispatch-layout ${layout === "desktop" && inspectorOpen ? "with-inspector" : ""}`}
                  >
                    <div className="dispatch-workspace">
                      <div className="board-toolbar">
                        <div className="board-date">
                          <CalendarDays size={15} />
                          <span>
                            {new Intl.DateTimeFormat("en-US", {
                              month: "short",
                              day: "numeric",
                              year: "numeric",
                              timeZone: "UTC",
                            }).format(new Date(snapshot.date + "T12:00:00Z"))}
                          </span>
                          <small>
                            {state.view === "proposed"
                              ? "Unapproved preview"
                              : state.view === "baseline"
                                ? "Snapshot from page load"
                                : "Approved schedule"}
                          </small>
                        </div>
                        {versionTabs}
                      </div>
                      {layout === "mobile" && (
                        <Tabs value={mobileView} onValueChange={setMobileView}>
                          <TabsList aria-label="Workspace view">
                            <TabsTrigger value="timeline">
                              <CalendarDays size={14} />
                              Timeline
                            </TabsTrigger>
                            <TabsTrigger value="map">
                              <MapIcon size={14} />
                              Map
                            </TabsTrigger>
                            <TabsTrigger
                              value="details"
                              onClick={() =>
                                dispatch({ type: "openInspector" })
                              }
                            >
                              Details
                            </TabsTrigger>
                          </TabsList>
                        </Tabs>
                      )}
                      {(layout !== "mobile" || mobileView === "map") && (
                        <section
                          className={`service-map ${mapExpanded ? "expanded" : ""}`}
                          aria-label="Service map"
                        >
                          <RouteMap
                            view={view}
                            changes={changes}
                            showChanges={showChanges}
                            selectedTech={state.selectedTech}
                            selectedJob={state.selectedJob}
                            onSelectTech={selectTech}
                            onSelectJob={selectJob}
                          />
                          <div className="map-caption">
                            <span className="map-title">
                              <MapIcon size={14} />
                              <strong>Service area</strong>
                              <small>Synthetic city · estimated travel</small>
                            </span>
                            <span className="map-selection">
                              {state.selectedTech
                                ? `${view.techs.get(state.selectedTech)?.name ?? state.selectedTech} · selected route`
                                : "Select a job or technician to explore"}
                            </span>
                            {layout !== "mobile" && (
                              <Button
                                size="sm"
                                variant="outline"
                                className="map-expand"
                                aria-expanded={mapExpanded}
                                onClick={() => setMapExpanded(!mapExpanded)}
                              >
                                {mapExpanded ? "Compact map" : "Expand map"}
                              </Button>
                            )}
                          </div>
                        </section>
                      )}
                      {(layout !== "mobile" || mobileView === "timeline") && (
                        <section
                          className="schedule-panel"
                          aria-label="Dispatch schedule"
                        >
                          <header className="schedule-heading">
                            <div>
                              <h2>Technician schedule</h2>
                              <span>
                                {snapshot.technicians.length} technicians ·{" "}
                                {view.snap.schedule.assignments.length} assigned
                                jobs
                              </span>
                            </div>
                            {state.selectedTech && (
                              <Button
                                size="sm"
                                variant="ghost"
                                onClick={() =>
                                  dispatch({ type: "selectTech", id: null })
                                }
                              >
                                Clear selection
                                <X size={14} />
                              </Button>
                            )}
                            {state.proposal && (
                              <span className="proposal-label">
                                {showChanges
                                  ? "Proposed changes highlighted"
                                  : "Viewing approved work"}
                              </span>
                            )}
                          </header>
                          <ScheduleBoard
                            view={view}
                            committed={committed}
                            changes={changes}
                            showChanges={showChanges}
                            selectedTech={state.selectedTech}
                            selectedJob={state.selectedJob}
                            onSelectTech={selectTech}
                            onSelectJob={selectJob}
                          />
                        </section>
                      )}
                    </div>
                    {layout === "desktop" && inspectorOpen && (
                      <aside
                        className="context-panel"
                        aria-label="Inspector"
                        data-testid="inspector"
                      >
                        {inspector}
                      </aside>
                    )}
                  </div>
                </>
              ) : (
                <OperationsPages
                  destination={destination}
                  view={committed}
                  onNavigate={navigate}
                  onSelectJob={selectJob}
                  onSelectTech={selectTech}
                />
              )}
              {(layout !== "desktop" || destination !== "dispatch") && (
                <Dialog
                  open={inspectorOpen}
                  onOpenChange={(open) =>
                    !open && dispatch({ type: "closeInspector" })
                  }
                >
                  <DialogContent
                    side="right"
                    title={state.proposal ? "Proposal review" : "Details"}
                    aria-describedby={undefined}
                  >
                    <div className="drawer-content" data-testid="inspector">
                      {inspector}
                    </div>
                  </DialogContent>
                </Dialog>
              )}
            </>
          )}
        </main>
      </div>
      <Dialog open={navOpen} onOpenChange={setNavOpen}>
        <DialogContent
          side="right"
          title="Workspace navigation"
          aria-describedby={undefined}
        >
          <div className="mobile-navigation">{nav}</div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
