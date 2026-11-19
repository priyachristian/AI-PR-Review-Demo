"""Application entrypoint for ASGI servers (e.g., uvicorn app:app).

Provides a clean, thin entrypoint without duplicate routes, circular imports, or side effects.
"""


__all__ = ["app"]
