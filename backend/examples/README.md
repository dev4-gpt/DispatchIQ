# Captured API payloads

These JSON files were produced by the running local operational service, not hand-authored success responses. They are development/reference fixtures. The committed live scenario was not changed by these captures.

- `scenario.json`: valid ten-technician/twenty-five-job baseline.
- `emergency-event.json`: feasible emergency body for the published fixture.
- `impossible-event.json`: a response deadline no technician can meet.
- `unavailable-event.json`: technician-unavailability event body.
- `preview-request.json`: full captured request; refresh its revision/epoch from your live GET scenario.
- `preview-response.json`: full independently validated proposal and comparison evidence.
- `impossible-preview-response.json`: honest no-plan result with candidate exclusion/constraint reasons.
- `openapi.json`: captured API schema, including typed collection responses.
- `MEASUREMENTS.json`: measured algorithm and HTTP timings, actual scheduling tradeoffs and capture method.

IDs, epochs, proposal expiry and measured timings belong to one local capture and are not reusable across server resets. The emergency ID must be unique in the current snapshot. Both strategies were evaluated on identical copies of the same committed state plus event. This is one reproducible synthetic example, not a generalized routing benchmark.

Core behavior and tests require no browser/network services after dependencies are installed. Developer 2 should use these files only while integrating, then call the real API; a failed API request must not silently load a successful fixture.
