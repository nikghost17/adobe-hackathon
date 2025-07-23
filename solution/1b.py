import os
import json
import fitz  # PyMuPDF
from datetime import datetime
from collections import Counter


def extract_text_by_page(file_path):
    doc = fitz.open(file_path)
    return [(i + 1, page.get_text()) for i, page in enumerate(doc)]


def is_likely_heading(line):
    line = line.strip()
    if len(line) > 100 or len(line) < 10:
        return False
    if line.endswith("."):
        return False
    # Heuristic: Title case OR high capital ratio
    words = line.split()
    title_case_count = sum(w[0].isupper() for w in words)
    capital_ratio = sum(c.isupper() for c in line) / (len(line) + 1e-5)
    return title_case_count / len(words) > 0.6 or capital_ratio > 0.4


SKIP_TITLES = {"introduction", "conclusion", "table of contents", "about", "references"}

def detect_sections(pages, filename):
    sections = []
    for page_number, text in pages:
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        for i, line in enumerate(lines):
            if is_likely_heading(line):
                if line.lower().strip() in SKIP_TITLES:
                    continue  # skip generic sections
                section = {
                    "document": filename,
                    "section_title": line,
                    "page_number": page_number,
                    "raw_text": "\n".join(lines[i: i + 20])
                }
                sections.append(section)
    return sections


from fuzzywuzzy import fuzz

def rank_sections(sections, job_description):
    for sec in sections:
        preview = sec["raw_text"][:500]
        combined = sec["section_title"] + " " + preview
        sec["importance_rank"] = fuzz.token_set_ratio(combined.lower(), job_description.lower())
    return sorted(sections, key=lambda s: s["importance_rank"], reverse=True)




def refine_text(raw_text, max_chars=3000):
    lines = [line.strip() for line in raw_text.splitlines() if len(line.strip()) > 30]
    return " ".join(lines)[:max_chars]


def process_pdfs(pdf_folder, persona, job_to_be_done):
    input_docs = [f for f in os.listdir(pdf_folder) if f.lower().endswith(".pdf")]
    all_sections = []

    for doc in input_docs:
        path = os.path.join(pdf_folder, doc)
        pages = extract_text_by_page(path)
        sections = detect_sections(pages, doc)
        all_sections.extend(sections)

    ranked_sections = rank_sections(all_sections, job_to_be_done)

    metadata = {
        "input_documents": input_docs,
        "persona": persona,
        "job_to_be_done": job_to_be_done,
        "processing_timestamp": datetime.utcnow().isoformat()
    }

    extracted_sections = [
        {
            "document": s["document"],
            "section_title": s["section_title"],
            "importance_rank": i + 1,
            "page_number": s["page_number"]
        }
        for i, s in enumerate(ranked_sections[:5])
    ]

    subsection_analysis = [
        {
            "document": s["document"],
            "refined_text": refine_text(s["raw_text"]),
            "page_number": s["page_number"]
        }
        for s in ranked_sections[:5]
    ]

    return {
        "metadata": metadata,
        "extracted_sections": extracted_sections,
        "subsection_analysis": subsection_analysis
    }


def save_output(data, output_path):
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


if __name__ == "__main__":
    # 💡 Hardcoded inputs
    pdf_folder = "C:/Users/varni/OneDrive/Desktop/Adobe/adobe-hackathon/solution/pdfs"
    persona = "Travel Planner"
    job_description = "Plan a trip of 4 days for a group of 10 college friends."
    output_file = "output.json"

    result = process_pdfs(pdf_folder, persona, job_description)
    save_output(result, output_file)
    print(f"✅ Extraction complete. Data saved to {output_file}")

