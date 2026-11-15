import os
from typing import Dict, List, Optional
import pypdf

def extract_text_from_slides(pdf_path: str, max_pages: int = 150) -> Dict:
    """
    Extracts text, slide titles, and outline from a professor's presentation slides PDF.
    Returns structured data for multi-source fusion with lecture audio.
    """
    if not pdf_path or not os.path.exists(pdf_path):
        return {"total_slides": 0, "text": "", "summary": "", "slides": []}

    try:
        reader = pypdf.PdfReader(pdf_path)
        total_pages = len(reader.pages)
        slides = []
        combined_text_parts = []

        pages_to_read = min(total_pages, max_pages)

        for idx in range(pages_to_read):
            page = reader.pages[idx]
            page_text = page.extract_text() or ""
            clean_text = page_text.strip()
            
            # Extract first line as tentative slide title
            lines = [l.strip() for l in clean_text.splitlines() if l.strip()]
            slide_title = lines[0] if lines else f"Slide {idx + 1}"
            if len(slide_title) > 60:
                slide_title = slide_title[:57] + "..."

            slides.append({
                "page": idx + 1,
                "title": slide_title,
                "content": clean_text
            })

            combined_text_parts.append(f"[Diapositive / Slide {idx + 1} : {slide_title}]\n{clean_text}\n")

        full_text = "\n".join(combined_text_parts)
        
        # Build brief overview
        titles_sample = [s["title"] for s in slides[:8]]
        summary = f"Support de {total_pages} diapositives. Thèmes abordés : {', '.join(titles_sample)}"

        return {
            "total_slides": total_pages,
            "text": full_text,
            "summary": summary,
            "slides": slides,
            "filename": os.path.basename(pdf_path)
        }

    except Exception as e:
        print(f"Error parsing slides PDF: {e}")
        return {"total_slides": 0, "text": "", "summary": f"Erreur de lecture: {e}", "slides": []}
