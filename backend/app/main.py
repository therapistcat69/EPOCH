import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.db.database import init_db
from app.errors import register_error_handlers
from app.routes import analytics, auth, channels, health, me_channel, ml, reporting, sync, youtube

logging.basicConfig(level=logging.INFO)
# httpx logs full request URLs at INFO, which would include the API key query param.
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)


@asynccontextmanager
async def lifespan(_: FastAPI):
    await init_db()
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="Retention Predictor API", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[get_settings().frontend_url],
        allow_credentials=True,  # session cookie (HttpOnly) is sent from the frontend origin only
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )
    register_error_handlers(app)
    for r in (
        health.router, youtube.router, channels.router, ml.router, auth.router,
        me_channel.router, analytics.router, sync.router, reporting.router,
    ):
        app.include_router(r)
    return app


app = create_app()
