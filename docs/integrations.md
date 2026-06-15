# Integrations

BeliefOS is designed to be the missing confidence layer between
external signals and downstream action. The integrations are
intentionally thin adapters — they translate domain-specific events
into `Observation`s, and translate `Decision`s back into the host
system's action vocabulary.

## OpenAI

`beliefos/integrations/openai.py` exposes `OpenAIBeliefAdapter`, which
turns a model output into a structured observation. Use it to feed
GPT-class signals (e.g. "is this conversation going off the rails?")
into the belief system.

```python
from beliefos.integrations.openai import OpenAIBeliefAdapter

adapter = OpenAIBeliefAdapter(api_key=os.environ["OPENAI_API_KEY"])
score = await adapter.score(
    subject="support_conversation_health",
    prompt="Rate the customer support conversation from 0 (terrible) to 1 (excellent).",
    text=transcript,
)
engine.observe(score)
```

## Anthropic

Same shape as the OpenAI adapter (`AnthropicBeliefAdapter`), but uses
the Anthropic SDK and supports Claude tool use. Both adapters normalize
to the same `Observation` shape, so the engine treats them identically.

## ROS2

`beliefos/integrations/ros2.py` provides a small bridge for streaming
topics into the engine and publishing decisions back out:

- Subscribes to any topic with a `std_msgs/Float32`-compatible payload.
- Publishes a `beliefos/Decision` message (custom type, JSON-encoded)
  whenever a new decision is computed.

The bridge runs in a separate process and is designed to be deployed
alongside a ROS2 control stack. See `examples/` for a minimal launch
file.

## Autonomous drones

`beliefos/integrations/drones.py` exposes a `DroneDecisionSink` that
maps a `Decision` to flight-controller commands. The mapping is
configurable via a small YAML file so the same runtime can drive
different airframes (MAVLink, PX4, custom):

```yaml
stable:
  action: hold
watch:
  action: loiter
  altitude_m: 30
alert:
  action: rtl
critical:
  action: land
  precision: true
```

## Adding your own

An integration is just two functions:

1. **Ingest** — produce `Observation` objects from the host's signal
   space. The only required fields are `subject`, `value` in [0, 1],
   and `source`. Optional `confidence`, `weight`, `note`, and
   `timestamp` improve the engine's calibration.
2. **Act** — consume `Decision` objects. Most integrations only need
   the `state` and `action` fields. `rationale` is intended for human
   consumers (dashboard, on-call); `recommended_policies` is a
   free-form list of suggestions.

The integration does not need to know about the engine's internals —
it just produces `Observation`s and consumes `Decision`s.
