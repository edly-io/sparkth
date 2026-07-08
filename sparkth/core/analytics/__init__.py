"""Analytics subsystem: the emission gateway write path.

Holds the versioned event schema registry, the registered event schemas, and the
gateway that validates and lands events into the analytics database. Producers
will emit through this path in a later phase.
"""
