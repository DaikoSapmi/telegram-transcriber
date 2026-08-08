from pathlib import Path

from docx import Document

from src.document_generator import DocumentGenerator
from src.transcription_types import TranscriptionResult, TranscriptSegment


def test_txt_is_plain_and_docx_contains_real_metadata(tmp_path: Path):
    result = TranscriptionResult(
        segments=[
            TranscriptSegment("Bures boahtin.", 0.0, 2.5),
            TranscriptSegment("Dette er neste avsnitt.", 62.0, 66.0),
        ],
        duration_seconds=66.0,
        model_name="NbAiLab/whisper-large-sme",
        language="sme",
    )
    paths = DocumentGenerator(tmp_path).generate(result, "møte.m4a", "both")
    txt = next(path for path in paths if path.suffix == ".txt")
    docx = next(path for path in paths if path.suffix == ".docx")

    assert (
        txt.read_text(encoding="utf-8") == "Bures boahtin.\n\nDette er neste avsnitt.\n"
    )
    document_text = "\n".join(paragraph.text for paragraph in Document(docx).paragraphs)
    assert "NbAiLab/whisper-large-sme" in document_text
    assert "Nordsamisk" in document_text
    assert "[00:01:02]" in document_text
    assert "Ren transkripsjon" in document_text
    assert "Ailo-versjon: pure-transcription-2026.08.08-segmented" in document_text
    assert "uten oversettelse, språkvask eller sammendrag" in document_text
    assert "Gemini (Google AI)" not in document_text
    assert "Ailo 2.0" not in document_text
    assert "Person 1" not in document_text


def test_txt_preserves_every_raw_segment_without_shortening(tmp_path: Path):
    segments = [
        TranscriptSegment(f"sámegiellasátni{i}", float(i), float(i + 1))
        for i in range(800)
    ]
    result = TranscriptionResult(
        segments=segments,
        duration_seconds=800.0,
        model_name="NbAiLab/whisper-large-sme",
        language="sme",
    )

    path = DocumentGenerator(tmp_path).generate(result, "gulahallan.m4a", "txt")[0]
    delivered = path.read_text(encoding="utf-8")

    assert len(delivered.split()) == 800
    assert "sámegiellasátni0" in delivered
    assert "sámegiellasátni799" in delivered
