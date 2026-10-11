import { Bot, BrainCircuit, HardHat } from "lucide-react";
import type { Job, Technician, WorkerType } from "@/api/types";

export const workerType = (t: Technician): WorkerType => t.worker_type ?? "human";
export const allowedTypes = (j: Job): WorkerType[] => j.allowed_worker_types ?? ["human"];

export const WORKER = {
  human: { label: "Person", plural: "People", icon: HardHat },
  robot: { label: "Robot", plural: "Robots", icon: Bot },
  agent: { label: "AI agent", plural: "AI agents", icon: BrainCircuit },
} as const;

export const TYPE_ORDER: WorkerType[] = ["human", "robot", "agent"];

/** Agents work remotely: no travel, no position on the map. */
export const isRemote = (t: Technician) => workerType(t) === "agent";

export const CERT_LABEL: Record<string, string> = { robot_cowork: "Robot co-work certified" };
