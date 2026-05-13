import logging
from celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    name="workers.documents.normalize_document",
    max_retries=3,
    default_retry_delay=30,
    autoretry_for=(Exception,),
)
def normalize_document(self, card_id: str) -> dict:
    """
    Convert uploaded document to PDF (if needed) and generate thumbnail.
    Triggered after upload. Updates operational_cards.status.

    Steps:
    1. Fetch card record from DB (status = 'uploaded')
    2. Download file from R2/local storage
    3. Convert to PDF if needed (LibreOffice headless for DOCX/VSD)
    4. Generate thumbnail (first page -> JPG 400px wide)
    5. Upload converted PDF + thumbnail to storage
    6. Update card status -> 'ready_for_extraction'
    7. Chain: trigger extract_document task
    """
    logger.info(f"normalize_document called for card_id={card_id}")
    # Placeholder -- real implementation in F-3
    return {"card_id": card_id, "status": "normalize_placeholder"}


@celery_app.task(
    bind=True,
    name="workers.documents.extract_document",
    max_retries=3,
    default_retry_delay=60,
    autoretry_for=(Exception,),
)
def extract_document(self, card_id: str) -> dict:
    """
    Run Claude Sonnet 4 extraction on normalized PDF.
    Updates operational_cards.status -> 'extracted'.
    Real implementation in F-6.
    """
    logger.info(f"extract_document called for card_id={card_id}")
    return {"card_id": card_id, "status": "extract_placeholder"}


@celery_app.task(
    bind=True,
    name="workers.documents.analyze_vulnerabilities",
    max_retries=2,
    default_retry_delay=30,
    autoretry_for=(Exception,),
)
def analyze_vulnerabilities(self, extraction_id: str) -> dict:
    """
    Run Claude vulnerability analysis on extracted data.
    Updates card_extractions.vulnerabilities + card status -> 'review'.
    Real implementation in F-7.
    """
    logger.info(f"analyze_vulnerabilities called for extraction_id={extraction_id}")
    return {"extraction_id": extraction_id, "status": "vulnerability_placeholder"}
