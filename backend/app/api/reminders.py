"""提醒 API：列表与删除（工具执行产物展示）。"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.models import ReminderOut
from app.storage import db

router = APIRouter(prefix="/api/reminders", tags=["reminders"])


@router.get("", response_model=list[ReminderOut])
def list_reminders(limit: int = 50) -> list[ReminderOut]:
    rows = db.list_reminders(limit=min(max(limit, 1), 200))
    return [ReminderOut(**r) for r in rows]


@router.delete("/{reminder_id}")
def delete_reminder(reminder_id: int) -> dict[str, bool]:
    if not db.delete_reminder(reminder_id):
        raise HTTPException(status_code=404, detail="提醒不存在")
    return {"deleted": True}
