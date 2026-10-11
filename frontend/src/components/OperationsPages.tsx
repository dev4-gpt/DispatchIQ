import { useState } from "react";
import {
  ArrowRight,
  CalendarClock,
  CheckCheck,
  Clock,
  Search,
  ShieldCheck,
  Siren,
  Users,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { skillText, type Indexed } from "@/lib/schedule";
import { hhmm } from "@/state/dispatch";

export type Destination =
  | "overview"
  | "dispatch"
  | "jobs"
  | "technicians"
  | "activity";
interface Props {
  destination: Destination;
  view: Indexed;
  onNavigate: (page: Destination) => void;
  onSelectJob: (id: string) => void;
  onSelectTech: (id: string) => void;
}
const statusLabel = (status: string) =>
  status === "in_progress"
    ? "In progress"
    : status.charAt(0).toUpperCase() + status.slice(1);

export function TechnicianInspector({
  view,
  id,
  onSelectJob,
}: Pick<Props, "view" | "onSelectJob"> & { id: string }) {
  const t = view.techs.get(id);
  if (!t) return null;
  const route = view.routes.get(id) ?? [];
  const service = route.reduce((n, a) => n + a.end_min - a.start_min, 0);
  const active = route.find(
    (a) => a.start_min <= view.snap.now_min && a.end_min > view.snap.now_min,
  );
  return (
    <section className="technician-detail" data-testid="technician-inspector">
      <div className="detail-avatar">{t.name.slice(0, 1)}</div>
      <h2>{t.name}</h2>
      <p className="text-muted">
        {active
          ? `Working on ${active.job_id}`
          : t.availability === "available"
            ? "Available for assignment"
            : "Unavailable"}
      </p>
      <div className="flex flex-wrap gap-1.5">
        {t.skills.map((s) => (
          <Badge key={s}>{skillText(s)}</Badge>
        ))}
      </div>
      <dl className="detail-list">
        <div>
          <dt>Shift</dt>
          <dd>
            {hhmm(t.shift_start_min)}–{hhmm(t.shift_end_min)}
          </dd>
        </div>
        <div>
          <dt>Scheduled service</dt>
          <dd>
            {service} / {t.max_service_min} min
          </dd>
        </div>
        <div>
          <dt>Assigned jobs</dt>
          <dd>{route.length}</dd>
        </div>
        <div>
          <dt>Starting location</dt>
          <dd>
            {t.location.x_km}, {t.location.y_km} km grid
          </dd>
        </div>
      </dl>
      <h3 className="eyebrow">Today’s appointments</h3>
      <ul className="appointment-list">
        {route.map((a) => (
          <li key={a.job_id}>
            <button onClick={() => onSelectJob(a.job_id)}>
              <span>
                <strong>{view.jobs.get(a.job_id)?.customer.name}</strong>
                <small>
                  {a.job_id} · {hhmm(a.start_min)}–{hhmm(a.end_min)}
                </small>
              </span>
              <ArrowRight size={14} />
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}

export function OperationsPages({
  destination,
  view,
  onNavigate,
  onSelectJob,
  onSelectTech,
}: Props) {
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("all");
  const [skill, setSkill] = useState("all");
  const s = view.snap;
  const skills = [...new Set(s.technicians.flatMap((t) => t.skills))];
  if (destination === "jobs") {
    const jobs = s.jobs.filter(
      (j) =>
        `${j.id} ${j.customer.name} ${j.customer.site_name} ${view.techs.get(view.byJob.get(j.id)?.technician_id ?? "")?.name ?? ""}`
          .toLowerCase()
          .includes(query.toLowerCase()) &&
        (status === "all" || j.status === status) &&
        (skill === "all" || j.required_skills.includes(skill)),
    );
    return (
      <section className="data-page">
        <div className="list-toolbar">
          <label className="search-field">
            <Search size={16} />
            <input
              aria-label="Search jobs"
              placeholder="Search jobs, customers or technicians"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </label>
          <select
            aria-label="Filter job status"
            value={status}
            onChange={(e) => setStatus(e.target.value)}
          >
            <option value="all">All statuses</option>
            {[
              "scheduled",
              "in_progress",
              "completed",
              "unassigned",
              "cancelled",
            ].map((x) => (
              <option key={x} value={x}>
                {statusLabel(x)}
              </option>
            ))}
          </select>
          <select
            aria-label="Filter required skill"
            value={skill}
            onChange={(e) => setSkill(e.target.value)}
          >
            <option value="all">All skills</option>
            {skills.map((x) => (
              <option key={x} value={x}>
                {skillText(x)}
              </option>
            ))}
          </select>
          <span>{jobs.length} jobs</span>
        </div>
        <div className="table-scroll">
          <table className="operations-table">
            <thead>
              <tr>
                <th>Appointment</th>
                <th>Status</th>
                <th>Skills</th>
                <th>Start window</th>
                <th>Assigned technician</th>
                <th>Priority</th>
              </tr>
            </thead>
            <tbody>
              {jobs.map((j) => {
                const a = view.byJob.get(j.id);
                return (
                  <tr key={j.id}>
                    <td>
                      <button
                        className="table-job"
                        onClick={() => onSelectJob(j.id)}
                      >
                        <strong>{j.customer.name}</strong>
                        <small>
                          {j.id} · {j.customer.site_name}
                        </small>
                      </button>
                    </td>
                    <td>
                      <Badge
                        tone={
                          j.status === "completed"
                            ? "green"
                            : j.status === "in_progress"
                              ? "blue"
                              : j.status === "unassigned"
                                ? "amber"
                                : "neutral"
                        }
                      >
                        {statusLabel(j.status)}
                      </Badge>
                    </td>
                    <td>{j.required_skills.map(skillText).join(", ")}</td>
                    <td className="tabular">
                      {hhmm(j.earliest_start_min)}–{hhmm(j.latest_start_min)}
                    </td>
                    <td>
                      {a ? view.techs.get(a.technician_id)?.name : "Unassigned"}
                      {a && (
                        <small className="cell-meta">{hhmm(a.start_min)}</small>
                      )}
                    </td>
                    <td>
                      {j.emergency ? (
                        <Badge tone="red">
                          <Siren />
                          Emergency
                        </Badge>
                      ) : (
                        <span className="text-muted">P{j.priority}</span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        {!jobs.length && (
          <div className="empty-list">
            <Search />
            <h3>No matching appointments</h3>
            <p>Try a different search or filter.</p>
            <Button
              onClick={() => {
                setQuery("");
                setSkill("all");
                setStatus("all");
              }}
            >
              Clear filters
            </Button>
          </div>
        )}
      </section>
    );
  }
  if (destination === "technicians") {
    const techs = s.technicians.filter(
      (t) =>
        `${t.name} ${t.skills.map(skillText).join(" ")}`
          .toLowerCase()
          .includes(query.toLowerCase()) &&
        (skill === "all" || t.skills.includes(skill)),
    );
    return (
      <section className="data-page">
        <div className="list-toolbar">
          <label className="search-field">
            <Search size={16} />
            <input
              aria-label="Search technicians"
              placeholder="Search name or qualification"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </label>
          <select
            aria-label="Filter technician skill"
            value={skill}
            onChange={(e) => setSkill(e.target.value)}
          >
            <option value="all">All qualifications</option>
            {skills.map((x) => (
              <option key={x} value={x}>
                {skillText(x)}
              </option>
            ))}
          </select>
          <span>{techs.length} technicians</span>
        </div>
        <div className="technician-directory">
          {techs.map((t) => {
            const r = view.routes.get(t.id) ?? [];
            const service = r.reduce((n, a) => n + a.end_min - a.start_min, 0);
            const current = r.find(
              (a) => a.start_min <= s.now_min && a.end_min > s.now_min,
            );
            return (
              <button
                key={t.id}
                className="technician-card"
                data-testid={`tech-${t.id}`}
                onClick={() => onSelectTech(t.id)}
              >
                <div className="technician-card-heading">
                  <span className="detail-avatar small">
                    {t.name.slice(0, 1)}
                  </span>
                  <div>
                    <h2>{t.name}</h2>
                    <small>
                      {current
                        ? `On job ${current.job_id}`
                        : t.availability === "available"
                          ? "Available for assignment"
                          : "Unavailable"}
                    </small>
                  </div>
                  <ArrowRight size={16} />
                </div>
                <div className="flex flex-wrap gap-1">
                  {t.skills.map((k) => (
                    <Badge key={k}>{skillText(k)}</Badge>
                  ))}
                </div>
                <div className="workload">
                  <span>{r.length} jobs today</span>
                  <span>
                    {service} / {t.max_service_min} min
                  </span>
                </div>
                <progress
                  aria-label={`${t.name} daily service capacity`}
                  value={service}
                  max={t.max_service_min}
                />
                <span className="shift-meta">
                  Shift {hhmm(t.shift_start_min)}–{hhmm(t.shift_end_min)}
                </span>
              </button>
            );
          })}
        </div>
        {!techs.length && (
          <div className="empty-list">
            <Users />
            <h3>No matching technicians</h3>
            <p>Try a different name or qualification.</p>
          </div>
        )}
      </section>
    );
  }
  if (destination === "activity")
    return (
      <section className="data-page activity-page">
        <div className="section-intro">
          <h2>Committed events</h2>
          <p>
            Events shown here have been applied to this schedule. Pending
            proposals are reviewed on the dispatch board.
          </p>
        </div>
        {s.events.length ? (
          <ol className="activity-list">
            {s.events.map((e, i) => (
              <li key={`${i}-${e.at_min}`}>
                <span className="activity-icon">
                  {e.type === "emergency" ? (
                    <Siren size={18} />
                  ) : (
                    <Users size={18} />
                  )}
                </span>
                <div>
                  <h3>
                    {e.type === "emergency"
                      ? `Emergency assigned · ${e.job.customer.name}`
                      : `Technician unavailable · ${view.techs.get(e.technician_id)?.name ?? e.technician_id}`}
                  </h3>
                  <p>
                    {e.type === "emergency"
                      ? `${e.job.id} · ${e.job.required_skills.map(skillText).join(", ")}`
                      : "Future assignments replanned"}
                  </p>
                  <small className="tabular">
                    Event time {hhmm(e.at_min)} · simulated day
                  </small>
                </div>
                <Badge tone="green">
                  <CheckCheck />
                  Applied
                </Badge>
              </li>
            ))}
          </ol>
        ) : (
          <div className="empty-list">
            <CalendarClock />
            <h3>A calm start to the day</h3>
            <p>No disruption events have been applied to this schedule.</p>
            <Button onClick={() => onNavigate("dispatch")}>
              Open dispatch board
              <ArrowRight />
            </Button>
          </div>
        )}
        <p className="page-footnote">
          Approval actor, wall-clock audit timestamps and rejected-event history
          are not supplied by this API.
        </p>
      </section>
    );
  const upcoming = s.schedule.assignments
    .filter((a) => a.start_min > s.now_min)
    .sort((a, b) => a.start_min - b.start_min)
    .slice(0, 5);
  const completed = s.jobs.filter((j) => j.status === "completed").length;
  const active = s.jobs.filter((j) => j.status === "in_progress").length;
  const alerts = s.jobs.filter((j) => j.status === "unassigned" || j.emergency);
  return (
    <div className="overview-page">
      <div className="overview-metrics">
        {[
          ["Completed jobs", completed, CheckCheck],
          ["In progress", active, Clock],
          [
            "On shift",
            s.technicians.filter((t) => t.availability === "available").length,
            Users,
          ],
          ["Future travel", `${s.metrics.travel_min} min`, CalendarClock],
        ].map(([label, value, Icon]) => {
          const I = Icon as typeof Users;
          return (
            <div key={label as string}>
              <I />
              <span>{label as string}</span>
              <strong>{value as string | number}</strong>
            </div>
          );
        })}
      </div>
      <div className="overview-columns">
        <section className="data-page">
          <div className="section-intro">
            <h2>Up next</h2>
            <p>Upcoming appointments from the approved schedule.</p>
          </div>
          <ul className="appointment-list">
            {upcoming.map((a) => (
              <li key={a.job_id}>
                <button onClick={() => onSelectJob(a.job_id)}>
                  <span className="time-block tabular">
                    {hhmm(a.start_min)}
                  </span>
                  <span>
                    <strong>{view.jobs.get(a.job_id)?.customer.name}</strong>
                    <small>
                      {a.job_id} · {view.techs.get(a.technician_id)?.name}
                    </small>
                  </span>
                  <ArrowRight size={16} />
                </button>
              </li>
            ))}
          </ul>
          <Button className="m-4" onClick={() => onNavigate("dispatch")}>
            Open dispatch board
            <ArrowRight />
          </Button>
        </section>
        <section className="data-page">
          <div className="section-intro">
            <h2>Requires attention</h2>
            <p>Unassigned work and emergency appointments.</p>
          </div>
          {alerts.length ? (
            <ul className="appointment-list">
              {alerts.map((j) => (
                <li key={j.id}>
                  <button onClick={() => onSelectJob(j.id)}>
                    <Siren
                      size={16}
                      className={
                        j.emergency ? "text-emergency" : "text-proposed"
                      }
                    />
                    <span>
                      <strong>{j.customer.name}</strong>
                      <small>
                        {j.id} ·{" "}
                        {j.status === "unassigned"
                          ? "Needs assignment"
                          : "Emergency"}
                      </small>
                    </span>
                    <ArrowRight size={16} />
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            <div className="quiet-state">
              <ShieldCheck />
              <h3>All work is accounted for</h3>
              <p>No emergencies or unassigned appointments.</p>
            </div>
          )}
          <div className="service-checks">
            <div>
              <span>Late customer promises</span>
              <strong>{s.metrics.soft_sla_violations}</strong>
            </div>
            <div>
              <span>Constraint violations</span>
              <strong>{s.metrics.hard_constraint_violations}</strong>
            </div>
            <div>
              <span>Authorized overtime</span>
              <strong>{s.metrics.overtime_min} min</strong>
            </div>
          </div>
          <p className="page-footnote">
            Travel and promise metrics cover future work after {hhmm(s.now_min)}
            .
          </p>
        </section>
      </div>
    </div>
  );
}
