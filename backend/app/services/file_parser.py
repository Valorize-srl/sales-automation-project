"""File parser service - extracts text from PDF, DOCX, and TXT files."""
import io

from fastapi import UploadFile


async def extract_text_from_file(file: UploadFile) -> str:
    """Extract text content from an uploaded file."""
    content = await file.read()
    filename = file.filename or ""

    if filename.lower().endswith(".txt"):
        return content.decode("utf-8", errors="replace")

    elif filename.lower().endswith(".pdf"):
        import PyPDF2

        reader = PyPDF2.PdfReader(io.BytesIO(content))
        parts = [page.extract_text() or "" for page in reader.pages]
        return "\n".join(parts)

    elif filename.lower().endswith(".docx"):
        import docx

        doc = docx.Document(io.BytesIO(content))
        return "\n".join(p.text for p in doc.paragraphs)

    else:
        raise ValueError(f"Unsupported file type: {filename}")
