import io
import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)

def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Extract readable text from a PDF file using pypdf."""
    from pypdf import PdfReader
    stream = io.BytesIO(file_bytes)
    reader = PdfReader(stream)
    pages_text = []
    for idx, page in enumerate(reader.pages):
        try:
            pt = page.extract_text()
            if pt and pt.strip():
                pages_text.append(pt.strip())
        except Exception as e:
            logger.warning("Failed to extract page %d from PDF: %s", idx, e)
    return "\n\n".join(pages_text)

def extract_text_from_docx(file_bytes: bytes) -> str:
    """Extract readable text from Word .docx file including paragraphs and tables."""
    from docx import Document
    stream = io.BytesIO(file_bytes)
    doc = Document(stream)
    lines = []
    
    # Paragraphs
    for p in doc.paragraphs:
        txt = p.text.strip()
        if txt:
            lines.append(txt)
            
    # Tables (resumes often use tables for skills/experience columns)
    for table in doc.tables:
        for row in table.rows:
            row_cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
            if row_cells:
                # remove duplicates if merged cells
                unique_cells = []
                for c in row_cells:
                    if not unique_cells or c != unique_cells[-1]:
                        unique_cells.append(c)
                lines.append(" | ".join(unique_cells))
                
    return "\n\n".join(lines)

def extract_text_from_doc_fallback(file_bytes: bytes) -> str:
    """Fallback text extractor for legacy .doc binary files."""
    # First try docx parser in case it's a docx with .doc extension
    try:
        res = extract_text_from_docx(file_bytes)
        if res and len(res) > 50:
            return res
    except Exception:
        pass

    # Extract ASCII and UTF-16 printable strings
    try:
        ascii_matches = re.findall(rb'[\x20-\x7E\r\n\t]{4,}', file_bytes)
        text = "\n".join([m.decode('ascii', errors='ignore').strip() for m in ascii_matches if m.strip()])
        if len(text) > 100:
            return text
    except Exception:
        pass

    try:
        return file_bytes.decode('utf-8', errors='ignore')
    except Exception:
        return ""

def extract_document_text(file_bytes: bytes, filename: str) -> str:
    """
    Main entrypoint: extracts clean structured text from PDF, DOCX, DOC, TXT, MD.
    """
    fn = (filename or "").lower().strip()
    extracted = ""
    
    if fn.endswith(".pdf"):
        try:
            extracted = extract_text_from_pdf(file_bytes)
        except Exception as e:
            logger.error("PDF extraction error for %s: %s", filename, e)
            raise ValueError(f"Failed to read PDF file: {str(e)}")
            
    elif fn.endswith(".docx"):
        try:
            extracted = extract_text_from_docx(file_bytes)
        except Exception as e:
            logger.error("DOCX extraction error for %s: %s", filename, e)
            raise ValueError(f"Failed to read Word (.docx) file: {str(e)}")
            
    elif fn.endswith(".doc"):
        try:
            extracted = extract_text_from_doc_fallback(file_bytes)
        except Exception as e:
            logger.error("Legacy DOC extraction error for %s: %s", filename, e)
            raise ValueError(f"Failed to read Word (.doc) file: {str(e)}")
            
    else:
        # Plain text / Markdown / other text formats
        for enc in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
            try:
                extracted = file_bytes.decode(enc)
                break
            except Exception:
                continue
        if not extracted:
            extracted = file_bytes.decode("utf-8", errors="replace")

    # Clean up whitespace and excessive blank lines
    cleaned = re.sub(r'[ \t]+', ' ', extracted)
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned).strip()
    return cleaned
