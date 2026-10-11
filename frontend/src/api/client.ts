import type {
  ApiErrorBody,
  BaseMetadata,
  DispatchEvent,
  Health,
  Proposal,
  RejectResult,
  Snapshot,
  Strategy,
} from "./types";

/** Typed error for every failed call; the UI keeps the committed view on any of these. */
export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public currentRevision?: number,
  ) {
    super(message);
  }

  /** Lifecycle conflicts mean the proposal is unusable and the user must refresh/preview again. */
  get isStale() {
    return (
      this.status === 409 ||
      this.status === 410 ||
      ["STALE_PROPOSAL", "PROPOSAL_CONSUMED", "PROPOSAL_REJECTED", "SCENARIO_CHANGED", "PROPOSAL_EXPIRED"].includes(this.code)
    );
  }
}

export interface Transport {
  readonly kind: "api" | "dev-fixture";
  health(): Promise<Health>;
  scenario(): Promise<Snapshot>;
  preview(base: BaseMetadata, event: DispatchEvent, strategy: Strategy): Promise<Proposal>;
  commit(base: BaseMetadata, proposalId: string): Promise<Snapshot>;
  reject(base: BaseMetadata, proposalId: string): Promise<RejectResult>;
  reset(base: BaseMetadata): Promise<Snapshot>;
}

const FRIENDLY: Record<string, string> = {
  STALE_PROPOSAL: "The schedule changed since this preview. Preview the event again.",
  PROPOSAL_CONSUMED: "This proposal was already approved.",
  PROPOSAL_REJECTED: "This proposal was already rejected.",
  SCENARIO_CHANGED: "The scenario was reset or changed. Refresh and preview again.",
  PROPOSAL_EXPIRED: "This proposal expired. Preview the event again.",
  INVALID_INPUT: "The request was rejected as invalid input.",
  OPTIMIZER_FAILED: "The optimizer failed. The committed schedule was not changed.",
  STATE_WRITE_FAILED: "The server could not save state. The committed schedule was not changed.",
  NETWORK: "Cannot reach the dispatch API. The last committed schedule is still shown.",
};

export function friendlyMessage(e: unknown): string {
  if (e instanceof ApiError) return FRIENDLY[e.code] ?? e.message ?? `Request failed (${e.status}).`;
  return e instanceof Error ? e.message : "Unexpected error.";
}

async function request<T>(method: "GET" | "POST", path: string, body?: unknown): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`/api${path}`, {
      method,
      headers: body ? { "Content-Type": "application/json" } : undefined,
      body: body ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new ApiError(0, "NETWORK", FRIENDLY.NETWORK);
  }
  const text = await res.text();
  let data: unknown = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    throw new ApiError(res.status, "BAD_RESPONSE", `Server returned non-JSON (${res.status}).`);
  }
  if (!res.ok) {
    const err = (data as ApiErrorBody | null)?.error;
    throw new ApiError(res.status, err?.code ?? `HTTP_${res.status}`, err?.message ?? `Request failed (${res.status}).`, err?.current_revision);
  }
  return data as T;
}

export const httpTransport: Transport = {
  kind: "api",
  health: () => request("GET", "/health"),
  scenario: () => request("GET", "/scenario"),
  preview: (base, event, strategy) => request("POST", "/events/preview", { ...base, event, strategy }),
  commit: (base, proposal_id) => request("POST", "/events/commit", { ...base, proposal_id }),
  reject: (base, proposal_id) => request("POST", "/events/reject", { ...base, proposal_id }),
  reset: (base) => request("POST", "/reset", base),
};

/** The dev fixture is opt-in only (`npm run dev:fixture` or `?fixture=dev`); never a silent fallback. */
export async function chooseTransport(): Promise<Transport> {
  const wantFixture =
    import.meta.env.VITE_DEV_FIXTURE === "1" || new URLSearchParams(window.location.search).get("fixture") === "dev";
  if (!wantFixture) return httpTransport;
  const { devFixtureTransport } = await import("./devFixture");
  return devFixtureTransport;
}
