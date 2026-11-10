import logging
import re

logger = logging.getLogger(__name__)

try:
    import pymupdf as fitz
except ImportError:
    import fitz

_OCR_ENGINE = None

def get_ocr_engine():
    """Lazily loads and returns the RapidOCR engine instance if available."""
    global _OCR_ENGINE
    if _OCR_ENGINE is None:
        try:
            from rapidocr_onnxruntime import RapidOCR
            _OCR_ENGINE = RapidOCR()
            logger.info("RapidOCR engine initialized successfully.")
        except Exception as e:
            logger.warning(f"RapidOCR engine not available: {e}")
            _OCR_ENGINE = False
    return _OCR_ENGINE if _OCR_ENGINE is not False else None

def _is_green_tick_image(img_bytes: bytes) -> bool:
    try:
        import io

        from PIL import Image
        im = Image.open(io.BytesIO(img_bytes))
        if 8 <= im.width <= 32 and 8 <= im.height <= 32:
            rgb = im.convert("RGB")
            green_count = 0
            for r, g, b in list(rgb.getdata()):
                if g > 100 and g > r + 15 and g > b + 15:
                    green_count += 1
            if green_count >= 4:
                return True
    except Exception:
        pass
    return False

def _extract_text_with_green_ticks(doc) -> str:
    """Extracts text while detecting visual green tick marks on option lines (e.g. TCS iON printouts)."""
    try:
        all_xrefs = set()
        for page in doc:
            for img in page.get_images():
                all_xrefs.add(img[0])

        green_xrefs = set()
        for xref in all_xrefs:
            try:
                data = doc.extract_image(xref)
                if _is_green_tick_image(data["image"]):
                    green_xrefs.add(xref)
            except Exception:
                pass

        if not green_xrefs:
            pages = [p.get_text("text") for p in doc]
            return "\n".join(pages)

        all_pages_text = []
        for pno in range(len(doc)):
            page = doc[pno]
            raw_text = page.get_text("text")

            ticks = []
            for img in page.get_images():
                xref = img[0]
                if xref in green_xrefs:
                    for r in page.get_image_rects(xref):
                        ticks.append(r)

            if not ticks:
                all_pages_text.append(raw_text)
                continue

            words = page.get_text("words")
            opt_words = []
            for w in words:
                if w[4] in ["1.", "2.", "3.", "4."]:
                    opt_words.append({"num": w[4][0], "y": w[1]})

            matched_y_levels = []
            for t in ticks:
                closest = None
                min_dist = 999.0
                for opt in opt_words:
                    dist = abs(t.y0 - opt["y"])
                    if dist < min_dist:
                        min_dist = dist
                        closest = opt
                if closest and min_dist < 10.0:
                    matched_y_levels.append(closest)

            if not matched_y_levels:
                all_pages_text.append(raw_text)
                continue

            lines = raw_text.splitlines()
            new_lines = []
            matched_nums = {m["num"] for m in matched_y_levels}
            for line in lines:
                s_line = line.strip()
                matched = False
                for c_opt in matched_nums:
                    if s_line.startswith(f"{c_opt}.") and "[Correct Option]" not in line:
                        new_lines.append(f"{line} [Correct Option]")
                        matched = True
                        break
                if not matched:
                    new_lines.append(line)
            all_pages_text.append("\n".join(new_lines))

        return "\n".join(all_pages_text)
    except Exception as e:
        logger.warning(f"Tick extraction fallback: {e}")
        return "\n".join([p.get_text("text") for p in doc])

def is_allowed_response_url(url: str) -> bool:
    """Validates that a recovered URL is an HTTPS URL from an authorized exam portal domain."""
    try:
        import urllib.parse
        p = urllib.parse.urlparse(url.strip())
        if p.scheme.lower() != "https":
            return False
        hostname = (p.hostname or "").lower()
        if not hostname:
            return False
        allowed = (
            "digialm.com", ".digialm.com",
            "ibpsonline.ibps.in", ".ibpsonline.ibps.in",
            "tcsion.com", ".tcsion.com"
        )
        return any(hostname == d or hostname.endswith("." + d.lstrip(".")) for d in allowed)
    except Exception:
        return False

def extract_pdf_text_with_status(path: str, max_ocr_pages: int = None) -> tuple:
    """
    Extracts text from all pages of a PDF document safely while classifying extraction errors:
    Returns (text, error_code):
      - ("", "empty_file") if 0-byte or 0 pages
      - ("", "password_protected") if doc.needs_pass or doc.is_encrypted
      - ("", "corrupt_pdf") if fitz.FileDataError or file is not a valid PDF
      - ("", "empty_ocr") if PDF contains no readable text layer and OCR yielded no text
      - (text, "") on success
    """
    import os
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        return "", "empty_file"

    try:
        doc = fitz.open(path)
    except (fitz.FileDataError, RuntimeError, Exception) as e:
        logger.warning(f"Failed to open PDF {path}: {e}")
        return "", "corrupt_pdf"

    try:
        if getattr(doc, "needs_pass", False) or getattr(doc, "is_encrypted", False):
            doc.close()
            return "", "password_protected"

        total_pages = len(doc)
        if total_pages == 0:
            doc.close()
            return "", "empty_file"

        sample_chars = sum(len(doc[i].get_text("text").strip()) for i in range(min(3, total_pages)))
        if sample_chars >= 60:
            text = _extract_text_with_green_ticks(doc)
            doc.close()
            return (text, "") if text.strip() else ("", "empty_ocr")

        # Document is image-based / scanned -> run RapidOCR
        logger.info(f"PDF {path} has no embedded text layer. Running RapidOCR fallback...")
        ocr = get_ocr_engine()
        if not ocr:
            doc.close()
            return "", "empty_ocr"

        ocr_pages = []
        limit = min(max_ocr_pages, total_pages) if max_ocr_pages else min(total_pages, 25)
        for i in range(limit):
            page = doc[i]
            pix = page.get_pixmap(dpi=150)
            img_bytes = pix.tobytes("png")
            result, _ = ocr(img_bytes)
            if result:
                ocr_pages.append("\n".join([line[1] for line in result]))
        doc.close()
        full_ocr = "\n".join(ocr_pages)
        return (full_ocr, "") if full_ocr.strip() else ("", "empty_ocr")
    except Exception as e:
        logger.error(f"Error extracting PDF text from {path}: {e}")
        try:
            doc.close()
        except Exception:
            pass
        return "", "corrupt_pdf"

def extract_pdf_text(path: str, max_ocr_pages: int = None) -> str:
    """
    Extracts text from all pages of a PDF document safely.
    If the document has no digital text layer (scanned or printed as images),
    automatically falls back to RapidOCR.
    """
    text, _ = extract_pdf_text_with_status(path, max_ocr_pages)
    return text

def recover_digialm_url_from_pdf(path: str) -> str:
    """
    Inspects PDF metadata, link annotations, and runs a quick OCR on page 0
    to recover the original DigiALM / TCS web URL if printed as a raster PDF.
    Returns the live full URL string if successfully reconstructed and validated, else empty string.
    """
    try:
        doc = fitz.open(path)
        if getattr(doc, "needs_pass", False) or getattr(doc, "is_encrypted", False):
            doc.close()
            return ""
        total_pages = len(doc)
        # 1. Embedded annotations / URI links
        for page in doc[:min(5, total_pages)]:
            for link in page.get_links():
                uri = link.get("uri", "")
                if is_allowed_response_url(uri):
                    doc.close()
                    return uri

        # 2. Digital text layer
        for page in doc[:min(3, total_pages)]:
            txt = page.get_text("text")
            m = re.search(r'(https://[^\s"\'<>]+(?:digialm|touchstone|ibpsonline)[^\s"\'<>]*)', txt)
            if m:
                cand = m.group(1)
                if is_allowed_response_url(cand):
                    doc.close()
                    return cand

        # 3. Document Title metadata + Page 0 OCR footer (Microsoft Print to PDF)
        meta_title = doc.metadata.get("title", "")
        m_fn = re.search(r'([A-Za-z0-9_-]+\.html)', meta_title)
        meta_raw_fn = m_fn.group(1) if m_fn else ""

        ocr = get_ocr_engine()
        if ocr and total_pages > 0:
            pix = doc[0].get_pixmap(dpi=150)
            res, _ = ocr(pix.tobytes("png"))
            if res:
                for line in res:
                    text_line = line[1]
                    if "http" in text_line and "digialm.com" in text_line and ".html" in text_line:
                        cand_url = text_line.strip()
                        if is_allowed_response_url(cand_url):
                            doc.close()
                            return cand_url
                    if "digialm.com" in text_line and "touchstone" in text_line:
                        m_dir = re.search(r'([A-Za-z0-9_./]+)/(\d+)\.\.\.', text_line)
                        if m_dir and meta_raw_fn:
                            base_path = m_dir.group(1).lstrip('/')
                            prefix_digits = m_dir.group(2)
                            m_sub = re.search(r'^(\d+)_(.+)$', meta_raw_fn)
                            if m_sub:
                                suffix_digits = m_sub.group(1)
                                clean_fn = m_sub.group(2)
                                full_folder = prefix_digits + suffix_digits
                                url = f"https://{base_path}/{full_folder}/{clean_fn}"
                                clean_url = re.sub(r"(?<!:)//+", "/", url)
                                if is_allowed_response_url(clean_url):
                                    doc.close()
                                    return clean_url
        doc.close()
    except Exception as e:
        logger.warning(f"Error checking PDF for DigiALM URL: {e}")
    return ""

def parse_html_response_sheet(html_content: str) -> str:
    """
    Pre-processes HTML response sheets (DigiALM, TCS iON, IBPS).
    Explicitly marks correct answers identified by CSS classes (.rightAns)
    or checkmark images (tick.png / correct.png) so they are preserved in text.
    """
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html_content, "html.parser")

        # Mark correct answer rows or cells
        for el in soup.find_all(class_=re.compile(r"rightAns|correct", re.IGNORECASE)):
            if "[Correct Option]" not in el.text:
                el.append(" [Correct Option] ")

        # Mark tick/correct image tags
        for img in soup.find_all("img"):
            src = img.get("src", "")
            alt = img.get("alt", "")
            if any(k in (src + " " + alt).lower() for k in ["tick", "correct", "right"]):
                parent = img.parent
                if parent and "[Correct Option]" not in parent.text:
                    img.replace_with(" [Correct Option] ")
                else:
                    img.decompose()

        return soup.get_text(separator="\n")
    except Exception as e:
        logger.error(f"Error parsing HTML response sheet: {e}")
        return html_content

def detect_exam(text: str, exams: dict):
    """
    Detects which configured exam corresponds to the extracted PDF text.
    Matches aliases and display names using word-boundary matching for short acronyms
    to prevent false positives (e.g. 'STI' matching inside 'QUESTION').
    """
    upper_text = text.upper()
    matches = []

    for key, config in exams.items():
        aliases = [config.get("display_name", "")] + config.get("aliases", [])
        hits = []
        for a in aliases:
            if not a:
                continue
            clean_a = a.strip()
            # For short alphanumeric acronyms (<= 4 chars like STI, PSI, ASO, ZP, DMA), use strict word boundary
            if len(clean_a) <= 4 and clean_a.isalnum():
                pattern = r"(?<![A-Za-z0-9])" + re.escape(clean_a) + r"(?![A-Za-z0-9])"
                if re.search(pattern, text, re.IGNORECASE):
                    hits.append(clean_a)
            else:
                if clean_a.upper() in upper_text:
                    hits.append(clean_a)

        if hits:
            matches.append((key, config, hits))

    if len(matches) == 1:
        return {"status": "detected", "key": matches[0][0], "config": matches[0][1], "matched_aliases": matches[0][2]}
    if len(matches) > 1:
        # Prioritize match with the highest hit count or longest matched alias
        sorted_matches = sorted(matches, key=lambda m: (len(m[2]), max(len(x) for x in m[2])), reverse=True)
        # If top match has significantly stronger hits than second match, select it
        if len(sorted_matches[0][2]) > len(sorted_matches[1][2]):
            return {"status": "detected", "key": sorted_matches[0][0], "config": sorted_matches[0][1], "matched_aliases": sorted_matches[0][2]}
        return {"status": "ambiguous", "matches": [{"key": k, "name": c["display_name"]} for k, c, _ in matches]}
    return {"status": "not_found"}

def extract_post_and_metadata(text: str) -> dict:
    """
    Extracts Candidate Metadata and Applied Post Name from Response Sheet text.
    Handles TCS iON, IBPS, and Maharashtra Saralsewa Bharti headers.
    """
    metadata = {
        "candidate_name": None,
        "roll_number": None,
        "post_name": "General (सर्वसाधारण)",
        "test_date": None,
        "test_time": None
    }

    # 1. Post Name extraction from header
    post_match = re.search(
        r"(?:Post\s*(?:Name)?|Applied\s*Post|Subject|पदाचे\s*नाव|संवर्ग)\s*[:\-]?\s*\n?\s*([A-Za-z0-9\s&,/\-\u0900-\u097F]+?)(?=\n|Test|Roll|Date|$)",
        text[:3500],
        re.IGNORECASE
    )
    if post_match:
        raw_post = post_match.group(1).strip()
        raw_post = re.sub(r"\s+", " ", raw_post)
        if len(raw_post) >= 3 and not raw_post.isdigit():
            metadata["post_name"] = raw_post[:50]

    # If post name is still generic, detect known Maharashtra Saralsewa posts from text
    first_chunk = text[:5000].lower()
    known_posts = [
        ("तलाठी", "तलाठी (Talathi)"),
        ("talathi", "तलाठी (Talathi)"),
        ("ग्रामसेवक", "ग्रामसेवक (Gramsevak)"),
        ("gramsevak", "ग्रामसेवक (Gramsevak)"),
        ("कनिष्ठ लिपिक", "कनिष्ठ लिपिक (Junior Clerk)"),
        ("junior clerk", "कनिष्ठ लिपिक (Junior Clerk)"),
        ("आरोग्य सेवक", "आरोग्य सेवक (Arogya Sevak)"),
        ("arogya sevak", "आरोग्य सेवक (Arogya Sevak)"),
        ("आरोग्य सेविका", "आरोग्य सेविका (Health Worker)"),
        ("वनरक्षक", "वनरक्षक (Forest Guard)"),
        ("vanrakshak", "वनरक्षक (Forest Guard)"),
        ("पोलीस शिपाई", "पोलीस शिपाई (Police Constable)"),
        ("police constable", "पोलीस शिपाई (Police Constable)"),
        ("विस्तार अधिकारी", "विस्तार अधिकारी (Extension Officer)"),
        ("प्रयोगशाळा वैज्ञानिक", "प्रयोगशाळा वैज्ञानिक अधिकारी (Lab Tech)"),
        ("कनिष्ठ लेखापाल", "कनिष्ठ लेखापाल (Junior Accountant)"),
        ("लिपिक टंकलेखक", "लिपिक-टंकलेखक (Clerk Typist)"),
        ("पशुधन पर्यवेक्षक", "पशुधन पर्यवेक्षक (Livestock Supervisor)"),
        ("शिपाई", "शिपाई (Peon)"),
        ("peon", "शिपाई (Peon)"),
        ("कक्ष सेवक", "कक्ष सेवक (Ward Boy)"),
        ("ward boy", "कक्ष सेवक (Ward Boy)"),
        ("सफाईगार", "सफाईगार (Sweeper)")
    ]
    for term, formal_name in known_posts:
        if term in first_chunk:
            metadata["post_name"] = formal_name
            break

    # Candidate Name
    name_match = re.search(r"(?:Participant\s*Name|Candidate\s*Name|उमेदवाराचे\s*नाव)\s*[:\-]?\s*\n?\s*([A-Za-z\s\u0900-\u097F]+?)(?=\n|Test|Subject|Roll|Date|$)", text[:2500], re.IGNORECASE)
    if name_match:
        metadata["candidate_name"] = name_match.group(1).strip()[:50]

    # Roll / Registration Number
    roll_match = re.search(r"(?:Participant\s*ID|Roll\s*(?:Number|No)|Registration\s*(?:Number|No))\s*[:\-]?\s*\n?\s*([A-Za-z0-9]+)", text[:2500], re.IGNORECASE)
    if roll_match:
        metadata["roll_number"] = roll_match.group(1).strip()

    # Test Date
    date_match = re.search(r"(?:Test\s*Date|Exam\s*Date|दिनांक)\s*[:\-]?\s*\n?\s*([0-9/\-]+)", text[:2500], re.IGNORECASE)
    if date_match:
        metadata["test_date"] = date_match.group(1).strip()

    # Test Time
    time_match = re.search(r"(?:Test\s*Time|Exam\s*Time|वेळ|सत्र)\s*[:\-]?\s*\n?\s*([0-9:APMapm\s\-]+)", text[:2500], re.IGNORECASE)
    if time_match:
        metadata["test_time"] = time_match.group(1).strip()[:30]

    # Test Center & District Extraction
    metadata["center_name"] = "TCS iON / Official Center"
    metadata["district"] = "महाराष्ट्र (सर्वसाधारण)"
    center_match = re.search(
        r"(?:Test\s*Center\s*(?:Name)?|Center\s*(?:Name)?|Venue|परीक्षा\s*केंद्र)\s*[:\-]?\s*\n?\s*([A-Za-z0-9\s&,/\-\u0900-\u097F]+?)(?=\n|Subject|Roll|Date|$)",
        text[:3500],
        re.IGNORECASE
    )
    if center_match:
        raw_center = center_match.group(1).strip()
        metadata["center_name"] = re.sub(r"\s+", " ", raw_center)[:60]

    district_map = {
        "pune": "पुणे (Pune)", "पुणे": "पुणे (Pune)",
        "mumbai": "मुंबई (Mumbai)", "मुंबई": "मुंबई (Mumbai)",
        "nagpur": "नागपूर (Nagpur)", "नागपूर": "नागपूर (Nagpur)",
        "nashik": "नाशिक (Nashik)", "नाशिक": "नाशिक (Nashik)",
        "aurangabad": "छ. संभाजीनगर (Aurangabad)", "संभाजीनगर": "छ. संभाजीनगर", "sambhajinagar": "छ. संभाजीनगर",
        "kolhapur": "कोल्हापूर (Kolhapur)", "कोल्हापूर": "कोल्हापूर (Kolhapur)",
        "solapur": "सोलापूर (Solapur)", "सोलापूर": "सोलापूर (Solapur)",
        "thane": "ठाणे (Thane)", "ठाणे": "ठाणे (Thane)",
        "amravati": "अमरावती (Amravati)", "अमरावती": "अमरावती (Amravati)",
        "nanded": "नांदेड (Nanded)", "नांदेड": "नांदेड (Nanded)",
        "jalgaon": "जळगाव (Jalgaon)", "जळगाव": "जळगाव (Jalgaon)",
        "akola": "अकोला (Akola)", "अकोला": "अकोला (Akola)",
        "latur": "लातूर (Latur)", "लातूर": "लातूर (Latur)",
        "dhule": "धुळे (Dhule)", "धुळे": "धुळे (Dhule)",
        "ahmednagar": "अहिल्यानगर (Ahmednagar)", "ahilyanagar": "अहिल्यानगर", "अहमदनगर": "अहिल्यानगर",
        "satara": "सातारा (Satara)", "सातारा": "सातारा (Satara)",
        "beed": "बीड (Beed)", "बीड": "बीड (Beed)",
        "yavatmal": "यवतमाळ (Yavatmal)", "यवतमाळ": "यवतमाळ (Yavatmal)",
        "jalna": "जालना (Jalna)", "जालना": "जालना (Jalna)",
        "chandrapur": "चंद्रपूर (Chandrapur)", "चंद्रपूर": "चंद्रपूर (Chandrapur)",
        "parbhani": "परभणी (Parbhani)", "परभणी": "परभणी (Parbhani)",
        "sangli": "सांगली (Sangli)", "सांगली": "सांगली (Sangli)",
        "buldhana": "बुलढाणा (Buldhana)", "buldana": "बुलढाणा (Buldhana)", "बुलढाणा": "बुलढाणा",
        "gondia": "गोंदिया (Gondia)", "गोंदिया": "गोंदिया (Gondia)",
        "wardha": "वर्धा (Wardha)", "वर्धा": "वर्धा (Wardha)",
        "bhandara": "भंडारा (Bhandara)", "भंडारा": "भंडारा (Bhandara)",
        "raigad": "रायगड (Raigad)", "रायगड": "रायगड (Raigad)",
        "ratnagiri": "रत्नागिरी (Ratnagiri)", "रत्नागिरी": "रत्नागिरी (Ratnagiri)",
        "sindhudurg": "सिंधुदुर्ग (Sindhudurg)", "सिंधुदुर्ग": "सिंधुदुर्ग",
        "dharashiv": "धाराशिव (Dharashiv)", "osmanabad": "धाराशिव", "उस्मानाबाद": "धाराशिव",
        "nandurbar": "नंदुरबार (Nandurbar)", "नंदुरबार": "नंदुरबार",
        "hingoli": "हिंगोली (Hingoli)", "हिंगोली": "हिंगोली",
        "gadchiroli": "गडचिरोली (Gadchiroli)", "गडचिरोली": "गडचिरोली",
        "palghar": "पालघर (Palghar)", "पालघर": "पालघर",
        "washim": "वाशीम (Washim)", "वाशीम": "वाशीम"
    }

    # Search in center name and first 4000 chars of document for district
    search_context = (metadata.get("center_name", "") + " " + text[:4000]).lower()
    for d_key, formal_d in district_map.items():
        if d_key in search_context:
            metadata["district"] = formal_d
            break

    return metadata

def parse_answers(text: str):
    """
    Parses questions, sections, and candidate responses from response-sheet text.
    Supports TCS iON, SSC, RRB, and standard PSC formats.
    """
    records = []

    # Detect section/subject headers (Supports English and Marathi Devanagari script)
    # Strictly require colon/dash delimiter and exclude words like 'Part-time'
    section_pattern = re.compile(
        r"(?m)^\s*(?:Section(?:\s*Name)?|Subject|विभाग|घटक|Part\s*[:\-])\s*[:\-]+\s*([A-Za-z0-9\s&,/\-\u0900-\u097F]+?)\s*$",
        re.IGNORECASE
    )

    # Split questions ONLY at line starts to prevent mid-text mentions (e.g. "Refer to Q. 2") creating phantom questions
    # Supports English ("Q. 1", "Question 1") and Marathi ("प्रश्न १", "प्रश्न क्र. १", "प्र. क्र. 1")
    qnum_pattern = r"(?m)(?=^\s*(?:Q\s*\.\s*\d+|Question\s*(?:No\.?|Number)?\s*\d+|प्रश्न\s*(?:क्र\.?|क्रमांक)?\s*[\d१-९]+|प्र\s*\.\s*क्र\s*\.\s*[\d१-९]+))"
    qid_pattern = r"(?m)(?=^\s*Question\s*ID\s*[:\-])"
    if re.search(qnum_pattern, text, re.IGNORECASE):
        parts = re.split(qnum_pattern, text, flags=re.IGNORECASE)
    elif re.search(qid_pattern, text, re.IGNORECASE):
        parts = re.split(qid_pattern, text, flags=re.IGNORECASE)
    else:
        parts = re.split(r"(?m)(?=^\s*(?:Q\.\s*\d+|Question\s*\d+))", text, flags=re.IGNORECASE)

    current_section = "General Paper"
    dev_digits = {"०": "0", "१": "1", "२": "2", "३": "3", "४": "4", "५": "5", "६": "6", "७": "7", "८": "8", "९": "9"}

    for block in parts:
        if not block.strip():
            continue

        sec_match = section_pattern.search(block)
        if sec_match:
            candidate_sec = sec_match.group(1).strip()
            candidate_sec = re.sub(r"\s+", " ", candidate_sec)
            if len(candidate_sec) > 3 and not candidate_sec.isdigit():
                current_section = candidate_sec[:40]

        qid_match = re.search(r"(?:Question|प्रश्न)\s*(?:ID|आयडी)?\s*[:\-]+\s*(\w+)", block, re.IGNORECASE)
        qnum_match = re.search(r"(?:Q\.\s*|Question\s*(?:No\.?|Number)?\s*|प्रश्न\s*(?:क्र\.?|क्रमांक)?\s*|प्र\s*\.\s*क्र\s*\.\s*)([\d१-९]+)", block, re.IGNORECASE)

        if not qid_match and not qnum_match:
            continue

        raw_qnum_str = qnum_match.group(1) if qnum_match else ""
        norm_qnum_str = "".join(dev_digits.get(ch, ch) for ch in raw_qnum_str) if raw_qnum_str else ""
        qid = qid_match.group(1) if qid_match else norm_qnum_str

        # 1. Direct Option ID match
        selected_opt = re.search(r"(?:Answer\s*Given\s*by\s*Candidate|उमेदवाराने\s*दिलेले\s*उत्तर)\s*[:\-].*?Option\s*ID\s*[:\-]*\s*(\w+)", block, re.IGNORECASE | re.DOTALL)
        correct_opt = re.search(r"(?:Correct\s*Answer|अधिकृत\s*अचूक\s*उत्तर)\s*[:\-].*?Option\s*ID\s*[:\-]*\s*(\w+)", block, re.IGNORECASE | re.DOTALL)

        # 2. Chosen Option Number (1, 2, 3, 4, Marathi १-४, or --)
        chosen_match = re.search(r"(?:Chosen|Selected|Given|Candidate|निवडलेला|दिलेला|दिलेले)\s*(?:Option|Answer|पर्याय|उत्तर)\s*[:\-]+\s*([1-4१-४]|-+)", block, re.IGNORECASE)
        # 3. Correct Option Number directly in text (e.g. Correct Option : 2 or checkmarks)
        correct_num_match = re.search(r"(?:Correct|Right|अचूक|बरोबर|योग्य)\s*(?:Option|Answer|पर्याय|उत्तर)\s*[:\-]+\s*([1-4१-४])\b", block, re.IGNORECASE)

        if not correct_num_match and not correct_opt:
            # Check for [Correct Option] from HTML or checkmark symbol (✓ / ✔ / ☑ / rightAns)
            tick_match = re.search(
                r"\b([1-4१-४])\s*[\.\):\-](?:(?!\b[1-4१-४]\s*[\.\):\-]).)*?(?:\[Correct Option\]|[✓✔☑]|\brightAns\b)",
                block,
                re.IGNORECASE | re.DOTALL
            )
            if not tick_match:
                tick_match = re.search(
                    r"(?:\[Correct Option\]|[✓✔☑]|\brightAns\b)(?:(?!\b[1-4१-४]\s*[\.\):\-]).)*?\b([1-4१-४])\s*[\.\):\-]",
                    block,
                    re.IGNORECASE | re.DOTALL
                )
            if tick_match:
                correct_num_match = tick_match

        status_match = re.search(r"(?:Status|स्थिती)\s*[:\-]+\s*([A-Za-z\s\u0900-\u097F]+)", block, re.IGNORECASE)
        opt_ids = dict(re.findall(r"Option\s*([1-4])\s*ID\s*[:\-]+\s*(\w+)", block, re.IGNORECASE))

        given_opt_num = None
        if chosen_match:
            val = chosen_match.group(1).strip()
            val = dev_digits.get(val, val)
            if val.isdigit():
                given_opt_num = val

        correct_opt_num = None
        if correct_num_match:
            cval = correct_num_match.group(1).strip()
            correct_opt_num = dev_digits.get(cval, cval)

        selected_id = None
        if selected_opt:
            selected_id = selected_opt.group(1)
        elif given_opt_num and opt_ids.get(given_opt_num):
            selected_id = opt_ids[given_opt_num]

        correct_id = None
        if correct_opt:
            correct_id = correct_opt.group(1)
        elif correct_opt_num and opt_ids.get(correct_opt_num):
            correct_id = opt_ids[correct_opt_num]

        # Bidirectional Option ID <-> Option Number resolution
        if not correct_opt_num and correct_id and opt_ids:
            for onum, oid in opt_ids.items():
                if str(oid).strip() == str(correct_id).strip():
                    correct_opt_num = str(onum)
                    break

        if not given_opt_num and selected_id and opt_ids:
            for onum, oid in opt_ids.items():
                if str(oid).strip() == str(selected_id).strip():
                    given_opt_num = str(onum)
                    break

        status = status_match.group(1).strip() if status_match else None

        clean_excerpt = re.sub(r"(?:Question|Option\s*\d|Status|Chosen|Answer\s*Given|Correct\s*Answer).*?(?:\n|$)", "", block, flags=re.IGNORECASE)
        clean_excerpt = re.sub(r"\s+", " ", clean_excerpt).strip()[:400]
        if not clean_excerpt:
            clean_excerpt = block[:300]

        # Extract full question text
        qtext_m = re.search(r"(?:Q\.\s*\d+|Question\s*(?:No\.?|Number)?\s*\d+)\s*\n+(.*?)(?=\n+\s*(?:Ans\b|[1-4]\s*[\.\):\-]|Question\s*Type|Question\s*ID))", block, re.DOTALL | re.IGNORECASE)
        if qtext_m:
            full_q_text = qtext_m.group(1).strip()
            full_q_text = re.sub(r"\s+", " ", full_q_text)
        else:
            full_q_text = clean_excerpt

        # Extract all options (1 to 4, Devanagari १-४, or Letters A-D)
        options = {}
        opt_matches = re.findall(
            r"(?:\n|^)\s*([1-4]|[१-४]|[A-Da-d])\s*[\.\):\-]\s*([^\n]+(?:\n(?!(?:[1-4]|[१-४]|[A-Da-d])\s*[\.\):\-]|Question|Status|Ans|Chosen|Option\s*\d\s*ID)[^\n]+)*)",
            block
        )
        devanagari_map = {"१": "1", "२": "2", "३": "3", "४": "4"}
        letter_map = {"A": "1", "B": "2", "C": "3", "D": "4", "a": "1", "b": "2", "c": "3", "d": "4"}

        for raw_num, opt_val in opt_matches:
            normalized_num = devanagari_map.get(raw_num, letter_map.get(raw_num, raw_num))
            # If option text explicitly contains checkmark or [Correct Option], mark as correct
            if not correct_opt_num and re.search(r"\[Correct Option\]|rightAns|[✓✔☑]", opt_val, re.IGNORECASE):
                correct_opt_num = str(normalized_num)
                if opt_ids.get(correct_opt_num):
                    correct_id = opt_ids[correct_opt_num]

            cleaned_opt = re.sub(r"\[Correct Option\]|rightAns|[✓✔☑]", "", opt_val, flags=re.IGNORECASE).strip()
            cleaned_opt = re.sub(r"\s+", " ", cleaned_opt)
            options[str(normalized_num)] = cleaned_opt

        # Final fallback check: if correct_opt_num still None but correct_id exists
        if not correct_opt_num and correct_id and opt_ids:
            for onum, oid in opt_ids.items():
                if str(oid).strip() == str(correct_id).strip():
                    correct_opt_num = str(onum)
                    break

        chosen_text = options.get(str(given_opt_num), "") if given_opt_num else ""
        correct_text = options.get(str(correct_opt_num), "") if correct_opt_num else ""

        # Extract comprehension / passage if present
        comp_m = re.search(r"(?:Comprehension|उतारा)\s*[:\-]+\s*(.*?)(?=\bSubQuestion\b|\bQ\.\s*\d+\b|\bQuestion\s*ID|$)", block, re.DOTALL | re.IGNORECASE)
        comp_text = comp_m.group(1).strip() if comp_m else ""
        if comp_text:
            comp_text = re.sub(r"\s+", " ", comp_text)

        sec_qnum = int(qnum_match.group(1)) if qnum_match and qnum_match.group(1).isdigit() else (len(records) + 1)
        seq_num = len(records) + 1

        records.append({
            "question_number": seq_num,
            "section_question_number": sec_qnum,
            "question_id": qid,
            "section": current_section,
            "question_text": full_q_text,
            "options": options,
            "selected_option_id": selected_id,
            "correct_option_id": correct_id,
            "chosen_option_number": given_opt_num,
            "chosen_option_text": chosen_text,
            "correct_option_number": correct_opt_num,
            "correct_option_text": correct_text,
            "comprehension": comp_text,
            "option_ids": opt_ids,
            "status_text": status,
            "raw_excerpt": clean_excerpt
        })

    # Robust fallback: If structured TCS/iON parsing found 0 or very few questions,
    # parse general MCQ compilation / question bank format (Q. 1, 1., Options A-D / 1-4, Ans)
    if not records or len(records) < 3:
        general_records = parse_general_mcqs(text)
        if len(general_records) > len(records):
            return general_records

    return records

def parse_general_mcqs(text: str) -> list[dict]:
    """
    Universal MCQ Parser for Bulk Question Banks and Compilation PDFs.
    Parses questions formatted as:
      1. Question text / Q. 1 / प्रश्न १ / प्र. क्र. १
      A) / (A) / 1) / (1) Option text
      Ans: B / उत्तर: B / Answer: 2 / [Correct Option]
    """
    records = []
    dev_digits = {"०": "0", "१": "1", "२": "2", "३": "3", "४": "4", "५": "5", "६": "6", "७": "7", "८": "8", "९": "9"}
    def norm_num(s):
        if not s:
            return ""
        return "".join(dev_digits.get(c, c) for c in str(s))

    # Match section headers
    sec_pattern = re.compile(
        r"(?m)^\s*(?:Section(?:\s*Name)?|Subject|विभाग|घटक|Part\s*[:\-])\s*[:\-]+\s*([A-Za-z0-9\s&,/\-\u0900-\u097F]+?)\s*$",
        re.IGNORECASE
    )

    # Match question starters at line starts
    q_pattern = re.compile(
        r"(?m)^\s*(?:(?:Q(?:ue)?\.?|Question|प्रश्न|प्र\s*\.\s*क्र\.?)\s*(?:No\.?|Number)?\s*([\d१-९]+)|(\d+|[१-९]+)\s*[\.\:\-]\s+)(.*?)$",
        re.IGNORECASE
    )
    matches = list(q_pattern.finditer(text))
    if not matches:
        return []

    ans_pattern = re.compile(
        r"(?:Ans(?:wer)?|उत्तर|Correct(?:\s*Option)?|योग्य\s*पर्याय|अचूक\s*उत्तर)\s*[:\-\.]*\s*(?:Option\s*)?[\(\[]?([A-Da-d1-4१-४])[\)\]]?",
        re.IGNORECASE
    )
    opt_line_pattern = re.compile(
        r"^\s*(?:[\(\[]?([A-Da-d1-4१-४])[\)\]\.\:\-]\s*|\b([A-Da-d1-4१-४])[\)\.\:\-]\s+)(.*)$",
        re.IGNORECASE
    )

    current_section = "General Paper"

    for idx in range(len(matches)):
        m = matches[idx]
        start_pos = m.start()
        end_pos = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        block = text[start_pos:end_pos].strip()

        # Check for section header inside block
        sec_m = sec_pattern.search(block)
        if sec_m:
            cand_sec = sec_m.group(1).strip()
            cand_sec = re.sub(r"\s+", " ", cand_sec)
            if len(cand_sec) > 3 and not cand_sec.isdigit():
                current_section = cand_sec[:40]

        raw_qnum = m.group(1) or m.group(2) or str(idx + 1)
        qnum = norm_num(raw_qnum)

        header_text = m.group(3).strip()
        lines = block.splitlines()

        q_lines = [header_text] if header_text else []
        options = {}
        correct_num = None

        in_options = False
        for line in lines[1:]:
            s_line = line.strip()
            if not s_line:
                continue

            ans_m = ans_pattern.search(s_line)
            if ans_m:
                raw_a = ans_m.group(1).upper()
                k_map = {"A": "1", "B": "2", "C": "3", "D": "4"}
                correct_num = k_map.get(norm_num(raw_a), norm_num(raw_a))
                continue

            opt_m = opt_line_pattern.match(s_line)
            if opt_m:
                in_options = True
                k_raw = opt_m.group(1) or opt_m.group(2)
                k_raw = k_raw.upper()
                k_map = {"A": "1", "B": "2", "C": "3", "D": "4"}
                opt_key = k_map.get(norm_num(k_raw), norm_num(k_raw))
                val = opt_m.group(3).strip()

                if re.search(r"\[Correct Option\]|rightAns|[✓✔☑]", val, re.IGNORECASE):
                    correct_num = opt_key
                val = re.sub(r"\[Correct Option\]|rightAns|[✓✔☑]", "", val, flags=re.IGNORECASE).strip()
                if opt_key in ("1", "2", "3", "4"):
                    options[opt_key] = val
            elif not in_options:
                q_lines.append(s_line)
            elif in_options and len(options) > 0:
                last_k = sorted(options.keys())[-1]
                options[last_k] = (options[last_k] + " " + s_line).strip()

        full_q = " ".join(q_lines).strip()
        full_q = re.sub(r"\s+", " ", full_q)

        if len(options) >= 2 and full_q:
            c_num = correct_num or "1"
            records.append({
                "question_number": int(qnum) if qnum.isdigit() else len(records) + 1,
                "section_question_number": int(qnum) if qnum.isdigit() else len(records) + 1,
                "question_id": str(qnum),
                "section": current_section,
                "question_text": full_q,
                "options": options,
                "selected_option_id": None,
                "correct_option_id": c_num,
                "chosen_option_number": None,
                "chosen_option_text": "",
                "correct_option_number": c_num,
                "correct_option_text": options.get(str(c_num), options.get("1", "")),
                "comprehension": "",
                "option_ids": {},
                "status_text": "Answered" if correct_num else "Unanswered",
                "raw_excerpt": full_q[:300]
            })

    return records

def score_answers(records: list, exam_config: dict):
    """
    Computes candidate score, count of correct/incorrect/unanswered questions,
    accuracy rate, and complete Subject-wise / Section-wise statistics.
    Supports Option IDs, Option Numbers, and External Answer Keys.
    """
    positive_marks = float(exam_config.get("positive_marks", 1.0))
    negative_marks = float(exam_config.get("negative_marks", 0.0))
    external_key = exam_config.get("answer_key", {})
    has_answer_keys = any(bool(r.get("correct_option_number") or r.get("correct_option_id")) for r in records) or bool(external_key)

    correct_count = 0
    wrong_count = 0
    unanswered_count = 0
    total_score = 0.0

    sections_stat = {}

    for idx, row in enumerate(records, start=1):
        s_id = row.get("selected_option_id")
        c_id = row.get("correct_option_id")
        chosen_num = row.get("chosen_option_number")
        correct_num = row.get("correct_option_number")
        qid = str(row.get("question_id", ""))
        sec = row.get("section", "General Paper")

        if sec not in sections_stat:
            sections_stat[sec] = {
                "total": 0, "attempted": 0, "correct": 0,
                "incorrect": 0, "unanswered": 0, "score": 0.0
            }
        sections_stat[sec]["total"] += 1

        key_ans = external_key.get(qid) or external_key.get(str(idx))
        is_answered = bool((s_id and s_id not in ("0", "NONE", "NA", "-")) or chosen_num)

        if not is_answered:
            row["evaluation"] = "unanswered"
            unanswered_count += 1
            sections_stat[sec]["unanswered"] += 1
        elif c_id and s_id:
            # 1. Option ID direct comparison
            sections_stat[sec]["attempted"] += 1
            if s_id == c_id:
                row["evaluation"] = "correct"
                total_score += positive_marks
                correct_count += 1
                sections_stat[sec]["correct"] += 1
                sections_stat[sec]["score"] += positive_marks
            else:
                row["evaluation"] = "incorrect"
                total_score -= negative_marks
                wrong_count += 1
                sections_stat[sec]["incorrect"] += 1
                sections_stat[sec]["score"] -= negative_marks
        elif chosen_num and correct_num:
            # 2. Direct option number comparison (1-4)
            sections_stat[sec]["attempted"] += 1
            if str(chosen_num).strip() == str(correct_num).strip():
                row["evaluation"] = "correct"
                total_score += positive_marks
                correct_count += 1
                sections_stat[sec]["correct"] += 1
                sections_stat[sec]["score"] += positive_marks
            else:
                row["evaluation"] = "incorrect"
                total_score -= negative_marks
                wrong_count += 1
                sections_stat[sec]["incorrect"] += 1
                sections_stat[sec]["score"] -= negative_marks
        elif key_ans and chosen_num:
            # 3. External key comparison (letters A/B/C/D or numbers 1-4)
            sections_stat[sec]["attempted"] += 1
            num_to_letter = {"1": "A", "2": "B", "3": "C", "4": "D"}
            chosen_letter = num_to_letter.get(str(chosen_num), str(chosen_num)).upper()
            if chosen_letter == str(key_ans).strip().upper() or str(chosen_num) == str(key_ans).strip():
                row["evaluation"] = "correct"
                total_score += positive_marks
                correct_count += 1
                sections_stat[sec]["correct"] += 1
                sections_stat[sec]["score"] += positive_marks
            else:
                row["evaluation"] = "incorrect"
                total_score -= negative_marks
                wrong_count += 1
                sections_stat[sec]["incorrect"] += 1
                sections_stat[sec]["score"] -= negative_marks
        else:
            row["evaluation"] = "attempted_unverified"

    for sec, data in sections_stat.items():
        att = data["attempted"]
        data["accuracy"] = round((data["correct"] / att * 100.0), 1) if att > 0 else 0.0
        data["score"] = round(data["score"], 2)

    attempted_count = correct_count + wrong_count
    accuracy = (correct_count / attempted_count * 100.0) if attempted_count > 0 else 0.0

    return {
        "total_parsed": len(records),
        "attempted": attempted_count,
        "correct": correct_count,
        "incorrect": wrong_count,
        "unanswered": unanswered_count,
        "score": round(total_score, 2),
        "accuracy": round(accuracy, 2),
        "positive_marks": positive_marks,
        "negative_marks": negative_marks,
        "sections": sections_stat,
        "records": records,
        "has_answer_key": has_answer_keys,
        "error": None if has_answer_keys or len(records) == 0 else "NO_ANSWER_KEY",
        "warning": None if has_answer_keys or len(records) == 0 else "या रिस्पॉन्स शीटमध्ये अधिकृत उत्तरतालिका (Answer Key) आढळली नाही. केवळ उमेदवाराचे प्रतिसाद असल्याने रँक काढता येत नाही."
    }
