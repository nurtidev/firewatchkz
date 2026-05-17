"""
workers/documents.py — Celery tasks for document processing pipeline.

normalize_document  — convert to PDF, generate thumbnail (F-3)
extract_document    — Claude extraction stub (F-6)
analyze_vulnerabilities — Claude vulnerability analysis (F-7)
"""
import json
import logging
import os
import subprocess
import tempfile
from pathlib import Path
from typing import List, Optional

import anthropic

from celery_app import celery_app

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sync_db_conn():
    """Return a psycopg (sync) connection using DATABASE_URL env var."""
    import psycopg  # noqa: PLC0415 — optional at import time

    db_url = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://firewatch:firewatch_dev@localhost:5432/firewatch",
    )
    # psycopg uses postgresql:// scheme (no +asyncpg driver qualifier)
    sync_url = db_url.replace("postgresql+asyncpg://", "postgresql://").replace(
        "postgresql+psycopg://", "postgresql://"
    )
    return psycopg.connect(sync_url)


def _download_file_sync(storage_key: str) -> bytes:
    """Download a file from storage synchronously via asyncio.run."""
    import asyncio  # noqa: PLC0415

    from services.storage import get_storage  # noqa: PLC0415

    storage = get_storage()

    async def _dl() -> bytes:
        return await storage.download(storage_key)

    return asyncio.run(_dl())


def _upload_file_sync(key: str, content: bytes, content_type: str) -> str:
    """Upload a file to storage synchronously via asyncio.run."""
    import asyncio  # noqa: PLC0415

    from services.storage import get_storage  # noqa: PLC0415

    storage = get_storage()

    async def _ul() -> str:
        return await storage.upload(key, content, content_type)

    return asyncio.run(_ul())


def _convert_to_pdf(src_path: Path, out_dir: Path) -> Optional[Path]:
    """
    Convert a DOCX/DOC/VSD file to PDF using LibreOffice headless.

    Returns the path to the generated PDF, or None if conversion failed.
    """
    try:
        result = subprocess.run(
            [
                "libreoffice",
                "--headless",
                "--convert-to",
                "pdf",
                "--outdir",
                str(out_dir),
                str(src_path),
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            logger.error(
                "LibreOffice conversion failed for %s: %s",
                src_path,
                result.stderr,
            )
            return None

        # LibreOffice outputs <basename>.pdf
        expected_pdf = out_dir / (src_path.stem + ".pdf")
        if expected_pdf.exists():
            return expected_pdf

        # Fallback: find any PDF written to out_dir
        pdfs = list(out_dir.glob("*.pdf"))
        return pdfs[0] if pdfs else None

    except FileNotFoundError:
        logger.warning("libreoffice not found — skipping conversion")
        return None
    except subprocess.TimeoutExpired:
        logger.error("LibreOffice conversion timed out for %s", src_path)
        return None


def _generate_thumbnail(pdf_path: Path, width_px: int = 400) -> Optional[bytes]:
    """
    Render the first page of a PDF to a JPEG thumbnail.

    Tries pdf2image first; falls back to Pillow alone (which can open PDFs
    on some platforms via Ghostscript). Returns JPEG bytes or None.
    """
    import io  # noqa: PLC0415

    # --- attempt 1: pdf2image (poppler) ---
    try:
        from pdf2image import convert_from_path  # noqa: PLC0415

        images = convert_from_path(str(pdf_path), first_page=1, last_page=1, dpi=72)
        if images:
            img = images[0]
            ratio = width_px / img.width
            new_height = int(img.height * ratio)
            img = img.resize((width_px, new_height))
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=85)
            return buf.getvalue()
    except Exception as exc:  # pdf2image not installed or poppler missing
        logger.debug("pdf2image unavailable (%s), trying Pillow", exc)

    # --- attempt 2: Pillow direct (requires Ghostscript on PATH) ---
    try:
        from PIL import Image  # noqa: PLC0415

        img = Image.open(str(pdf_path))  # may work with GS plugin
        img.load()
        ratio = width_px / img.width
        new_height = int(img.height * ratio)
        img = img.resize((width_px, new_height))
        buf = io.BytesIO()
        img.convert("RGB").save(buf, format="JPEG", quality=85)
        return buf.getvalue()
    except Exception as exc:
        logger.warning("Pillow thumbnail generation failed: %s", exc)

    return None


# ---------------------------------------------------------------------------
# Vulnerability analysis — Claude Sonnet pass (F-7)
# ---------------------------------------------------------------------------

_anthropic_client: Optional[anthropic.Anthropic] = None


def _get_anthropic_client() -> anthropic.Anthropic:
    """Return a module-level singleton Anthropic sync client."""
    global _anthropic_client
    if _anthropic_client is None:
        _anthropic_client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY
    return _anthropic_client


VULNERABILITY_SYSTEM_PROMPT = """
Ты — эксперт по пожарной безопасности и нормативным требованиям МЧС Республики Казахстан.

Проанализируй извлечённые данные оперативной карточки объекта и выяви нарушения и уязвимости пожарной безопасности.

Для каждой уязвимости укажи:
- severity: critical/high/medium/low
- description: конкретное описание нарушения на русском языке
- regulation_violated: ссылка на нарушенный норматив (НПБ РК, ГОСТ, СНиП) или null
- recommended_action: конкретная рекомендация по устранению

Ориентируйся на:
- Отсутствие или неисправность систем обнаружения (critical если нет совсем)
- Недостаточное количество эвакуационных выходов (по нормам)
- Отсутствие дымоудаления (high для зданий > 9 этажей)
- Устаревший год постройки без данных о капремонте (medium)
- Опасные материалы без указания мер защиты (high-critical)
- Несоответствие категории пожарной опасности типу здания

Возвращай ТОЛЬКО валидный JSON массив объектов уязвимостей.
"""


def _analyze_with_claude(extracted_data: dict) -> List[dict]:
    """Call Claude Sonnet to identify vulnerabilities. Returns list of vulnerability dicts."""
    prompt = (
        "Данные оперативной карточки:\n"
        + json.dumps(extracted_data, ensure_ascii=False, indent=2)
        + "\n\nВыяви все уязвимости и нарушения пожарной безопасности. Возврати JSON массив."
    )

    client = _get_anthropic_client()
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        system=VULNERABILITY_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )

    text = response.content[0].text.strip()
    # Strip markdown code fences if present
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        logger.warning("_analyze_with_claude: failed to parse JSON response — returning empty list")
        return []


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------


@celery_app.task(
    bind=True,
    name="workers.documents.normalize_document",
    max_retries=3,
    default_retry_delay=30,
    autoretry_for=(Exception,),
)
def normalize_document(self, card_id: str) -> dict:
    """
    Convert uploaded document to PDF (if needed) and generate a thumbnail.

    Steps:
    1. Fetch card record from DB (status = 'uploaded')
    2. Update status -> 'converting'
    3. Download original file from storage to /tmp
    4. Convert to PDF if format requires it (LibreOffice headless for DOCX/DOC/VSD)
    5. Generate thumbnail (first page -> JPEG 400px wide)
    6. Upload converted PDF + thumbnail back to storage
    7. Update card record: converted_key, thumbnail_key, status -> 'ready_for_extraction'
    """
    logger.info("normalize_document started for card_id=%s", card_id)

    # -- 1. Fetch card from DB --------------------------------------------------
    conn = _sync_db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, file_url, file_name, file_mime, uploaded_by "
                "FROM operational_cards WHERE id = %s",
                (card_id,),
            )
            row = cur.fetchone()

        if row is None:
            logger.error("normalize_document: card %s not found", card_id)
            return {"card_id": card_id, "status": "error", "detail": "card not found"}

        _id, file_url, file_name, file_mime, uploaded_by = row
        user_id = uploaded_by or "anonymous"

        # -- 2. Mark as converting ---------------------------------------------
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE operational_cards SET status = 'converting' WHERE id = %s",
                (card_id,),
            )
        conn.commit()

        # -- 3. Download original file to /tmp ---------------------------------
        original_bytes = _download_file_sync(file_url)

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            src_path = tmp_path / (file_name or "original")
            src_path.write_bytes(original_bytes)

            mime = (file_mime or "").lower()
            ext = Path(file_name or "").suffix.lower()

            # -- 4. Determine if conversion is needed --------------------------
            needs_conversion = ext in {".docx", ".doc", ".vsd"} or mime in {
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                "application/msword",
                "application/vnd.visio",
                "application/vnd.ms-visio.drawing",
            }

            if needs_conversion:
                pdf_path = _convert_to_pdf(src_path, tmp_path)
            elif ext == ".pdf" or mime == "application/pdf":
                pdf_path = src_path
            else:
                # Image file (JPG/PNG) — no conversion needed
                pdf_path = None

            # -- 5 & 6. Thumbnail + upload ------------------------------------
            from services.storage import make_converted_key, make_thumbnail_key  # noqa: PLC0415

            converted_key: Optional[str] = None
            thumbnail_key: Optional[str] = None

            if pdf_path is not None and pdf_path.exists():
                # Upload converted/original PDF only if it was actually converted
                if needs_conversion:
                    pdf_bytes = pdf_path.read_bytes()
                    c_key = make_converted_key(user_id, card_id)
                    _upload_file_sync(c_key, pdf_bytes, "application/pdf")
                    converted_key = c_key

                # Generate thumbnail from PDF
                thumb_bytes = _generate_thumbnail(pdf_path)
                if thumb_bytes:
                    t_key = make_thumbnail_key(user_id, card_id)
                    _upload_file_sync(t_key, thumb_bytes, "image/jpeg")
                    thumbnail_key = t_key

            # -- 7. Update DB --------------------------------------------------
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE operational_cards
                    SET status = 'ready_for_extraction',
                        converted_key = %s,
                        thumbnail_key = %s
                    WHERE id = %s
                    """,
                    (converted_key, thumbnail_key, card_id),
                )
            conn.commit()

    finally:
        conn.close()

    logger.info("normalize_document finished for card_id=%s — chaining extract_document", card_id)

    # Chain: kick off extraction now that PDF is ready.
    extract_document.delay(card_id)

    return {"card_id": card_id, "status": "ready_for_extraction"}


def _run_async(coro):
    """Run an async coroutine from a synchronous (Celery worker) context."""
    import asyncio  # noqa: PLC0415

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Already inside a running event loop — push into a thread.
            import concurrent.futures  # noqa: PLC0415

            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, coro)
                return future.result()
        return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


@celery_app.task(
    bind=True,
    name="workers.documents.extract_document",
    max_retries=3,
    default_retry_delay=60,
    # Do NOT use autoretry_for here — we retry selectively on APIError only.
)
def extract_document(self, card_id: str) -> dict:
    """
    Run Claude extraction on a normalized PDF/image operational card.

    Steps:
    1. Load operational_card from DB (must have status 'ready_for_extraction').
    2. Download PDF/image bytes from storage.
    3. Call DocumentExtractor (async) via _run_async bridge.
    4. Insert ExtractionResult into card_extractions table.
    5. Update operational_cards: status='extracted', extraction_id=<new id>.
    6. Return {"card_id", "extraction_id", "status", "cost_usd"}.

    Retries up to 3 times on Anthropic API errors with exponential back-off.
    """
    import json  # noqa: PLC0415
    import uuid  # noqa: PLC0415

    logger.info("extract_document started for card_id=%s", card_id)

    conn = _sync_db_conn()
    try:
        # ------------------------------------------------------------------
        # 1. Fetch card record
        # ------------------------------------------------------------------
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, file_url, file_mime, converted_key, status, building_id "
                "FROM operational_cards WHERE id = %s",
                (card_id,),
            )
            row = cur.fetchone()

        if row is None:
            logger.warning("extract_document: card %s not found", card_id)
            return {"card_id": card_id, "status": "not_found"}

        _id, file_url, file_mime, converted_key, status, building_id = row

        if status != "ready_for_extraction":
            logger.warning(
                "extract_document: card %s has status '%s', expected 'ready_for_extraction' — skipping",
                card_id,
                status,
            )
            return {"card_id": card_id, "status": "skipped"}

        # ------------------------------------------------------------------
        # 2. Mark as extracting
        # ------------------------------------------------------------------
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE operational_cards SET status = 'extracting' WHERE id = %s",
                (card_id,),
            )
        conn.commit()

        # ------------------------------------------------------------------
        # 3. Download file bytes
        #    Prefer converted PDF key; fall back to original file_url.
        # ------------------------------------------------------------------
        storage_key = converted_key if converted_key else file_url
        file_bytes = _download_file_sync(storage_key)

        # ------------------------------------------------------------------
        # 4. Run extraction
        # ------------------------------------------------------------------
        from services.extraction.extractor import DocumentExtractor  # noqa: PLC0415

        extractor = DocumentExtractor()
        mime = (file_mime or "").lower()

        if mime in ("image/jpeg", "image/png", "image/jpg"):
            extraction_result = _run_async(
                extractor.extract_from_image_bytes(file_bytes, mime, card_id)
            )
        else:
            # Treat as PDF (default)
            extraction_result = _run_async(
                extractor.extract_from_pdf_bytes(file_bytes, card_id)
            )

        # ------------------------------------------------------------------
        # 5. Persist to card_extractions
        # ------------------------------------------------------------------
        extraction_id = str(uuid.uuid4())
        extracted_data = extraction_result.extraction.model_dump()
        # field_confidences: flatten confidence scores from FieldWithConfidence fields
        field_confidences = {
            k: v["confidence"]
            for k, v in extracted_data.items()
            if isinstance(v, dict) and "confidence" in v
        }
        cost_usd = extraction_result.cost_usd
        duration_ms = None  # not tracked at this level

        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO card_extractions
                    (id, card_id, model_version, extracted_data, field_confidences,
                     extraction_cost_usd, duration_ms)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    extraction_id,
                    card_id,
                    DocumentExtractor.MODEL,
                    json.dumps(extracted_data),
                    json.dumps(field_confidences),
                    float(cost_usd),
                    duration_ms,
                ),
            )

        # ------------------------------------------------------------------
        # 6. Update operational_cards
        # ------------------------------------------------------------------
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE operational_cards SET status = 'extracted', extraction_id = %s WHERE id = %s",
                (extraction_id, card_id),
            )
        conn.commit()

    except Exception as exc:
        # Roll back any partial updates so card stays in a consistent state.
        try:
            conn.rollback()
        except Exception:
            pass

        # Retry on Anthropic API errors with exponential back-off.
        if isinstance(exc, anthropic.APIError):
            raise self.retry(
                exc=exc,
                countdown=60 * (2 ** self.request.retries),
            )

        raise

    finally:
        conn.close()

    logger.info(
        "extract_document finished for card_id=%s, extraction_id=%s, cost_usd=%.6f — chaining analyze_vulnerabilities",
        card_id,
        extraction_id,
        cost_usd,
    )

    # Chain: kick off vulnerability analysis now that extraction is persisted.
    try:
        analyze_vulnerabilities.delay(extraction_id)
    except Exception as chain_exc:
        logger.warning("Could not enqueue analyze_vulnerabilities (broker unavailable?): %s", chain_exc)

    return {
        "card_id": card_id,
        "extraction_id": extraction_id,
        "status": "extracted",
        "cost_usd": float(cost_usd),
    }


@celery_app.task(
    bind=True,
    name="workers.documents.analyze_vulnerabilities",
    max_retries=2,
    default_retry_delay=30,
    autoretry_for=(Exception,),
)
def analyze_vulnerabilities(self, extraction_id: str) -> dict:
    """
    Run Claude Sonnet vulnerability analysis on extracted operational card data (F-7).

    Steps:
    1. Load card_extractions row by extraction_id.
    2. If not found → {"status": "not_found"}.
    3. If status != 'done' → {"status": "skipped", "reason": "extraction not done"}.
    4. Call Claude Sonnet via _analyze_with_claude to identify vulnerabilities.
    5. Persist vulnerabilities to card_extractions.vulnerabilities.
    6. Update operational_cards.status → 'review' for the associated card.
    7. Return {"extraction_id", "vulnerability_count", "status": "review"}.
    """
    logger.info("analyze_vulnerabilities started for extraction_id=%s", extraction_id)

    conn = _sync_db_conn()
    try:
        # ------------------------------------------------------------------
        # 1. Load extraction row
        # ------------------------------------------------------------------
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, card_id, status, extracted_data FROM card_extractions WHERE id = %s",
                (extraction_id,),
            )
            row = cur.fetchone()

        if row is None:
            logger.warning("analyze_vulnerabilities: extraction %s not found", extraction_id)
            return {"extraction_id": extraction_id, "status": "not_found"}

        _id, card_id, status, extracted_data = row

        # ------------------------------------------------------------------
        # 2. Guard: only analyse completed extractions
        # ------------------------------------------------------------------
        if status != "done":
            logger.info(
                "analyze_vulnerabilities: extraction %s has status '%s', expected 'done' — skipping",
                extraction_id,
                status,
            )
            return {
                "extraction_id": extraction_id,
                "status": "skipped",
                "reason": "extraction not done",
            }

        # ------------------------------------------------------------------
        # 3. Parse extracted_data (may be a dict already or a JSON string)
        # ------------------------------------------------------------------
        if isinstance(extracted_data, str):
            try:
                extracted_data = json.loads(extracted_data)
            except json.JSONDecodeError:
                extracted_data = {}

        # ------------------------------------------------------------------
        # 4. Claude vulnerability analysis
        # ------------------------------------------------------------------
        vulnerability_dicts = _analyze_with_claude(extracted_data)
        vulnerability_count = len(vulnerability_dicts)

        logger.info(
            "analyze_vulnerabilities: found %d vulnerabilities for extraction_id=%s",
            vulnerability_count,
            extraction_id,
        )

        # ------------------------------------------------------------------
        # 5. Persist vulnerabilities to card_extractions
        # ------------------------------------------------------------------
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE card_extractions SET vulnerabilities = %s WHERE id = %s",
                (json.dumps(vulnerability_dicts), extraction_id),
            )

        # ------------------------------------------------------------------
        # 6. Update operational_cards status → 'review'
        # ------------------------------------------------------------------
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE operational_cards SET status = 'review' WHERE id = %s",
                (card_id,),
            )

        conn.commit()

    finally:
        conn.close()

    logger.info(
        "analyze_vulnerabilities finished for extraction_id=%s, card_id=%s, vulnerabilities=%d",
        extraction_id,
        card_id,
        vulnerability_count,
    )
    return {
        "extraction_id": extraction_id,
        "vulnerability_count": vulnerability_count,
        "status": "review",
    }
