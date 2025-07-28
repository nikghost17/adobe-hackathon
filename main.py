import fitz
import re
import os
import json
import joblib
import pandas as pd
from collections import Counter
from sklearn.preprocessing import OneHotEncoder

# --- If parsing.py exists in same dir, with PDFOutlineExtractorV8_Final ---
from parsing import PDFOutlineExtractorV8_Final

def debug(msg):
    print("[DEBUG]", msg)

def improved_extract_title(doc):
    meta_title = doc.metadata.get('title')
    if meta_title and meta_title.strip() and not meta_title.lower().startswith("microsoft word"):
        debug(f"Title from metadata: {meta_title.strip()}")
        return meta_title.strip()
    page = doc[0]
    spans = []
    blocks = page.get_text("dict")["blocks"]
    for b in blocks:
        if b['type'] != 0: continue
        for line in b['lines']:
            for span in line['spans']:
                text = span['text'].strip()
                if not text: continue
                spans.append({
                    "text": text,
                    "size": span['size'],
                    "y": span['origin'][1],
                    "bold": bool(span.get('flags', 0) & 2),
                    "centered": abs((span['bbox'][0] + span['bbox'][2]) / 2 - page.rect.width/2) < page.rect.width * 0.2,
                })
    if not spans: return ""
    max_size = max(s['size'] for s in spans)
    candidates = [s for s in spans if s['size'] >= max_size*0.85 and s['y'] < page.rect.height*0.3 and len(s['text']) > 10]
    candidates.sort(key=lambda s: (s['bold'], s['centered'], -len(s['text'])), reverse=True)
    if candidates:
        title = candidates[0]['text']
        title = re.sub(r"\s*[\-–_ ]*\.[a-z]{3,4}\s*$", "", title, flags=re.I)
        return title.strip()
    spans.sort(key=lambda s: s['size']*1.2 + len(s['text']), reverse=True)
    return spans[0]['text'] if spans else ""

def extract_headers_and_footers(doc, top_pct=0.12, bottom_pct=0.12, min_repeat_ratio=0.7):
    header_candidates, footer_candidates = [], []
    for page in doc:
        page_height = page.rect.height
        blocks = page.get_text("blocks")
        for b in blocks:
            line = b[4].strip()
            if not line: continue
            y0, y1 = b[1], b[3]
            if y0 < page_height * top_pct: header_candidates.append(line)
            elif y1 > page_height * (1 - bottom_pct): footer_candidates.append(line)
    def get_repeats(items, npg, thr): return [t for t,c in Counter(items).items() if c/npg>=thr]
    headers = get_repeats(header_candidates, len(doc), min_repeat_ratio)
    footers = get_repeats(footer_candidates, len(doc), min_repeat_ratio)
    debug(f"Found {len(headers)} headers, {len(footers)} footers")
    return headers, footers

def analyze_text(text):
    has_colon = ':' in text
    numbered = bool(re.match(r'^\d+[\.\)\-]?\s', text))
    num_digits = sum(c.isdigit() for c in text)
    num_uppercase = sum(c.isupper() for c in text)
    special_chars = re.findall(r'[^a-zA-Z0-9\s]', text)
    has_special_char = len(special_chars) > 0
    return has_colon, numbered, num_digits, num_uppercase, has_special_char

def extract_text_properties(doc):
    records = []
    for i, page in enumerate(doc):
        page_num = i + 1
        page_width = page.rect.width
        blocks = page.get_text("dict")["blocks"]
        for block in blocks:
            if block['type'] != 0: continue
            for line in block["lines"]:
                x0s = [span["bbox"][0] for span in line["spans"]]
                indentation = min(x0s) if x0s else 0
                line_text = " ".join(span["text"].strip() for span in line["spans"]).strip()
                line_length = len(line_text)
                avg_x0 = sum(x0s) / len(x0s) if x0s else 0
                max_x1 = max(span["bbox"][2] for span in line["spans"]) if line["spans"] else 0
                if avg_x0 < page_width * 0.1:
                    alignment = "left"
                elif max_x1 > page_width * 0.9:
                    alignment = "right"
                else:
                    alignment = "center"
                max_font_span = max(line["spans"], key=lambda s: s["size"]) if line["spans"] else None
                font_size = max_font_span["size"] if max_font_span else 0
                font_name = max_font_span["font"] if max_font_span else ""
                flags = max_font_span.get("flags", 0) if max_font_span else 0
                is_bold = bool(flags & 2)
                has_colon, numbered, num_digits, num_uppercase, has_special_char = analyze_text(line_text)
                record = dict(
                    text=line_text,
                    page=page_num,
                    font_size=font_size,
                    font_name=font_name,
                    is_bold=is_bold,
                    indentation=indentation,
                    alignment=alignment,
                    line_length=line_length,
                    has_colon=has_colon,
                    is_numbered=numbered,
                    num_digits=num_digits,
                    num_uppercase=num_uppercase,
                    has_special_char=has_special_char
                )
                records.append(record)
    debug(f"Extracted {len(records)} lines from doc")
    return records

def filter_heading_candidates(lines, headers, footers):
    headers_set = set(h.lower() for h in headers)
    footers_set = set(f.lower() for f in footers)
    filtered = []
    for line in lines:
        t = line["text"].strip()
        if not t: continue
        if t.lower() in headers_set or t.lower() in footers_set: continue
        if all(c.isdigit() or not c.isalnum() for c in t): continue
        filtered.append(line)
    debug(f"{len(filtered)} lines after header/footer/body filtering")
    return filtered

def prepare_features(lines, encoder_path=None):
    if not lines: return pd.DataFrame(), None
    df = pd.DataFrame(lines)
    df['is_bold'] = df['is_bold'].astype(int)
    bin_cols = ['has_colon','is_numbered','has_special_char']
    for col in bin_cols:
        df[col] = df[col].astype(int)
    cat_cols = ['font_name','alignment']
    if encoder_path and os.path.exists(encoder_path):
        encoder = joblib.load(encoder_path)
        enc_vals = encoder.transform(df[cat_cols])
    else:
        encoder = OneHotEncoder(sparse=False, handle_unknown='ignore')
        enc_vals = encoder.fit_transform(df[cat_cols])
        if encoder_path: joblib.dump(encoder, encoder_path)
    enc_df = pd.DataFrame(enc_vals, columns=encoder.get_feature_names_out(cat_cols), index=df.index)
    numeric_cols = ['page','font_size','indentation','line_length','num_digits','num_uppercase','is_bold','has_colon','is_numbered','has_special_char']
    final_df = pd.concat([df[numeric_cols], enc_df], axis=1)
    debug(f"Feature dataframe has shape {final_df.shape}, cols: {final_df.columns.tolist()[:8]} ...")
    return final_df, encoder

def is_form_or_table_outline(outline_list):
    if not outline_list:
        return False
    if len(outline_list) > 8:
        short_label_count = sum(len(o['text'].split()) <= 5 for o in outline_list)
        unique_texts = set(o['text'].strip().lower() for o in outline_list)
        if (
            short_label_count / len(outline_list) > 0.7
            or len(unique_texts) / len(outline_list) < 0.7
        ):
            debug("Outline matches a form/table pattern: suppressing it.")
            return True
    return False

def postprocess_outline(title_str, outline_list):
    if is_form_or_table_outline(outline_list):
        return {"title": title_str, "outline": []}
    return {"title": title_str, "outline": outline_list}

def make_outline_json(title, candidate_lines, preds, output_path):
    label_mapping = {0: 'H1', 1: 'H2', 2: 'H3', 3: 'H4', 4: 'H5', 99: 'body'}
    outline = []
    for line, pred in zip(candidate_lines, preds):
        lvl = label_mapping.get(pred, f"X{pred}")
        if lvl in ('H1','H2','H3'):
            outline.append({
                "level": lvl, "text": line["text"], "page": line["page"]
            })
    result = postprocess_outline(title, outline)
    with open(output_path,"w",encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    debug(f"Wrote final outline: {len(result['outline'])} entries")

def pdf_processing_pipeline(
    input_pdf_path,
    output_dir,
    model_path,
    encoder_path
):
    os.makedirs(output_dir, exist_ok=True)
    doc = fitz.open(input_pdf_path)
    title = improved_extract_title(doc)
    headers, footers = extract_headers_and_footers(doc)
    lines = extract_text_properties(doc)
    candidates = filter_heading_candidates(lines, headers, footers)
    if not candidates:
        raise ValueError("No candidate lines found in PDF!")
    features_df, encoder = prepare_features(candidates, encoder_path)
    if model_path and os.path.exists(model_path) and not features_df.empty:
        model = joblib.load(model_path)
        if hasattr(model,'feature_names_in_'):
            wanted = list(model.feature_names_in_)
            features_df = features_df.reindex(columns=wanted, fill_value=0)
        preds = model.predict(features_df)
        debug(f"Predictions: {Counter(preds)}")
    else:
        preds = [99]*len(candidates)
        debug("Model not found or features empty; tagging all as body.")
    #make_outline_json(title, candidates, preds, os.path.join(output_dir,"output_outline.json"))
    print("[+] Pipeline completed. Outline JSON written.")

if __name__ == "__main__":
    input_dir = "/app/input"
    output_dir = "/app/output"
    model_path = "models/xgb_heading_classifier_with_text.pkl"
    encoder_path = "models/onehot_encoder.pkl"

    os.makedirs(output_dir, exist_ok=True)
    pdf_files = [f for f in os.listdir(input_dir) if f.lower().endswith(".pdf")]

    for pdf_file in pdf_files:
        input_pdf_path = os.path.join(input_dir, pdf_file)
        base = os.path.splitext(pdf_file)[0]
        output_json_path = os.path.join(output_dir, f"{base}.json")

        
        pdf_processing_pipeline(
            input_pdf_path=input_pdf_path,
            output_dir=output_dir,
            model_path=model_path,
            encoder_path=encoder_path
        )

        extractor = PDFOutlineExtractorV8_Final(input_pdf_path)
        result = extractor.process()
        with open(output_json_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=4, ensure_ascii=False)
        print(f"[+] Created outline for {pdf_file}: {output_json_path}")
