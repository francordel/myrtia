"""FastAPI routers, one module per domain.

Each module exposes a `router: APIRouter`; `myrtia.api.app` is the composition
root that creates the app, adds middleware and includes these in order.
"""
