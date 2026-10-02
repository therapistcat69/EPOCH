from fastapi import APIRouter

from app.db.database import db_backend

router = APIRouter()


@router.get("/health")
async def health() -> dict:
    # "database" tells teammates whether Postgres or the local SQLite fallback is active.
    return {"status": "ok", "database": db_backend}
