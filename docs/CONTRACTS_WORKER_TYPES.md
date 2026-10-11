# Contract v1.1 proposal: agent, robot and human workers

**Status: proposed by Developer 2. Needs Developer 1's acknowledgement before the backend implements it.**
- **Frontend and fixture:** already accept these fields.
- **Compatibility:** every addition is optional, so v1 payloads still work.

Why: the YC "operating system for the physical world" brief asks how to route a job between an AI agent, a robot and a person, how to keep people safe beside robots, and how to measure reliability. v1 models only human technicians.

## Additive fields

| Model | Field | Type | Meaning / default |
|---|---|---|---|
| Technician (any worker) | `worker_type` | `"human" \| "robot" \| "agent"` | Missing = `"human"` |
| Technician | `certifications` | `string[]` | Safety/operating certifications, e.g. `"robot_cowork"`. Missing = `[]` |
| Job / JobInput | `allowed_worker_types` | `WorkerType[]` (non-empty) | Which kinds of worker may do the job. Missing = `["human"]` |
| Job / JobInput | `site_id` | `string \| null` | Physical site. Used by the co-presence safety rule |

The meaning of existing fields doesn't change:
- `max_service_min` doubles as a robot's battery/duty limit.
- `skills` covers robot capabilities (e.g. `"inspection"`) and agent capabilities (e.g. `"quoting"`).

## New hard rules (validator)

| Code | Rule |
|---|---|
| `WORKER_TYPE_NOT_ALLOWED` | The assigned worker's `worker_type` is not in the job's `allowed_worker_types` |
| `SAFETY_ROBOT_COPRESENCE` | A person and a robot have overlapping intervals at the same `site_id`, and the person lacks the `robot_cowork` certification |

These rules join the existing skill, window, travel, shift, capacity and frozen-work checks. Candidate evidence should give the reason a worker was excluded, e.g. `"Job needs robot or person; this is an AI agent"` or the safety violation message.

## Travel
`agent` workers work remotely: their travel is 0 and they need no map position. Robots and people use the existing grid travel model.

## Metrics (no contract change)
The UI computes per-type workforce figures from the schedule: done, in progress, planned, and load (scheduled minutes ÷ capacity). A backend `metrics.by_worker_type` would be welcome later. Until telemetry exists, it must not report reliability numbers it didn't measure.

## Example emergency routed across types
```json
{"type":"emergency","at_min":690,"job":{"id":"E01","customer":{"id":"C-E01","name":"Elm St HOA","site_name":"Main sewer line"},
 "location":{"x_km":6,"y_km":8,"latitude":null,"longitude":null},"required_skills":["inspection"],"priority":5,
 "duration_min":60,"earliest_start_min":690,"latest_start_min":810,"window_end_min":990,"soft_promised_start_min":null,
 "deadline_start_min":810,"release_min":690,"emergency":true,"locked":false,
 "allowed_worker_types":["robot","human"],"site_id":"SITE-E01"}}
```
