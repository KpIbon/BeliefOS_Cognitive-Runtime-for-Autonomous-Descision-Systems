"""Future-facing integrations.

Each module in this package is a thin adapter that maps external signals
into ``Observation`` instances and feeds them into a ``BeliefEngine``. They
are designed to be safe to import even when the third-party SDK isn't
installed: we only require it at call time.
"""
