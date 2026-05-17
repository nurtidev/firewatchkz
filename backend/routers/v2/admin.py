"""
routers/v2/admin.py — Admin-only endpoints for FireWatch API v2.

GET /api/v2/admin/audit-log   — paginated audit_log listing (admin only).
GET /api/v2/admin/backup/status — last backup status (admin only).
"""
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import get_db
from services.auth import require_admin

router = APIRouter()

# ---------------------------------------------------------------------------
# In-memory backup status record (updated by the Celery task result if needed;
# for now just returns a stable informational response — no DB query required).
# ---------------------------------------------------------------------------
_last_backup_result: Optional[dict] = None


# ---------------------------------------------------------------------------
# Response schema
# ---------------------------------------------------------------------------


class AuditLogEntry(BaseModel):
    id: str
    user_id: Optional[str]
    action: str
    entity_type: str
    entity_id: Optional[str]
    changes: Optional[dict]
    ip_address: Optional[str]
    occurred_at: str


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


@router.get("/audit-log", response_model=List[AuditLogEntry])
async def list_audit_log(
    entity_type: Optional[str] = Query(None, description="Filter by entity type"),
    user_id: Optional[str] = Query(None, description="Filter by user ID"),
    from_ts: Optional[str] = Query(None, description="ISO datetime lower bound (inclusive)"),
    to_ts: Optional[str] = Query(None, description="ISO datetime upper bound (inclusive)"),
    limit: int = Query(50, ge=1, le=200, description="Page size (max 200)"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    session: AsyncSession = Depends(get_db),
    _current_user: dict = Depends(require_admin),
) -> List[AuditLogEntry]:
    """Return a paginated, filtered list of audit_log rows sorted newest-first.

    All filter parameters are optional and combinable.
    """
    filters = []
    params: dict = {"limit": limit, "offset": offset}

    if entity_type:
        filters.append("entity_type = :entity_type")
        params["entity_type"] = entity_type

    if user_id:
        filters.append("user_id = :user_id")
        params["user_id"] = user_id

    if from_ts:
        filters.append("occurred_at >= :from_ts")
        params["from_ts"] = from_ts

    if to_ts:
        filters.append("occurred_at <= :to_ts")
        params["to_ts"] = to_ts

    where_clause = ("WHERE " + " AND ".join(filters)) if filters else ""

    result = await session.execute(
        text(
            f"""
            SELECT id, user_id, action, entity_type, entity_id,
                   changes, ip_address, occurred_at
            FROM audit_log
            {where_clause}
            ORDER BY occurred_at DESC
            LIMIT :limit OFFSET :offset
            """
        ),
        params,
    )
    rows = result.mappings().all()

    return [
        AuditLogEntry(
            id=row["id"],
            user_id=row["user_id"],
            action=row["action"],
            entity_type=row["entity_type"],
            entity_id=row["entity_id"],
            changes=row["changes"],
            ip_address=row["ip_address"],
            occurred_at=str(row["occurred_at"]),
        )
        for row in rows
    ]


# ---------------------------------------------------------------------------
# Backup status endpoint
# ---------------------------------------------------------------------------


@router.get("/backup/status")
async def backup_status(
    _current_user: dict = Depends(require_admin),
) -> dict:
    """Return the status of the last scheduled database backup.

    The backup task runs daily at 02:00 UTC via Celery beat and uploads a
    pg_dump file to Cloudflare R2 at ``backups/postgres/{YYYY-MM-DD}.dump``.

    This endpoint reports the last known in-process result if available,
    otherwise directs operators to check R2 directly.
    """
    if _last_backup_result is not None:
        return _last_backup_result
    return {
        "last_run": None,
        "message": "check R2 for backup files — backups/postgres/{YYYY-MM-DD}.dump",
    }
