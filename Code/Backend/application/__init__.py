"""Application layer.

Use cases and the ports (abstract interfaces) they depend on. This layer knows
the domain and its own ports; it knows nothing about FastAPI, SQLAlchemy or any
concrete provider. Adapters for these ports live in ``infrastructure``.
"""
