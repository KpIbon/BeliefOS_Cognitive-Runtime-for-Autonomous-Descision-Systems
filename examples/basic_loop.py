"""End-to-end demo: ingest three correlated signals, watch the world
state escalate from stable → watch → alert as the evidence builds.

Run with:

    BELIEFOS_DATABASE_URL=sqlite:///./demo.db \
    python examples/basic_loop.py

Then visit http://localhost:8000 in another terminal to see the
dashboard update in real time (start the server separately with
``uvicorn beliefos.api.app:create_app --factory --port 8000``).
"""

from __future__ import annotations

import time

from beliefos import BeliefEngine
from beliefos.core.models import Observation, Severity


def main() -> None:
    engine = BeliefEngine.ready()

    subjects = ["cpu", "latency", "error_rate"]
    for i in range(8):
        for subject in subjects:
            # Each round we push all three subjects slightly higher.
            # A single high value would be noise; three correlated
            # values are a pattern — the correlation boost will fire.
            value = min(0.4 + i * 0.07, 0.97)
            engine.observe(
                Observation(
                    subject=subject,
                    value=value,
                    source="demo",
                    confidence=0.8,
                    metadata={"round": i},
                )
            )

        state = engine.world_state()
        decision = engine.decide()
        print(
            f"round {i}: "
            f"strength={state.overall_strength:.2f} "
            f"confidence={state.overall_confidence:.2f} "
            f"risk={state.risk_score:.2f} "
            f"state={decision.state.value}"
        )
        time.sleep(0.2)

    print()
    print("Final decision:", decision.action)
    if decision.state != Severity.STABLE:
        print("Drivers:", state.contributing_subjects)


if __name__ == "__main__":
    main()

