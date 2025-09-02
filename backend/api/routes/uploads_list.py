from fastapi import APIRouter, Query, HTTPException
from sqlalchemy import select
from backend.api.database import async_session_maker
from backend.models import Upload

router = APIRouter(prefix="/uploads", tags=["uploads"])

@router.get("")
async def list_uploads(user_id: str = Query(...), limit: int = 20):
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id is required")
    if limit > 100:  # simple guard
        limit = 100
    async with async_session_maker() as session:
        res = await session.execute(
            select(Upload)
            .where(Upload.user_id == user_id)
            .order_by(Upload.created_at.desc())
            .limit(limit)
        )
        rows = res.scalars().all()
        return [
            {
              "id": r.id,
              "user_id": r.user_id,
              "filename": r.filename,
              "s3_key": getattr(r, "s3_key", None),
              "file_size": getattr(r, "file_size", None),
              "created_at": (r.created_at.isoformat() if getattr(r, "created_at", None) else None),
            } for r in rows
        ]
