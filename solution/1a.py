import fitz  # PyMuPDF
import json
import re
from collections import defaultdict

def extract_headings_filtered(pdf_path):
    doc = fitz.open(pdf_path)
    all_spans = []

    # Step 1: Extract all spans and collect font size frequencies
    size_freq = defaultdict(int)
    for page_num, page in enumerate(doc, start=1):
        blocks = page.get_text("dict")["blocks"]
        for block in blocks:
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    text = span["text"].strip()
                    size = round(span["size"], 2)
                    if not text:
                        continue
                    size_freq[size] += 1
                    all_spans.append({
                        "text": text,
                        "size": size,
                        "flags": span["flags"],
                        "font": span["font"],
                        "bbox": span["bbox"],
                        "page": page_num
                    })

    if not size_freq:
        return {"title": "Untitled Document", "outline": []}

    # Step 2: Identify most common (body) font size
    body_size = max(size_freq.items(), key=lambda x: x[1])[0]

    # Step 3: Sort sizes to assign heading levels
    distinct_sizes = sorted([s for s in size_freq if s > body_size], reverse=True)
    size_to_level = {size: f"H{i+1}" for i, size in enumerate(distinct_sizes)}

    # Step 4: Get title (first non-empty text with largest font)
    sorted_spans = sorted(all_spans, key=lambda x: (-x["size"], x["page"]))
    title = next((s["text"] for s in sorted_spans if s["text"]), "Untitled Document")

    # Step 5: Filter and extract headings, excluding the title
    headings = []
    for span in all_spans:
        text = span["text"]
        size = span["size"]
        flags = span["flags"]
        page = span["page"]
        is_bold = flags & 2 != 0

        # Heuristic heading checks
        is_numbered = re.match(r"^\d+(\.\d+)*\s+", text)
        starts_cap = re.match(r"^[A-Z]", text)
        ends_colon = text.endswith(":")
        is_likely_heading = (
            size > body_size and
            (is_bold or is_numbered or starts_cap or ends_colon)
        )

        if is_likely_heading and text != title:
            level = size_to_level.get(size, "H3")
            headings.append({
                "level": level,
                "text": text,
                "page": page
            })

    def heading_sort_key(h):
        level_number = int(h["level"][1:]) if h["level"].startswith("H") else 99
        return (h["page"], level_number)

    headings.sort(key=heading_sort_key)

    return {
        "title": title,
        "outline": headings
    }

# === USAGE ===
pdf_path = "E0H1CM114.pdf"  
result = extract_headings_filtered(pdf_path)

# Print the structured JSON
print(json.dumps(result, indent=2, ensure_ascii=False))
