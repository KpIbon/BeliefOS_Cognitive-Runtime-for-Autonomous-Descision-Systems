# BeliefOS HTTP API

> Version 1. All endpoints are JSON. The server is unauthenticated by
> default — put it behind an authenticating reverse proxy in
> production.

## Base URL

```
http://localhost:8000
```

When running via Docker Compose, the same URL works from the host.

## Endpoints

### `POST /observe`

Record an observation. Returns the updated belief.

**Request body**

```json
{
  "subject": "cpu",
  "value": 0.7,
  "source": "prometheus",
  "confidence": 0.8,
  "metadata": {"host": "web-1"}
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `subject` | string | yes | The dimension being measured. Normalized to lowercase. |
| `value` | float | yes | Normalized strength in `[0.0, 1.0]`. |
| `source` | string | no | Provenance label. Default `default`. |
| `confidence` | float | no | Source trust in `[0.0, 1.0]`. Default `0.5`. |
| `metadata` | object | no | Arbitrary context. |

**Response 201**

```json
{
  "observation": { ... },
  "belief": {
    "subject": "cpu",
    "strength": 0.62,
    "confidence": 0.45,
    "observation_count": 3,
    "last_value": 0.7,
    "last_source": "prometheus",
    "trend": "rising",
    "evidence": [ ... ],
    "previous_strength": 0.5,
    "last_updated": "2025-01-15T12:34:56.789Z"
  }
}
```

**Errors**

* `422` — request body failed validation (e.g. value out of range).

### `GET /beliefs`

List current beliefs.

**Query parameters**

| Name | Type | Default | Description |
|---|---|---|---|
| `subject` | string | — | Filter to a single subject. |
| `apply_decay` | bool | `true` | Apply time-based decay before returning. |

**Response 200**

```json
{
  "beliefs": [
    { ... Belief ... }
  ],
  "count": 1
}
```

### `GET /world-state`

Return the fused world state. Cached for
`BELIEFOS_CACHE_TTL_SECONDS` (default 15s).

**Response 200**

```json
{
  "overall_strength": 0.65,
  "overall_confidence": 0.42,
  "risk_score": 0.27,
  "trend": "rising",
  "contributing_subjects": ["cpu", "error_rate"],
  "summary": {},
  "generated_at": "2025-01-15T12:34:56.789Z"
}
```

### `GET /decide`

Return the current decision. Cached alongside `/world-state`.

**Response 200**

```json
{
  "state": "watch",
  "action": "Increase observation cadence. Surface to on-call dashboard.",
  "rationale": "World strength 0.65 above watch threshold 0.45 — increasing observation cadence.",
  "recommended_policies": [],
  "risk_score": 0.27,
  "world_state": { ... },
  "generated_at": "2025-01-15T12:34:56.789Z"
}
```

### `GET /report`

Full report: beliefs + world state + decision in one round-trip.
Useful for the dashboard's initial render.

**Response 200**

```json
{
  "beliefs": [ ... ],
  "world_state": { ... },
  "decision": { ... }
}
```

### `GET /health`

Liveness probe.

**Response 200**

```json
{
  "status": "ok",
  "version": "0.1.0",
  "environment": "development",
  "cache": "InMemoryCache",
  "cache_alive": true
}
```

### `GET /` (dashboard)

A self-contained HTML page that polls `/report` every second and
renders a live state. Chart.js is loaded from a pinned CDN.

### `GET /docs` and `GET /redoc`

Auto-generated OpenAPI / Swagger UI. Useful for exploring the schema
interactively.

## Error model

All errors are JSON:

```json
{ "detail": "human-readable message" }
```

* `400` — domain validation failure (e.g. a malformed observation).
* `404` — unknown subject when `?subject=` is used.
* `422` — FastAPI request validation.
* `500` — unexpected error; check server logs.

