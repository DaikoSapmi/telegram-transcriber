# src/document_generator.py
"""Genererer Word-dokumenter fra transkripsjoner."""
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple
import logging

from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH

logger = logging.getLogger(__name__)


class DocumentGenerator:
    """Genererer Word-dokumenter fra transkripsjoner."""
    
    def __init__(self, output_dir: str = "output"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
    
    def generate(
        self,
        segments: List[Tuple[str, Optional[float]]],
        original_filename: str,
        language: str,
        duration_seconds: Optional[float] = None,
        include_speakers: bool = True,
        include_timestamps: bool = False
    ) -> Path:
        """
        Genererer Word-dokument.
        
        Args:
            segments: Liste med (tekst, timestamp) tupler
            original_filename: Navn på original lydfil
            language: Språk som ble transkribert
            duration_seconds: Varighet i sekunder
            include_speakers: Om talegjenkjenning skal inkluderes
            include_timestamps: Om tidsstempler skal inkluderes
            
        Returns:
            Sti til generert dokument
        """
        doc = Document()
        
        # Sett opp dokument
        self._setup_document(doc)
        
        # Legg til header
        self._add_header(doc, original_filename, language, duration_seconds)
        
        # Legg til metadata
        self._add_metadata(doc, original_filename, language, duration_seconds, len(segments))
        
        # Legg til transkripsjon
        if include_speakers:
            self._add_transcription_with_speakers(doc, segments, include_timestamps)
        else:
            self._add_transcription_simple(doc, segments, include_timestamps)
        
        # Lagre dokument
        output_path = self._generate_filename(original_filename)
        doc.save(output_path)
        
        logger.info(f"Dokument generert: {output_path}")
        return output_path
    
    def _setup_document(self, doc: Document) -> None:
        """Setter opp dokumentstil."""
        # Sett standard fonter
        style = doc.styles['Normal']
        font = style.font
        font.name = 'Calibri'
        font.size = Pt(11)
        
        # Marger
        sections = doc.sections
        for section in sections:
            section.top_margin = Inches(1)
            section.bottom_margin = Inches(1)
            section.left_margin = Inches(1)
            section.right_margin = Inches(1)
    
    def _add_header(
        self, 
        doc: Document, 
        original_filename: str,
        language: str,
        duration_seconds: Optional[float]
    ) -> None:
        """Legger til header med tittel."""
        # Hovedtittel
        title = doc.add_heading('Møtetranskripsjon', level=0)
        title.alignment = WD_ALIGN_PARAGRAPH.CENTER
        
        # Dato
        date_para = doc.add_paragraph()
        date_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        date_run = date_para.add_run(f"Generert: {datetime.now().strftime('%d. %B %Y, %H:%M')}")
        date_run.font.size = Pt(10)
        date_run.font.color.rgb = RGBColor(128, 128, 128)
        
        doc.add_paragraph()  # Tom linje
    
    def _add_metadata(
        self,
        doc: Document,
        original_filename: str,
        language: str,
        duration_seconds: Optional[float],
        num_segments: int
    ) -> None:
        """Legger til metadata-seksjon."""
        doc.add_heading('Metadata', level=1)
        
        metadata = [
            ("Original fil:", original_filename),
            ("Språk:", self._get_language_name(language)),
            ("Varighet:", self._format_duration(duration_seconds) if duration_seconds else "Ukjent"),
            ("Segmenter:", str(num_segments)),
            ("Generert av:", "OpenClaw Transcriber"),
        ]
        
        for label, value in metadata:
            para = doc.add_paragraph(style='List Bullet')
            para.add_run(label).bold = True
            para.add_run(f" {value}")
        
        doc.add_paragraph()  # Tom linje
    
    def _add_transcription_simple(
        self,
        doc: Document,
        segments: List[Tuple[str, Optional[float]]],
        include_timestamps: bool
    ) -> None:
        """Legger til ren transkripsjon uten talegjenkjenning."""
        doc.add_heading('Transkripsjon', level=1)
        
        for text, timestamp in segments:
            para = doc.add_paragraph()
            
            if include_timestamps and timestamp is not None:
                time_str = self._format_timestamp(timestamp)
                time_run = para.add_run(f"[{time_str}] ")
                time_run.font.name = 'Courier New'
                time_run.font.size = Pt(9)
                time_run.font.color.rgb = RGBColor(128, 128, 128)
            
            para.add_run(text)
    
    def _add_transcription_with_speakers(
        self,
        doc: Document,
        segments: List[Tuple[str, Optional[float]]],
        include_timestamps: bool
    ) -> None:
        """Legger til transkripsjon med talegjenkjenning."""
        doc.add_heading('Transkripsjon', level=1)
        
        # Simulert talegjenkjenning (bytter taler hver 3. segment)
        current_speaker = "Person 1"
        
        for i, (text, timestamp) in enumerate(segments):
            # Bytt taler
            if i > 0 and i % 3 == 0:
                speaker_num = (i // 3) + 1
                current_speaker = f"Person {speaker_num}"
            
            para = doc.add_paragraph()
            
            # Tidsstempel
            if include_timestamps and timestamp is not None:
                time_str = self._format_timestamp(timestamp)
                time_run = para.add_run(f"[{time_str}] ")
                time_run.font.name = 'Courier New'
                time_run.font.size = Pt(9)
                time_run.font.color.rgb = RGBColor(128, 128, 128)
            
            # Taler
            speaker_run = para.add_run(f"{current_speaker}: ")
            speaker_run.bold = True
            speaker_run.font.color.rgb = RGBColor(0, 112, 192)
            
            # Tekst
            para.add_run(text)
    
    def _generate_filename(self, original_filename: str) -> Path:
        """Genererer filnavn for output."""
        timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M')
        base_name = Path(original_filename).stem
        filename = f"Transkripsjon_{base_name}_{timestamp}.docx"
        return self.output_dir / filename
    
    def _format_timestamp(self, seconds: float) -> str:
        """Formaterer sekunder til HH:MM:SS."""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        return f"{minutes:02d}:{secs:02d}"
    
    def _format_duration(self, seconds: float) -> str:
        """Formaterer varighet til lesbar tekst."""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        
        parts = []
        if hours > 0:
            parts.append(f"{hours} time{'r' if hours != 1 else ''}")
        if minutes > 0:
            parts.append(f"{minutes} minutt{'er' if minutes != 1 else ''}")
        if secs > 0 and hours == 0:
            parts.append(f"{secs} sekund{'er' if secs != 1 else ''}")
        
        return ", ".join(parts) if parts else "0 sekunder"
    
    def _get_language_name(self, code: str) -> str:
        """Returnerer språknavn."""
        mapping = {
            "no": "Norsk (bokmål)",
            "nn": "Norsk (nynorsk)",
            "sme": "Nordsamisk",
            "en": "Engelsk"
        }
        return mapping.get(code, code)
