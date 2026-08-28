"""Contract tests.

The shared policy every provider must obey: retry transient failures, repair a
schema violation exactly once, audit every attempt, never silently substitute a
different provider. A new adapter must pass this suite to be registered.
"""
