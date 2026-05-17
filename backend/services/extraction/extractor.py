from __future__ import annotations

import asyncio
import base64
import io
from functools import partial
from typing import List

from .schema import ExtractionResult, OperationalCardExtraction

SYSTEM_PROMPT = (
    "Ты — специализированная система извлечения данных из оперативных карточек МЧС Республики Казахстан.\n"
    "\n"
    "Твоя задача: точно извлечь структурированные данные о пожарной безопасности объекта.\n"
    "\n"
    "Правила:\n"
    "1. Для каждого поля укажи confidence от 0 до 1 (1 = данные явно указаны, 0.5 = логически выведено, 0 = не найдено/не применимо)\n"
    "2. Если поле не найдено — value=null, confidence=0\n"
    "3. Адреса нормализуй: улица, номер дома, город\n"
    "4. Даты — ISO формат YYYY-MM-DD\n"
    "5. Площади — числа в кв.м.\n"
    "6. Если документ нечитаемый/нерелевантный — overall_confidence < 0.3\n"
    "7. В missing_fields перечисли имена полей OperationalCardExtraction которые не удалось найти"
)

_EXTRACTION_TOOL = {
    "name": "extract_operational_card",
    "description": "Extract structured fire safety data from an МЧС РК operational card",
    "input_schema": OperationalCardExtraction.model_json_schema(),
}


def _pdf_to_images(pdf_bytes: bytes, max_pages: int = 20) -> List[bytes]:
    """Convert PDF to list of JPEG image bytes (one per page, up to max_pages)."""
    try:
        from pdf2image import convert_from_bytes

        images = convert_from_bytes(
            pdf_bytes,
            dpi=150,
            fmt="jpeg",
            first_page=1,
            last_page=max_pages,
        )
        result: List[bytes] = []
        for img in images:
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=85)
            result.append(buf.getvalue())
        return result
    except ImportError:
        # pdf2image not available — return empty (caller handles gracefully)
        return []


class DocumentExtractor:
    """
    Extracts structured data from МЧС РК operational card PDFs using Claude Sonnet
    with tool use (structured output).
    """

    MODEL = "claude-sonnet-4-6"
    MAX_PAGES = 20
    COST_PER_INPUT_TOKEN = 3e-6   # $3/MTok for Sonnet
    COST_PER_OUTPUT_TOKEN = 15e-6  # $15/MTok for Sonnet

    def __init__(self) -> None:
        import anthropic  # noqa: PLC0415 — intentional lazy import

        self.client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env

    # ------------------------------------------------------------------
    # Public async API
    # ------------------------------------------------------------------

    async def extract_from_pdf_bytes(
        self,
        pdf_bytes: bytes,
        card_id: str,
    ) -> ExtractionResult:
        """
        Convert PDF pages to images and send to Claude for extraction.
        Returns ExtractionResult with the structured data + cost.
        """
        page_images = await asyncio.to_thread(_pdf_to_images, pdf_bytes, self.MAX_PAGES)

        if not page_images:
            # pdf2image unavailable or empty PDF — return a minimal failed result
            return self._empty_result(pages_processed=0)

        return await self._call_claude(page_images, card_id)

    async def extract_from_image_bytes(
        self,
        image_bytes: bytes,
        mime_type: str,  # image/jpeg or image/png
        card_id: str,
    ) -> ExtractionResult:
        """Send a single image to Claude for extraction."""
        content = self._build_content([(image_bytes, mime_type)])
        return await self._invoke(content, pages_processed=1)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _call_claude(
        self,
        page_images: List[bytes],
        card_id: str,
    ) -> ExtractionResult:
        """Build multi-image content block and call Claude."""
        image_payloads = [(img, "image/jpeg") for img in page_images]
        content = self._build_content(image_payloads)
        return await self._invoke(content, pages_processed=len(page_images))

    def _build_content(self, image_payloads: List[tuple]) -> list:
        """Build content list: image blocks + instruction text block."""
        content: list = []
        for img_bytes, mime_type in image_payloads:
            content.append(
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": mime_type,
                        "data": base64.b64encode(img_bytes).decode(),
                    },
                }
            )
        content.append(
            {
                "type": "text",
                "text": (
                    "Extract all fire safety data from this operational card "
                    "(оперативная карточка МЧС РК). Use the extract_operational_card tool."
                ),
            }
        )
        return content

    async def _invoke(self, content: list, pages_processed: int) -> ExtractionResult:
        """Run the sync Anthropic SDK call in a thread and parse the result."""
        create_fn = partial(
            self.client.messages.create,
            model=self.MODEL,
            max_tokens=4096,
            tools=[_EXTRACTION_TOOL],
            messages=[{"role": "user", "content": content}],
            system=SYSTEM_PROMPT,
        )
        response = await asyncio.to_thread(create_fn)

        # Parse tool use block
        tool_use_block = next(
            (b for b in response.content if b.type == "tool_use"),
            None,
        )
        if tool_use_block is None:
            return self._empty_result(pages_processed=pages_processed)

        extraction = OperationalCardExtraction(**tool_use_block.input)

        input_tokens: int = response.usage.input_tokens
        output_tokens: int = response.usage.output_tokens
        cost_usd = (
            input_tokens * self.COST_PER_INPUT_TOKEN
            + output_tokens * self.COST_PER_OUTPUT_TOKEN
        )

        return ExtractionResult(
            extraction=extraction,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost_usd,
            pages_processed=pages_processed,
        )

    def _empty_result(self, pages_processed: int) -> ExtractionResult:
        """Return a zero-confidence result when extraction cannot proceed."""
        null_field = {"value": None, "confidence": 0.0}
        extraction = OperationalCardExtraction(
            card_number=null_field,
            approved_date=null_field,
            revision_date=null_field,
            building_name=null_field,
            address=null_field,
            city=null_field,
            hazard_class=null_field,
            floors_above=null_field,
            floors_below=null_field,
            total_area_sqm=null_field,
            height_m=null_field,
            year_built=null_field,
            wall_material=null_field,
            fire_resistance_degree=null_field,
            fire_safety={},
            fire_safety_confidence=0.0,
            hydrants=[],
            max_occupancy=null_field,
            has_gas_systems=null_field,
            has_hazardous_materials=null_field,
            hazardous_materials_description=null_field,
            overall_confidence=0.0,
            missing_fields=list(OperationalCardExtraction.model_fields.keys()),
            extraction_notes="Extraction could not proceed (no pages or pdf2image unavailable).",
        )
        return ExtractionResult(
            extraction=extraction,
            input_tokens=0,
            output_tokens=0,
            cost_usd=0.0,
            pages_processed=pages_processed,
        )
