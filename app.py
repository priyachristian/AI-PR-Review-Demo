"""Application entrypoint for ASGI servers (e.g., uvicorn app:app).

Provides a clean, thin entrypoint without duplicate routes, circular imports, or side effects.
"""

from app import module
__all__ = ["app"]
