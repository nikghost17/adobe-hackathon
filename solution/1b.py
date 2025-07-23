import os
import fitz  # PyMuPDF
import json
import re
from datetime import datetime

# === CONFIG ===
PDF_FOLDER = "C:/Users/varni/OneDrive/Desktop/Adobe/adobe-hackathon/Resources/Challenge_1b/Collection 1/PDFs"
OUTPUT_PATH = "./output/result.json"

# === Define Persona & Task (Dynamic Inputs) ===
PERSONA = "Travel Planner"
JOB_TO_BE_DONE = "Plan a trip of 4 days for a group of 10 college friends."

# === Load stopwords ===
def load_stopwords():
    # Lightweight internal list to avoid nltk/downloads
    return set([
        "this", "that", "with", "have", "from", "they", "would", "there", "their",
        "about", "could", "should", "where", "which", "those", "after", "again",
        "above", "because", "below", "very", "while", "being", "into", "some",
        "other", "more", "what", "when", "your", "you", "for", "and", "the", "are"
    ])

# === Extract relevant keywords ===
def extract_keywords(text, stopwords):
    words = re.findall(r'\b\w{4,}\b', text.lower())
    return list(set(w for w in words if w not in stopwords))

# === Score content relevance ===
def score_text_relevance(text, keywords):
    score = 0
    text_lower = text.lower()
    for keyword in keywords:
        score += text_lower.count(keyword)
    return score

# === Summarize text ===
def summarize(text):
    lines = [l.strip() for l in text.split("\n") if len(l.strip()) > 40]
    return " ".join(lines[:5])[:1000]

# === Main extraction function ===
def extract_from_pdfs():
    stopwords = load_stopwords()
    keywords = extract_keywords(PERSONA + " " + JOB_TO_BE_DONE, stopwords)

    metadata = {
        "input_documents": [],
        "persona": PERSONA,
        "job_to_be_done": JOB_TO_BE_DONE,
        "processing_timestamp": datetime.now().isoformat()
    }

    raw_sections = []
    raw_subsections = []

    for filename in sorted(os.listdir(PDF_FOLDER)):
        if not filename.lower().endswith(".pdf"):
            continue

        filepath = os.path.join(PDF_FOLDER, filename)
        metadata["input_documents"].append(filename)

        doc = fitz.open(filepath)

        for page_number in range(len(doc)):
            page = doc[page_number]
            text = page.get_text()
            if not text.strip():
                continue

            relevance_score = score_text_relevance(text, keywords)

            section_title = text.strip().split("\n")[0][:100]

            raw_sections.append({
                "document": filename,
                "page_number": page_number + 1,
                "section_title": section_title,
                "importance_score": relevance_score,
            })

            raw_subsections.append({
                "document": filename,
                "page_number": page_number + 1,
                "refined_text": summarize(text),
                "importance_score": relevance_score
            })

    # Sort and assign importance rank
    sorted_sections = sorted(raw_sections, key=lambda x: -x["importance_score"])
    top_sections = []
    used_docs = set()

    for entry in sorted_sections:
        if entry["document"] not in used_docs:
            used_docs.add(entry["document"])
            top_sections.append(entry)
        if len(top_sections) == 5:
            break

    for i, section in enumerate(top_sections):
        section["importance_rank"] = i + 1
        del section["importance_score"]

    # Match top subsections from the same documents and relevance
    sorted_subs = sorted(raw_subsections, key=lambda x: -x["importance_score"])
    top_subsections = []
    seen = set()
    for sub in sorted_subs:
        key = (sub["document"], sub["page_number"])
        if key not in seen:
            seen.add(key)
            del sub["importance_score"]
            top_subsections.append(sub)
        if len(top_subsections) == 5:
            break

    # Final output
    output = {
        "metadata": metadata,
        "extracted_sections": top_sections,
        "subsection_analysis": top_subsections
    }

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print("✅ Output saved at:", OUTPUT_PATH)

if __name__ == "__main__":
    extract_from_pdfs()
