"""
routers/v2/documents.py — Document upload and management endpoints (API v2).

POST   /api/v2/documents/upload              — multipart upload, enqueues normalize_document task
GET    /api/v2/documents/                    — list all operational cards
GET    /api/v2/documents/{card_id}           — single card detail
GET    /api/v2/documents/{card_id}/status    — polling: card_id + status
GET    /api/v2/documents/{card_id}/extraction — extraction row for a card
PATCH  /api/v2/documents/{card_id}/extraction — human corrections to extraction
POST   /api/v2/documents/{card_id}/approve   — approve card, upsert building record
DELETE /api/v2/documents/{card_id}           — soft delete (status='deleted') + storage cleanup
"""
import logging
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import get_db
from services.auth import require_analyst_or_above, require_inspector_or_above
from services.storage import get_storage, make_document_key

logger = logging.getLogger(__name__)

router = APIRouter()

# ---------------------------------------------------------------------------
# Allowed MIME types / extensions
# ---------------------------------------------------------------------------

ALLOWED_MIME_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/msword",
    "application/vnd.visio",
    "application/vnd.ms-visio.drawing",
    "image/jpeg",
    "image/png",
}

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".doc", ".vsd", ".jpg", ".jpeg", ".png"}


def _guess_mime(filename: str) -> str:
    """Return a basic MIME type based on file extension."""
    import mimetypes
    mime, _ = mimetypes.guess_type(filename)
    return mime or "application/octet-stream"


def _validate_file(upload: UploadFile) -> str:
    """Validate file type and return effective MIME type. Raises HTTPException on failure."""
    import pathlib

    ext = pathlib.Path(upload.filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Неподдерживаемый тип файла: {ext}. "
                   f"Допустимые форматы: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    content_type = upload.content_type or _guess_mime(upload.filename or "")
    # Normalise content-type sent by some browsers for .doc files
    if ext == ".doc" and content_type == "application/octet-stream":
        content_type = "application/msword"
    return content_type


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class UploadResponse(BaseModel):
    card_id: str
    status: str
    upload_url: str


class CardSummary(BaseModel):
    id: str
    status: str
    file_name: str
    file_mime: Optional[str]
    uploaded_at: str
    building_id: Optional[str]
    uploaded_by: Optional[str]
    thumbnail_key: Optional[str]
    converted_key: Optional[str]


class CardDetail(CardSummary):
    file_url: str
    file_size_bytes: Optional[int]
    extraction_id: Optional[str]
    approved_at: Optional[str]
    approved_by: Optional[str]


class CardStatusResponse(BaseModel):
    card_id: str
    status: str
    processed_at: Optional[str]


class ExtractionResponse(BaseModel):
    id: str
    card_id: Optional[str]
    model_version: str
    extracted_data: dict
    field_confidences: dict
    vulnerabilities: Optional[dict]
    extraction_cost_usd: Optional[float]
    duration_ms: Optional[int]
    human_corrections: Optional[dict]
    created_at: str


class ExtractionPatch(BaseModel):
    field_corrections: dict
    reviewer_id: Optional[str] = None
    notes: Optional[str] = None


class ApproveRequest(BaseModel):
    approved_by: Optional[str] = None  # user_id


class ApproveResponse(BaseModel):
    card_id: str
    building_id: str
    status: str  # 'approved'


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/upload", response_model=UploadResponse, status_code=200)
async def upload_document(
    file: UploadFile = File(...),
    building_id: Optional[str] = Form(None),
    uploaded_by: Optional[str] = Form(None),
    session: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_inspector_or_above),
) -> UploadResponse:
    """
    Accept a document upload (PDF/DOCX/DOC/VSD/JPG/PNG), persist it to storage,
    create an operational_cards record, and enqueue the normalize_document Celery task.
    """
    content_type = _validate_file(file)

    # Read file content
    content = await file.read()
    file_size = len(content)

    # Generate a new card ID and derive the storage key
    card_id = str(uuid.uuid4())
    user_id = uploaded_by or "anonymous"
    storage_key = make_document_key(user_id, card_id, file.filename or "upload")

    # Upload to storage
    storage = get_storage()
    upload_url = await storage.upload(storage_key, content, content_type)

    # Insert card record
    await session.execute(
        text(
            """
            INSERT INTO operational_cards
                (id, building_id, uploaded_by, file_url, file_name,
                 file_size_bytes, file_mime, status)
            VALUES
                (:id, :building_id, :uploaded_by, :file_url, :file_name,
                 :file_size_bytes, :file_mime, 'uploaded')
            """
        ),
        {
            "id": card_id,
            "building_id": building_id,
            "uploaded_by": uploaded_by,
            "file_url": storage_key,
            "file_name": file.filename or "upload",
            "file_size_bytes": file_size,
            "file_mime": content_type,
        },
    )
    await session.commit()

    # Enqueue Celery task — import here to avoid circular deps at module load
    try:
        from workers.documents import normalize_document  # noqa: PLC0415
        normalize_document.delay(card_id)
        logger.info("Enqueued normalize_document for card_id=%s", card_id)
    except Exception as exc:  # broker not available in tests / dev
        logger.warning("Could not enqueue normalize_document: %s", exc)

    return UploadResponse(card_id=card_id, status="uploaded", upload_url=upload_url)


@router.get("/", response_model=List[CardSummary])
async def list_documents(
    building_id: Optional[str] = None,
    status: Optional[str] = None,
    session: AsyncSession = Depends(get_db),
) -> List[CardSummary]:
    """Return all operational cards, optionally filtered by building_id or status."""
    filters = []
    params: dict = {}

    if building_id:
        filters.append("building_id = :building_id")
        params["building_id"] = building_id
    if status:
        filters.append("status = :status")
        params["status"] = status

    where_clause = ("WHERE " + " AND ".join(filters)) if filters else ""

    result = await session.execute(
        text(
            f"""
            SELECT id, status, file_name, file_mime, uploaded_at,
                   building_id, uploaded_by, thumbnail_key, converted_key
            FROM operational_cards
            {where_clause}
            ORDER BY uploaded_at DESC
            """
        ),
        params,
    )
    rows = result.mappings().all()

    return [
        CardSummary(
            id=row["id"],
            status=row["status"],
            file_name=row["file_name"],
            file_mime=row["file_mime"],
            uploaded_at=str(row["uploaded_at"]),
            building_id=row["building_id"],
            uploaded_by=row["uploaded_by"],
            thumbnail_key=row["thumbnail_key"],
            converted_key=row["converted_key"],
        )
        for row in rows
    ]


# ---------------------------------------------------------------------------
# F-9 — Status polling, extraction CRUD, soft delete
# NOTE: these sub-resource routes MUST be registered before /{card_id} so that
# FastAPI does not greedily match "status" or "extraction" as a card_id value.
# ---------------------------------------------------------------------------


@router.get("/{card_id}/status", response_model=CardStatusResponse)
async def get_card_status(
    card_id: str,
    session: AsyncSession = Depends(get_db),
) -> CardStatusResponse:
    """Return just the status fields needed for UI polling."""
    result = await session.execute(
        text("SELECT id, status, approved_at FROM operational_cards WHERE id = :card_id"),
        {"card_id": card_id},
    )
    row = result.mappings().first()

    if row is None:
        raise HTTPException(status_code=404, detail="Карточка не найдена")

    return CardStatusResponse(
        card_id=row["id"],
        status=row["status"],
        # operational_cards has no processed_at column — use approved_at as the closest proxy
        processed_at=str(row["approved_at"]) if row["approved_at"] else None,
    )


@router.get("/{card_id}/extraction", response_model=ExtractionResponse)
async def get_card_extraction(
    card_id: str,
    session: AsyncSession = Depends(get_db),
) -> ExtractionResponse:
    """Return the card_extractions row linked to this card."""
    # Resolve extraction_id from operational_cards
    card_result = await session.execute(
        text("SELECT extraction_id FROM operational_cards WHERE id = :card_id"),
        {"card_id": card_id},
    )
    card_row = card_result.mappings().first()

    if card_row is None:
        raise HTTPException(status_code=404, detail="Карточка не найдена")

    extraction_id = card_row["extraction_id"]
    if not extraction_id:
        raise HTTPException(status_code=404, detail="Extraction not available")

    ext_result = await session.execute(
        text(
            """
            SELECT id, card_id, model_version, extracted_data, field_confidences,
                   vulnerabilities, extraction_cost_usd, duration_ms,
                   human_corrections, created_at
            FROM card_extractions
            WHERE id = :extraction_id
            """
        ),
        {"extraction_id": extraction_id},
    )
    ext_row = ext_result.mappings().first()

    if ext_row is None:
        raise HTTPException(status_code=404, detail="Extraction not available")

    return ExtractionResponse(
        id=ext_row["id"],
        card_id=ext_row["card_id"],
        model_version=ext_row["model_version"],
        extracted_data=ext_row["extracted_data"] or {},
        field_confidences=ext_row["field_confidences"] or {},
        vulnerabilities=ext_row["vulnerabilities"],
        extraction_cost_usd=float(ext_row["extraction_cost_usd"]) if ext_row["extraction_cost_usd"] is not None else None,
        duration_ms=ext_row["duration_ms"],
        human_corrections=ext_row["human_corrections"],
        created_at=str(ext_row["created_at"]),
    )


@router.patch("/{card_id}/extraction", response_model=ExtractionResponse)
async def patch_card_extraction(
    card_id: str,
    body: ExtractionPatch,
    session: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_inspector_or_above),
) -> ExtractionResponse:
    """Merge human field corrections into the extraction row and write an audit log entry."""
    import json as _json

    # Resolve extraction_id
    card_result = await session.execute(
        text("SELECT extraction_id FROM operational_cards WHERE id = :card_id"),
        {"card_id": card_id},
    )
    card_row = card_result.mappings().first()

    if card_row is None:
        raise HTTPException(status_code=404, detail="Карточка не найдена")

    extraction_id = card_row["extraction_id"]
    if not extraction_id:
        raise HTTPException(status_code=404, detail="Extraction not available")

    # Load current extraction
    ext_result = await session.execute(
        text(
            """
            SELECT id, card_id, model_version, extracted_data, field_confidences,
                   vulnerabilities, extraction_cost_usd, duration_ms,
                   human_corrections, created_at
            FROM card_extractions
            WHERE id = :extraction_id
            """
        ),
        {"extraction_id": extraction_id},
    )
    ext_row = ext_result.mappings().first()

    if ext_row is None:
        raise HTTPException(status_code=404, detail="Extraction not available")

    # Merge corrections into existing human_corrections JSON
    existing_corrections: dict = dict(ext_row["human_corrections"] or {})
    existing_corrections.update(body.field_corrections)

    await session.execute(
        text(
            "UPDATE card_extractions SET human_corrections = :corrections WHERE id = :extraction_id"
        ),
        {
            "corrections": _json.dumps(existing_corrections),
            "extraction_id": extraction_id,
        },
    )

    # Write audit log
    await session.execute(
        text(
            """
            INSERT INTO audit_log (action, entity_type, entity_id, user_id, changes)
            VALUES ('extraction_corrected', 'card_extraction', :entity_id, :user_id, :changes)
            """
        ),
        {
            "entity_id": extraction_id,
            "user_id": body.reviewer_id,
            "changes": _json.dumps(body.field_corrections),
        },
    )

    await session.commit()

    return ExtractionResponse(
        id=ext_row["id"],
        card_id=ext_row["card_id"],
        model_version=ext_row["model_version"],
        extracted_data=ext_row["extracted_data"] or {},
        field_confidences=ext_row["field_confidences"] or {},
        vulnerabilities=ext_row["vulnerabilities"],
        extraction_cost_usd=float(ext_row["extraction_cost_usd"]) if ext_row["extraction_cost_usd"] is not None else None,
        duration_ms=ext_row["duration_ms"],
        human_corrections=existing_corrections,
        created_at=str(ext_row["created_at"]),
    )


# ---------------------------------------------------------------------------
# F-8 — Document approval → buildings upsert
# Registered before /{card_id} DELETE and GET so FastAPI matches /approve first.
# ---------------------------------------------------------------------------

# Hazard class (Ф1-Ф5) → building_type vocabulary
_HAZARD_TO_TYPE: dict[str, str] = {
    "Ф1": "residential",
    "Ф2": "social",
    "Ф3": "commercial",
    "Ф4": "educational",
    "Ф5": "industrial",
}

DEFAULT_CITY_ID = "astana"


def _extract_value(field_dict, default=None):
    """Extract value from a FieldWithConfidence dict produced by AI extraction."""
    if not field_dict or not isinstance(field_dict, dict):
        return default
    return field_dict.get("value", default)


@router.post("/{card_id}/approve", response_model=ApproveResponse, status_code=200)
async def approve_document(
    card_id: str,
    body: ApproveRequest,
    session: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_analyst_or_above),
) -> ApproveResponse:
    """
    Approve an operational card:
    1. Verify card exists and is not deleted.
    2. Load linked card_extractions row.
    3. Map extracted_data → buildings columns.
    4. UPSERT into buildings (source='document_extract', external_id=card_id).
    5. Update operational_cards.status='approved', set building_id.
    6. Write audit_log entry.
    7. Return {card_id, building_id, status='approved'}.
    """
    import json as _json

    approved_by = body.approved_by

    # ------------------------------------------------------------------
    # 1. Load the operational card
    # ------------------------------------------------------------------
    card_result = await session.execute(
        text(
            """
            SELECT id, status, extraction_id, file_name
            FROM operational_cards
            WHERE id = :card_id
            """
        ),
        {"card_id": card_id},
    )
    card_row = card_result.mappings().first()

    if card_row is None:
        raise HTTPException(status_code=404, detail="Карточка не найдена")

    if card_row["status"] == "deleted":
        raise HTTPException(status_code=422, detail="Нельзя утвердить удалённую карточку")

    # ------------------------------------------------------------------
    # 2. Load the extraction row
    # ------------------------------------------------------------------
    extraction_id = card_row["extraction_id"]
    if not extraction_id:
        raise HTTPException(
            status_code=422,
            detail="Карточка не имеет связанного извлечения. Сначала выполните извлечение.",
        )

    ext_result = await session.execute(
        text(
            """
            SELECT id, extracted_data
            FROM card_extractions
            WHERE id = :extraction_id
            """
        ),
        {"extraction_id": extraction_id},
    )
    ext_row = ext_result.mappings().first()

    if ext_row is None:
        raise HTTPException(status_code=422, detail="Данные извлечения не найдены")

    # ------------------------------------------------------------------
    # 3. Map extracted_data → building fields
    # ------------------------------------------------------------------
    extracted_data: dict = ext_row["extracted_data"] or {}

    address = _extract_value(extracted_data.get("address")) or card_row["file_name"]
    address_norm = address.lower().strip() if address else ""

    hazard_class_raw = _extract_value(extracted_data.get("hazard_class"))
    building_type = _HAZARD_TO_TYPE.get(hazard_class_raw or "", None)
    fire_hazard_class = hazard_class_raw

    floors_above = _extract_value(extracted_data.get("floors_above"))
    floors_below = _extract_value(extracted_data.get("floors_below"))
    height_m = _extract_value(extracted_data.get("height_m"))
    total_area_sqm = _extract_value(extracted_data.get("total_area_sqm"))
    year_built = _extract_value(extracted_data.get("year_built"))
    wall_material = _extract_value(extracted_data.get("wall_material"))
    fire_resistance_raw = _extract_value(extracted_data.get("fire_resistance_degree"))

    # fire_resistance_degree may come as Roman numerals (I-V) or integers (1-5)
    _roman_map = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5}
    if isinstance(fire_resistance_raw, str):
        fire_resistance: Optional[int] = _roman_map.get(fire_resistance_raw.strip().upper())
    elif isinstance(fire_resistance_raw, int):
        fire_resistance = fire_resistance_raw
    else:
        fire_resistance = None

    # Determine city_id — operational_cards has no city_id column, so try
    # to resolve from extracted city name, then fall back to default.
    city_name = _extract_value(extracted_data.get("city"))
    if city_name:
        city_lookup = await session.execute(
            text("SELECT id FROM cities WHERE LOWER(name) = LOWER(:name) LIMIT 1"),
            {"name": city_name},
        )
        city_row = city_lookup.mappings().first()
        city_id: str = city_row["id"] if city_row else DEFAULT_CITY_ID
    else:
        city_id = DEFAULT_CITY_ID

    # ------------------------------------------------------------------
    # 4. UPSERT into buildings
    # ------------------------------------------------------------------
    upsert_result = await session.execute(
        text(
            """
            INSERT INTO buildings
                (city_id, address, address_norm, building_type, floors_above, floors_below,
                 height_m, total_area_sqm, year_built, wall_material, fire_resistance,
                 fire_hazard_class, source, external_id, updated_at)
            VALUES
                (:city_id, :address, :address_norm, :building_type, :floors_above, :floors_below,
                 :height_m, :total_area_sqm, :year_built, :wall_material, :fire_resistance,
                 :fire_hazard_class, 'document_extract', :external_id, NOW())
            ON CONFLICT (source, external_id) DO UPDATE SET
                address           = EXCLUDED.address,
                address_norm      = EXCLUDED.address_norm,
                building_type     = EXCLUDED.building_type,
                floors_above      = EXCLUDED.floors_above,
                floors_below      = EXCLUDED.floors_below,
                height_m          = EXCLUDED.height_m,
                total_area_sqm    = EXCLUDED.total_area_sqm,
                year_built        = EXCLUDED.year_built,
                wall_material     = EXCLUDED.wall_material,
                fire_resistance   = EXCLUDED.fire_resistance,
                fire_hazard_class = EXCLUDED.fire_hazard_class,
                updated_at        = NOW()
            RETURNING id
            """
        ),
        {
            "city_id": city_id,
            "address": address,
            "address_norm": address_norm,
            "building_type": building_type,
            "floors_above": floors_above,
            "floors_below": floors_below,
            "height_m": height_m,
            "total_area_sqm": total_area_sqm,
            "year_built": year_built,
            "wall_material": wall_material,
            "fire_resistance": fire_resistance,
            "fire_hazard_class": fire_hazard_class,
            "external_id": card_id,
        },
    )
    building_id: str = upsert_result.scalar_one()

    # ------------------------------------------------------------------
    # 5. Update operational_cards
    # ------------------------------------------------------------------
    await session.execute(
        text(
            """
            UPDATE operational_cards
            SET status = 'approved',
                building_id = :building_id,
                approved_at = NOW(),
                approved_by = :approved_by
            WHERE id = :card_id
            """
        ),
        {"building_id": building_id, "approved_by": approved_by, "card_id": card_id},
    )

    # ------------------------------------------------------------------
    # 6. Audit log
    # ------------------------------------------------------------------
    await session.execute(
        text(
            """
            INSERT INTO audit_log (action, entity_type, entity_id, changes, occurred_at)
            VALUES ('document_approved', 'operational_card', :card_id, :changes::json, NOW())
            """
        ),
        {
            "card_id": card_id,
            "changes": _json.dumps({"building_id": building_id, "approved_by": approved_by}),
        },
    )

    await session.commit()

    # ------------------------------------------------------------------
    # 7. Return response
    # ------------------------------------------------------------------
    return ApproveResponse(card_id=card_id, building_id=building_id, status="approved")


@router.delete("/{card_id}", status_code=204)
async def delete_document(
    card_id: str,
    session: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_analyst_or_above),
) -> Response:
    """Soft delete: set status='deleted', attempt storage cleanup, write audit log."""
    import json as _json

    card_result = await session.execute(
        text("SELECT id, file_url FROM operational_cards WHERE id = :card_id"),
        {"card_id": card_id},
    )
    card_row = card_result.mappings().first()

    if card_row is None:
        raise HTTPException(status_code=404, detail="Карточка не найдена")

    # Soft delete in DB
    await session.execute(
        text("UPDATE operational_cards SET status = 'deleted' WHERE id = :card_id"),
        {"card_id": card_id},
    )

    # Write audit log
    await session.execute(
        text(
            """
            INSERT INTO audit_log (action, entity_type, entity_id, changes)
            VALUES ('document_deleted', 'operational_card', :entity_id, :changes)
            """
        ),
        {
            "entity_id": card_id,
            "changes": _json.dumps({"file_url": card_row["file_url"]}),
        },
    )

    await session.commit()

    # Best-effort storage cleanup — do not fail if storage errors
    try:
        storage = get_storage()
        await storage.delete(card_row["file_url"])
    except Exception as exc:
        logger.warning("Could not delete file from storage (key=%s): %s", card_row["file_url"], exc)

    return Response(status_code=204)


# ---------------------------------------------------------------------------
# Single card detail — registered LAST so sub-resource paths match first
# ---------------------------------------------------------------------------


@router.get("/{card_id}", response_model=CardDetail)
async def get_document(
    card_id: str,
    session: AsyncSession = Depends(get_db),
) -> CardDetail:
    """Return a single operational card by ID."""
    result = await session.execute(
        text(
            """
            SELECT id, status, file_name, file_mime, uploaded_at, building_id,
                   uploaded_by, thumbnail_key, converted_key, file_url,
                   file_size_bytes, extraction_id, approved_at, approved_by
            FROM operational_cards
            WHERE id = :card_id
            """
        ),
        {"card_id": card_id},
    )
    row = result.mappings().first()

    if row is None:
        raise HTTPException(status_code=404, detail="Карточка не найдена")

    return CardDetail(
        id=row["id"],
        status=row["status"],
        file_name=row["file_name"],
        file_mime=row["file_mime"],
        uploaded_at=str(row["uploaded_at"]),
        building_id=row["building_id"],
        uploaded_by=row["uploaded_by"],
        thumbnail_key=row["thumbnail_key"],
        converted_key=row["converted_key"],
        file_url=row["file_url"],
        file_size_bytes=row["file_size_bytes"],
        extraction_id=row["extraction_id"],
        approved_at=str(row["approved_at"]) if row["approved_at"] else None,
        approved_by=row["approved_by"],
    )
