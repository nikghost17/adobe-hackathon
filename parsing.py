import fitz
import os
import json
import re
from collections import Counter

class PDFOutlineExtractorV8_Final:
    """
    Robust universal PDF outline extractor using font/format heuristics.
    No document- or field-specific hardcoding.
    """

    def __init__(self, pdf_path):
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"The file {pdf_path} was not found.")
        self.doc = fitz.open(pdf_path)
        self.all_lines = []
        self.body_style = {'size': 12, 'font': 'default'}
        self.title = "Untitled Document"
        self.outline = []
        self.toc_pages = set()
        # --- NEW: Initialize a set to store text found inside tables ---
        self.table_texts = set()

    def _is_bold(self, font_name):
        return any(x in font_name.lower() for x in ['bold', 'black', 'heavy', 'cbi'])

    def _extract_all_lines(self):
        page_width = self.doc[0].rect.width if len(self.doc) > 0 else 612
        for page_num, page in enumerate(self.doc):
            page_dict = page.get_text("dict", sort=True)
            for block in page_dict.get("blocks", []):
                for line in block.get("lines", []):
                    if not line.get("spans"):
                        continue
                    line_text = "".join([s["text"] for s in line["spans"]]).strip()
                    if not line_text:
                        continue
                    span = line["spans"][0]
                    x0, _, x1, _ = line["bbox"]
                    center = (x0 + x1) / 2
                    alignment = "center" if abs(center - page_width / 2) < 20 else "left" if x0 < 100 else "other"
                    self.all_lines.append({
                        "text": line_text,
                        "font_size": round(span["size"]),
                        "font_name": span["font"],
                        "is_bold": self._is_bold(span["font"]),
                        "page_num": page_num,
                        "bbox": line["bbox"],
                        "alignment": alignment
                    })

    # --- NEW: Method to detect and extract text from tables ---
    def _extract_table_content(self):
        """
        Uses PyMuPDF's table detection to find all tables and extracts their content.
        Stores all unique cell text in self.table_texts for later filtering.
        """
        for page in self.doc:
            # find_tables() is a powerful feature to automatically detect tabular data
            tables = page.find_tables()
            for table in tables:
                # The extract() method returns a list of lists, representing the table rows
                content = table.extract()
                for row in content:
                    for cell in row:
                        if cell and isinstance(cell, str):
                            # Add cleaned cell text to our set for quick lookups later
                            self.table_texts.add(cell.strip().lower())

    # --- NEW: Helper method to identify lines that are likely just dates ---
    def _is_likely_date(self, text):
        """
        Checks if a string is likely a standalone date.
        Returns True if it matches common date patterns, False otherwise.
        """
        # A regex to find common date patterns (e.g., "20 April 2025", "April 20, 2025")
        # This looks for month names surrounded by numbers.
        date_pattern = re.compile(
            r'\b(?:january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\b',
            re.IGNORECASE
        )
        if date_pattern.search(text):
            # If a month is found, check if the line contains much else besides numbers and date-related words.
            # We strip date-related words and see what's left.
            non_date_text = re.sub(r'[\d\s,.-]+', '', text.lower())
            non_date_text = date_pattern.sub('', non_date_text)
            # If very little non-date text remains, it's likely just a date.
            if len(non_date_text) < 5:
                return True
        return False

    def _determine_body_style(self):
        styles = [
            (l["font_size"], l["font_name"])
            for l in self.all_lines
            if not l["is_bold"] and len(l["text"]) > 80 and l["alignment"] == 'left'
        ]
        if styles:
            common_style = Counter(styles).most_common(1)[0][0]
            self.body_style['size'], self.body_style['font'] = common_style

    def _detect_toc_pages(self):
        toc_keywords = re.compile(r'^(table\s+of\s+)?contents?|index', re.IGNORECASE)
        for page_num, page in enumerate(self.doc):
            lines_on_page = [l for l in self.all_lines if l['page_num'] == page_num]
            if not lines_on_page:
                continue
            has_keyword = any(toc_keywords.search(l['text']) for l in lines_on_page)
            dot_lines = sum(1 for l in lines_on_page if re.search(r'\.{5,}', l['text']))
            if has_keyword or (dot_lines / len(lines_on_page) > 0.3 and len(lines_on_page) > 5):
                self.toc_pages.add(page_num)

    def _is_in_filtered_zone(self, line):
        if line['page_num'] in self.toc_pages:
            return not re.match(r'^(table\s+of\s+)?contents?|index', line['text'], re.IGNORECASE)
        return False

    def _extract_title(self):
        first_page_lines = sorted(
            [l for l in self.all_lines if l["page_num"] == 0 and l["bbox"][1] < 400],
            key=lambda x: x["bbox"][1]
        )
        if not first_page_lines:
            return
        try:
            max_size = max(l["font_size"] for l in first_page_lines)
        except ValueError:
            return
        title_parts, last_y, title_font = [], None, None
        for line in first_page_lines:
            if line["font_size"] == max_size:
                if last_y and line["bbox"][1] > last_y + (line["bbox"][3] - line["bbox"][1]) * 1.5:
                    break
                if title_font is None:
                    title_font = line["font_name"]
                if line["font_name"] != title_font:
                    break
                title_parts.append(line["text"])
                last_y = line["bbox"][3]
            elif title_parts:
                break
        if title_parts:
            self.title = " ".join(title_parts)

    def _get_numbering_level(self, text):
        if re.match(r'^\d+\s', text) or re.match(r'^\d+\.\s', text): return 1
        if re.match(r'^\d+\.\d+', text): return 2
        if re.match(r'^\d+\.\d+\.\d+', text): return 3
        return 0

    def _classify_headings(self):
        last_heading = {'level': 0, 'x_pos': 0}
        for line in self.all_lines:
            text = line['text'].strip()
            if line["bbox"][1] < 50 or line["bbox"][3] > 740: continue
            if self._is_in_filtered_zone(line): continue
            if text == self.title or (self.title and text in self.title): continue
            if len(text) < 3 or len(text) > 150: continue
            if re.match(r'^[•\d\W_]+$', text): continue

            score = 0
            font_ratio = line["font_size"] / self.body_style['size']
            if font_ratio > 1.35: score += 12
            elif font_ratio > 1.15: score += 7
            elif font_ratio > 1.05: score += 2
            if line['is_bold']: score += 5
            if line['font_name'] != self.body_style['font']: score += 2
            if line['alignment'] == 'center': score += 3

            level = 0
            num_level = self._get_numbering_level(text)
            if num_level > 0:
                level = num_level
            else:
                if score >= 17: level = 1
                elif score >= 11: level = 2
                elif score >= 7: level = 3
            if level > 0:
                indent_diff = line['bbox'][0] - last_heading['x_pos']
                if indent_diff > 5 and last_heading['level'] > 0:
                    level = min(level, last_heading['level'] + 1)
                self.outline.append({
                    "level": f"H{level}", "text": text, "page": line["page_num"]
                })
                last_heading = {'level': level, 'x_pos': line['bbox'][0]}

    def process(self):
        # --- MODIFIED: The process flow is updated to include new filtering steps ---

        # 1. Initial data extraction from the PDF
        self._extract_all_lines()
        self._extract_table_content()  # Extract table content early on

        # 2. Analyze styles and special sections like the Table of Contents
        self._determine_body_style()
        self._detect_toc_pages()
        self._extract_title()

        # 3. Perform the core heading classification based on heuristics
        self._classify_headings()

        # 4. --- NEW: Post-processing and noise filtering ---
        # Start with the raw list of headings identified
        clean_outline = self.outline

        # Filter 1: Remove any headings that are identical to the document title
        clean_outline = [h for h in clean_outline if h['text'] != self.title]

        # Filter 2: Remove headings that are likely just dates
        clean_outline = [h for h in clean_outline if not self._is_likely_date(h['text'])]

        # Filter 3: Remove headings whose text content was found inside a table
        final_outline = [h for h in clean_outline if h['text'].strip().lower() not in self.table_texts]

        return {"title": self.title, "outline": final_outline}