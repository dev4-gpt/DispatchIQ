import { useCallback, useEffect, useReducer, useRef, useState } from "react";
import {
  ApiError,
  chooseTransport,
  friendlyMessage,
  type Transport,
} from "@/api/client";
import { baseOf, type DispatchEvent, type Strategy } from "@/api/types";
import { initialState, reducer } from "./dispatch";

export function useDispatch() {
  const [state, dispatch] = useReducer(reducer, initialState);
  const [transport, setTransport] = useState<Transport | null>(null);
  const [backend, setBackend] = useState<{ ok: boolean; label: string }>({
    ok: false,
    label: "Connecting…",
  });
  const stateRef = useRef(state);
  stateRef.current = state;

  const load = useCallback(async (t: Transport, resetBaseline: boolean) => {
    dispatch({ type: "busy", busy: "loading" });
    try {
      const h = await t.health();
      setBackend({
        ok: h.status === "ok" && h.state_ready,
        label: `${t.kind === "dev-fixture" ? "Dev fixture" : "API"} · ${h.optimizer}`,
      });
      const snap = await t.scenario();
      dispatch({ type: "loaded", snapshot: snap, resetBaseline });
    } catch (e) {
      setBackend({ ok: false, label: "API unreachable" });
      dispatch({ type: "error", scope: "load", message: friendlyMessage(e) });
    }
  }, []);

  useEffect(() => {
    let active = true;
    chooseTransport().then((t) => {
      if (!active) return;
      setTransport(t);
      void load(t, true);
    });
    return () => {
      active = false;
    };
  }, [load]);

  const handleLifecycle = useCallback(
    (e: unknown, scope: "commit" | "reject" | "preview") => {
      if (e instanceof ApiError && e.isStale) {
        dispatch({ type: "stale", reason: friendlyMessage(e) });
      } else {
        dispatch({ type: "error", scope, message: friendlyMessage(e) });
      }
    },
    [],
  );

  const preview = useCallback(
    async (event: DispatchEvent, strategy: Strategy = "stable_insertion") => {
      const s = stateRef.current.snapshot;
      if (!transport || !s) return;
      dispatch({ type: "busy", busy: "previewing" });
      try {
        const p = await transport.preview(baseOf(s), event, strategy);
        dispatch({ type: "proposal", proposal: p, strategy });
      } catch (e) {
        handleLifecycle(e, "preview");
      }
    },
    [transport, handleLifecycle],
  );

  const commit = useCallback(async () => {
    const { snapshot: s, proposal: p } = stateRef.current;
    if (!transport || !s || !p) return;
    dispatch({ type: "busy", busy: "committing" });
    try {
      const snap = await transport.commit(
        {
          scenario_id: p.scenario_id,
          scenario_epoch: p.scenario_epoch,
          base_revision: p.base_revision,
        },
        p.proposal_id,
      );
      dispatch({ type: "committed", snapshot: snap });
    } catch (e) {
      handleLifecycle(e, "commit");
    }
  }, [transport, handleLifecycle]);

  const reject = useCallback(async () => {
    const { snapshot: s, proposal: p } = stateRef.current;
    if (!transport || !s || !p) return;
    if (p.status !== "ready" || stateRef.current.proposalStale) {
      dispatch({ type: "rejected" }); // nothing open on the server; just dismiss locally
      return;
    }
    dispatch({ type: "busy", busy: "rejecting" });
    try {
      await transport.reject(baseOf(s), p.proposal_id);
      dispatch({ type: "rejected" });
    } catch (e) {
      if (e instanceof ApiError && e.isStale) dispatch({ type: "rejected" });
      else
        dispatch({
          type: "error",
          scope: "reject",
          message: friendlyMessage(e),
        });
    }
  }, [transport]);

  const reset = useCallback(async () => {
    const s = stateRef.current.snapshot;
    if (!transport || !s) return;
    dispatch({ type: "busy", busy: "resetting" });
    try {
      const snap = await transport.reset(baseOf(s));
      dispatch({
        type: "loaded",
        snapshot: snap,
        resetBaseline: true,
        announce: `Scenario reset. Revision ${snap.revision}.`,
      });
    } catch (e) {
      dispatch({ type: "error", scope: "reset", message: friendlyMessage(e) });
    }
  }, [transport]);

  const refresh = useCallback(
    () => (transport ? load(transport, false) : undefined),
    [transport, load],
  );

  return {
    state,
    dispatch,
    transport,
    backend,
    preview,
    commit,
    reject,
    reset,
    refresh,
  };
}
