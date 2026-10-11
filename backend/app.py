"""Run from repository root: python -m uvicorn backend.app:app --port 8000."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .intake import IntakeUnavailable, llm_complete, parse_event
from .research import research_summary
from .schemas import (BaseRequest, HealthResponse, JobsResponse, MetricsResponse, OptimizeRequest,
                      ParseRequest, ParseResponse, PreviewRequest, Proposal, ProposalRequest, RejectResponse,
                      ScheduleResponse, Snapshot, TechniciansResponse)
from .store import APIError, StateStore

RUNS_DIR = Path(__file__).resolve().parents[1] / "runs"
STATE_PATH = RUNS_DIR / "operations-state.json"


def create_app(store: StateStore | None = None, intake=llm_complete, runs_dir: Path = RUNS_DIR) -> FastAPI:
    """`intake` returns the LLM completion function for event parsing (replaced by a stub in tests)."""
    @asynccontextmanager
    async def lifespan(application):
        application.state.store = store if store is not None else StateStore(STATE_PATH)
        yield

    application = FastAPI(title="DispatchIQ Operations API", version="1.0.0", lifespan=lifespan)
    application.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
                               allow_methods=["GET", "POST"], allow_headers=["Content-Type"])

    @application.exception_handler(APIError)
    async def api_error(_request: Request, exc: APIError):
        return JSONResponse(status_code=exc.status, content=exc.envelope())

    @application.exception_handler(RequestValidationError)
    async def invalid_request(_request: Request, exc: RequestValidationError):
        details = [{"field": ".".join(map(str, e["loc"])), "type": e["type"], "message": e["msg"]} for e in exc.errors()]
        return JSONResponse(status_code=422, content={"error": {"code": "INVALID_INPUT",
                            "message": "Request does not match the operational contract.", "current_revision": None, "details": details}})

    @application.get("/api/health", response_model=HealthResponse)
    def health():
        return {"status": "ok", "schema_version": "1", "optimizer": "feasible_insertion", "state_ready": True}

    @application.get("/api/scenario", response_model=Snapshot)
    def scenario(request: Request):
        return request.app.state.store.snapshot()

    def collection(request: Request, *fields):
        snapshot = request.app.state.store.snapshot().model_dump(mode="json")
        return {key: snapshot[key] for key in ("schema_version", "scenario_id", "scenario_epoch", "revision", *fields)}

    @application.get("/api/technicians", response_model=TechniciansResponse)
    def technicians(request: Request):
        return collection(request, "technicians")

    @application.get("/api/jobs", response_model=JobsResponse)
    def jobs(request: Request):
        return collection(request, "jobs")

    @application.get("/api/schedule", response_model=ScheduleResponse)
    def schedule(request: Request):
        return collection(request, "schedule", "validation")

    @application.get("/api/metrics", response_model=MetricsResponse)
    def metrics(request: Request):
        return collection(request, "metrics")

    @application.get("/api/research/latest")
    def research_latest():
        # Read-only: parses saved evolve.py run files; never loads or executes policy code.
        return research_summary(runs_dir)

    @application.post("/api/events/preview", response_model=Proposal)
    def preview(body: PreviewRequest, request: Request):
        return request.app.state.store.preview(body)

    @application.post("/api/events/parse", response_model=ParseResponse)
    def parse(body: ParseRequest, request: Request):
        # Reads the committed snapshot only: no optimizer call, no proposal, no state change.
        snapshot = request.app.state.store.snapshot_at(body)
        try:
            complete = intake()
        except IntakeUnavailable:
            raise APIError(503, "LLM_NOT_CONFIGURED", "Event parsing needs an LLM provider "
                           "(LLM_BASE_URL, LLM_API_KEY, LLM_MODEL). Use the event form instead.", snapshot.revision)
        try:
            return parse_event(body.text, snapshot, complete)
        except Exception as exc:  # provider outage or unusable model output; never a partial event
            raise APIError(503, "LLM_FAILED", "The event could not be parsed. Try again or use the event form.",
                           snapshot.revision) from exc

    @application.post("/api/optimize", response_model=Proposal)
    def optimize(body: OptimizeRequest, request: Request):
        return request.app.state.store.preview(body)

    @application.post("/api/events/commit", response_model=Snapshot)
    def commit(body: ProposalRequest, request: Request):
        return request.app.state.store.commit(body)

    @application.post("/api/events/reject", response_model=RejectResponse)
    def reject(body: ProposalRequest, request: Request):
        return request.app.state.store.reject(body)

    @application.post("/api/reset", response_model=Snapshot)
    def reset(body: BaseRequest, request: Request):
        return request.app.state.store.reset(body)

    return application


app = create_app()
