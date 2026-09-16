import base64
import io
from dataclasses import dataclass
from unittest.mock import patch

import anthropic
import httpx
import pytest
from PIL import Image
from reportlab.pdfgen import canvas

from app.providers.base import DocumentInput
from app.providers.ocr.llm_vision_provider import LlmVisionOcrProvider, VisionOcrError


def _make_pdf_bytes(page_count: int = 1) -> bytes:
    buffer = io.BytesIO()
    pdf_canvas = canvas.Canvas(buffer)
    for i in range(page_count):
        pdf_canvas.drawString(100, 700, f"Testseite {i + 1}")
        pdf_canvas.showPage()
    pdf_canvas.save()
    return buffer.getvalue()


def _make_tiff_bytes(frame_count: int = 1) -> bytes:
    buffer = io.BytesIO()
    frames = [Image.new("RGB", (40, 20), color=(i * 10, 0, 0)) for i in range(frame_count)]
    frames[0].save(buffer, format="TIFF", save_all=frame_count > 1, append_images=frames[1:])
    return buffer.getvalue()


@dataclass
class _FakeToolUseBlock:
    input: dict
    type: str = "tool_use"


@dataclass
class _FakeMessage:
    content: list


def _provider(max_pages: int = 5) -> LlmVisionOcrProvider:
    return LlmVisionOcrProvider(api_key="fake-key", model="claude-sonnet-5", max_pages=max_pages)


# --- Bild-/PDF-Rendering (echte pdfplumber-/Pillow-Aufrufe, nicht gemockt) ---


def test_render_pdf_pages_produces_one_png_per_page() -> None:
    provider = _provider()
    pages = provider._render_pdf_pages(_make_pdf_bytes(page_count=2))

    assert len(pages) == 2
    for page in pages:
        assert page.media_type == "image/png"
        decoded = base64.b64decode(page.base64_data)
        assert decoded[:8] == b"\x89PNG\r\n\x1a\n"  # PNG-Signatur


def test_render_pdf_pages_respects_max_pages() -> None:
    provider = _provider(max_pages=2)
    pages = provider._render_pdf_pages(_make_pdf_bytes(page_count=3))
    assert len(pages) == 2


def test_render_image_pages_passes_through_native_png() -> None:
    provider = _provider()
    original = io.BytesIO()
    Image.new("RGB", (10, 10)).save(original, format="PNG")
    original_bytes = original.getvalue()

    pages = provider._render_image_pages(original_bytes, "image/png")

    assert len(pages) == 1
    assert pages[0].media_type == "image/png"
    assert base64.b64decode(pages[0].base64_data) == original_bytes


def test_render_image_pages_converts_single_frame_tiff() -> None:
    provider = _provider()
    pages = provider._render_image_pages(_make_tiff_bytes(frame_count=1), "image/tiff")
    assert len(pages) == 1
    assert pages[0].media_type == "image/png"


def test_render_image_pages_converts_multi_frame_tiff_to_multiple_pages() -> None:
    provider = _provider()
    pages = provider._render_image_pages(_make_tiff_bytes(frame_count=3), "image/tiff")
    assert len(pages) == 3
    assert all(page.media_type == "image/png" for page in pages)


# --- Mapping der (gemockten) Modellantwort auf ExtractedFieldResult ---


def _tool_response(**overrides) -> _FakeMessage:
    payload = {
        "full_text": "Frachtrechnung 4711",
        "signature_present": False,
        "fields": [
            {
                "field_name": "invoice_amount",
                "original_value": "1.234,56 EUR",
                "data_type": "decimal",
                "confidence": "high",
                "reasoning": "Steht unten rechts unter 'Gesamtbetrag'.",
            }
        ],
    }
    payload.update(overrides)
    return _FakeMessage(content=[_FakeToolUseBlock(input=payload)])


def test_analyze_maps_tool_response_and_normalizes_decimal() -> None:
    provider = _provider()
    document = DocumentInput(file_bytes=_make_pdf_bytes(1), mime_type="application/pdf", filename="rechnung.pdf")

    with patch.object(provider._client.messages, "create", return_value=_tool_response()) as mock_create:
        result = provider.analyze(document)

    assert mock_create.call_count == 1
    assert len(result.pages) == 1
    assert result.pages[0].extracted_text == "Frachtrechnung 4711"

    amount_field = next(f for f in result.fields if f.field_name == "invoice_amount")
    assert amount_field.original_value == "1.234,56 EUR"
    assert amount_field.normalized_value == "1234.56"
    assert amount_field.confidence == pytest.approx(0.97)
    assert amount_field.extraction_method == "claude_vision"
    assert amount_field.source_text == "Steht unten rechts unter 'Gesamtbetrag'."

    signature_field = next(f for f in result.fields if f.field_name == "signature_present")
    assert signature_field.original_value == "False"


def test_analyze_downgrades_confidence_when_decimal_unparsable() -> None:
    provider = _provider()
    document = DocumentInput(file_bytes=_make_pdf_bytes(1), mime_type="application/pdf", filename="rechnung.pdf")
    response = _tool_response(
        fields=[
            {
                "field_name": "invoice_amount",
                "original_value": "unleserlich",
                "data_type": "decimal",
                "confidence": "high",
                "reasoning": "Zahl ist verschmiert.",
            }
        ]
    )

    with patch.object(provider._client.messages, "create", return_value=response):
        result = provider.analyze(document)

    amount_field = next(f for f in result.fields if f.field_name == "invoice_amount")
    assert amount_field.normalized_value is None
    assert amount_field.confidence == pytest.approx(0.60)


def test_analyze_detects_signature_present() -> None:
    provider = _provider()
    document = DocumentInput(file_bytes=_make_pdf_bytes(1), mime_type="application/pdf", filename="beleg.pdf")
    response = _tool_response(signature_present=True, fields=[])

    with patch.object(provider._client.messages, "create", return_value=response):
        result = provider.analyze(document)

    signature_field = next(f for f in result.fields if f.field_name == "signature_present")
    assert signature_field.original_value == "True"
    assert signature_field.confidence == pytest.approx(0.97)


def test_analyze_calls_api_once_per_page() -> None:
    provider = _provider()
    document = DocumentInput(file_bytes=_make_pdf_bytes(2), mime_type="application/pdf", filename="mehrseitig.pdf")

    with patch.object(provider._client.messages, "create", return_value=_tool_response()) as mock_create:
        result = provider.analyze(document)

    assert mock_create.call_count == 2
    assert len(result.pages) == 2
    assert [p.page_number for p in result.pages] == [1, 2]


def test_extract_page_raises_when_no_tool_use_block_returned() -> None:
    provider = _provider()
    document = DocumentInput(file_bytes=_make_pdf_bytes(1), mime_type="application/pdf", filename="x.pdf")

    with patch.object(provider._client.messages, "create", return_value=_FakeMessage(content=[])):
        with pytest.raises(VisionOcrError):
            provider.analyze(document)


def test_extract_page_wraps_anthropic_api_errors() -> None:
    provider = _provider()
    document = DocumentInput(file_bytes=_make_pdf_bytes(1), mime_type="application/pdf", filename="x.pdf")
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")

    with patch.object(provider._client.messages, "create", side_effect=anthropic.APIConnectionError(request=request)):
        with pytest.raises(VisionOcrError):
            provider.analyze(document)
