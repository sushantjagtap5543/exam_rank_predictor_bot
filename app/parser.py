import re
import logging

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

def extract_pdf_text(path: str, max_ocr_pages: int = None) -> str:
    """
    Extracts text from all pages of a PDF document safely.
    If the document has no digital text layer (scanned or printed as images),
    automatically falls back to RapidOCR.
    """
    try:
        doc = fitz.open(path)
        pages = []
        for page in doc:
            pages.append(page.get_text("text"))
        text = "\n".join(pages)

        # If selectable text layer exists with sufficient content, return it directly
        if len(text.strip()) >= 60:
            doc.close()
            return text

        # Document is image-based / scanned -> run RapidOCR
        logger.info(f"PDF {path} has no embedded text layer. Running RapidOCR fallback...")
        ocr = get_ocr_engine()
        if not ocr:
            doc.close()
            return text

        ocr_pages = []
        total_pages = len(doc)
        limit = min(max_ocr_pages, total_pages) if max_ocr_pages else total_pages
        for i in range(limit):
            page = doc[i]
            pix = page.get_pixmap(dpi=150)
            img_bytes = pix.tobytes("png")
            result, _ = ocr(img_bytes)
            if result:
                ocr_pages.append("\n".join([line[1] for line in result]))
        doc.close()
        return "\n".join(ocr_pages)
    except Exception as e:
        logger.error(f"Error extracting PDF text from {path}: {e}")
        return ""

def recover_digialm_url_from_pdf(path: str) -> str:
    """
    Inspects PDF metadata, link annotations, and runs a quick OCR on page 0
    to recover the original DigiALM / TCS web URL if printed as a raster PDF.
    Returns the live full URL string if successfully reconstructed, else empty string.
    """
    try:
        doc = fitz.open(path)
        total_pages = len(doc)
        # 1. Embedded annotations / URI links
        for page in doc[:min(5, total_pages)]:
            for link in page.get_links():
                uri = link.get("uri", "")
                if any(k in uri.lower() for k in ["digialm.com", "touchstone", "ibpsonline", "tcsion"]):
                    doc.close()
                    return uri

        # 2. Digital text layer
        for page in doc[:min(3, total_pages)]:
            txt = page.get_text("text")
            m = re.search(r'(https?://[^\s"\'<>]+(?:digialm|touchstone|ibpsonline)[^\s"\'<>]*)', txt)
            if m:
                doc.close()
                return m.group(1)

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
                        doc.close()
                        return text_line.strip()
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
        for el in soup.find_all(class_=re.compile(r"rightAns|correct", re.I)):
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
                if re.search(pattern, text, re.I):
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
        re.I
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
        ("पशुधन पर्यवेक्षक", "पशुधन पर्यवेक्षक (Livestock Supervisor)")
    ]
    for term, formal_name in known_posts:
        if term in first_chunk:
            metadata["post_name"] = formal_name
            break

    # Candidate Name
    name_match = re.search(r"(?:Participant\s*Name|Candidate\s*Name|उमेदवाराचे\s*नाव)\s*[:\-]?\s*\n?\s*([A-Za-z\s\u0900-\u097F]+?)(?=\n|Test|Subject|Roll|Date|$)", text[:2500], re.I)
    if name_match:
        metadata["candidate_name"] = name_match.group(1).strip()[:50]

    # Roll / Registration Number
    roll_match = re.search(r"(?:Participant\s*ID|Roll\s*(?:Number|No)|Registration\s*(?:Number|No))\s*[:\-]?\s*\n?\s*([A-Za-z0-9]+)", text[:2500], re.I)
    if roll_match:
        metadata["roll_number"] = roll_match.group(1).strip()

    # Test Date
    date_match = re.search(r"(?:Test\s*Date|Exam\s*Date|दिनांक)\s*[:\-]?\s*\n?\s*([0-9/\-]+)", text[:2500], re.I)
    if date_match:
        metadata["test_date"] = date_match.group(1).strip()

    # Test Time
    time_match = re.search(r"(?:Test\s*Time|Exam\s*Time|वेळ|सत्र)\s*[:\-]?\s*\n?\s*([0-9:APMapm\s\-]+)", text[:2500], re.I)
    if time_match:
        metadata["test_time"] = time_match.group(1).strip()[:30]

    # Test Center & District Extraction
    metadata["center_name"] = "TCS iON / Official Center"
    metadata["district"] = "महाराष्ट्र (सर्वसाधारण)"
    center_match = re.search(
        r"(?:Test\s*Center\s*(?:Name)?|Center\s*(?:Name)?|Venue|परीक्षा\s*केंद्र)\s*[:\-]?\s*\n?\s*([A-Za-z0-9\s&,/\-\u0900-\u097F]+?)(?=\n|Subject|Roll|Date|$)",
        text[:3500],
        re.I
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
    section_pattern = re.compile(
        r"(?:Section\s*(?:Name)?|Subject|Part|विभाग|घटक)\s*[:\-]+\s*([A-Za-z0-9\s&,/\-\u0900-\u097F]+?)(?=\n|\r|$)",
        re.I
    )

    if re.search(r"\bQ\.\s*\d+\b", text, re.I):
        parts = re.split(r"(?=\bQ\.\s*\d+\b)", text, flags=re.I)
    elif re.search(r"\bQuestion\s*(?:No\.?|Number)?\s*\d+\b", text, re.I):
        parts = re.split(r"(?=\bQuestion\s*(?:No\.?|Number)?\s*\d+\b)", text, flags=re.I)
    else:
        parts = re.split(r"(?=\bQuestion\s*ID\s*[:\-])", text, flags=re.I)

    current_section = "General Paper"

    for block in parts:
        if not block.strip():
            continue

        sec_match = section_pattern.search(block)
        if sec_match:
            candidate_sec = sec_match.group(1).strip()
            candidate_sec = re.sub(r"\s+", " ", candidate_sec)
            if len(candidate_sec) > 3 and not candidate_sec.isdigit():
                current_section = candidate_sec[:40]

        qid_match = re.search(r"Question\s*ID\s*[:\-]+\s*(\w+)", block, re.I)
        qnum_match = re.search(r"Q\.\s*(\d+)", block, re.I)

        if not qid_match and not qnum_match:
            continue

        qid = qid_match.group(1) if qid_match else qnum_match.group(1)

        # 1. Direct Option ID match
        selected_opt = re.search(r"Answer\s*Given\s*by\s*Candidate\s*[:\-].*?Option\s*ID\s*[:\-]*\s*(\w+)", block, re.I | re.S)
        correct_opt = re.search(r"Correct\s*Answer\s*[:\-].*?Option\s*ID\s*[:\-]*\s*(\w+)", block, re.I | re.S)

        # 2. Chosen Option Number (1, 2, 3, 4 or --)
        chosen_match = re.search(r"(?:Chosen|Selected|Given|Candidate)\s*(?:Option|Answer)\s*[:\-]+\s*([1-4]|-+)", block, re.I)
        # 3. Correct Option Number directly in text (e.g. Correct Option : 2 or checkmarks)
        correct_num_match = re.search(r"(?:Correct|Right)\s*(?:Option|Answer)\s*[:\-]+\s*([1-4])\b", block, re.I)

        if not correct_num_match and not correct_opt:
            # Check for [Correct Option] from HTML or checkmark symbol (✓ / ✔ / ☑ / rightAns)
            tick_match = re.search(
                r"\b([1-4])\s*[\.\):\-](?:(?!\b[1-4]\s*[\.\):\-]).)*?(?:\[Correct Option\]|[✓✔☑]|\brightAns\b)",
                block,
                re.I | re.S
            )
            if not tick_match:
                tick_match = re.search(
                    r"(?:\[Correct Option\]|[✓✔☑]|\brightAns\b)(?:(?!\b[1-4]\s*[\.\):\-]).)*?\b([1-4])\s*[\.\):\-]",
                    block,
                    re.I | re.S
                )
            if tick_match:
                correct_num_match = tick_match

        status_match = re.search(r"Status\s*[:\-]+\s*([A-Za-z\s]+)", block, re.I)
        opt_ids = dict(re.findall(r"Option\s*([1-4])\s*ID\s*[:\-]+\s*(\w+)", block, re.I))

        given_opt_num = None
        if chosen_match:
            val = chosen_match.group(1).strip()
            if val.isdigit():
                given_opt_num = val

        correct_opt_num = None
        if correct_num_match:
            correct_opt_num = correct_num_match.group(1).strip()

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

        status = status_match.group(1).strip() if status_match else None

        clean_excerpt = re.sub(r"(?:Question|Option\s*\d|Status|Chosen|Answer\s*Given|Correct\s*Answer).*?(?:\n|$)", "", block, flags=re.I)
        clean_excerpt = re.sub(r"\s+", " ", clean_excerpt).strip()[:400]
        if not clean_excerpt:
            clean_excerpt = block[:300]

        # Extract full question text
        qtext_m = re.search(r"(?:Q\.\s*\d+|Question\s*(?:No\.?|Number)?\s*\d+)\s*\n+(.*?)(?=\n+\s*(?:Ans\b|[1-4]\s*[\.\):\-]|Question\s*Type|Question\s*ID))", block, re.S | re.I)
        if qtext_m:
            full_q_text = qtext_m.group(1).strip()
            full_q_text = re.sub(r"\s+", " ", full_q_text)
        else:
            full_q_text = clean_excerpt

        # Extract all options (1 to 4)
        options = {}
        opt_matches = re.findall(r"(?:\n|^)\s*([1-4])\s*[\.\):\-]\s*([^\n]+(?:\n(?![1-4]\s*[\.\):\-]|Question|Status|Ans|Chosen|Option\s*\d\s*ID)[^\n]+)*)", block)
        for opt_num, opt_val in opt_matches:
            cleaned_opt = re.sub(r"\[Correct Option\]|rightAns|[✓✔☑]", "", opt_val, flags=re.I).strip()
            cleaned_opt = re.sub(r"\s+", " ", cleaned_opt)
            options[str(opt_num)] = cleaned_opt

        chosen_text = options.get(str(given_opt_num), "") if given_opt_num else ""
        correct_text = options.get(str(correct_opt_num), "") if correct_opt_num else ""

        # Extract comprehension / passage if present
        comp_m = re.search(r"(?:Comprehension|उतारा)\s*[:\-]+\s*(.*?)(?=\bSubQuestion\b|\bQ\.\s*\d+\b|\bQuestion\s*ID|$)", block, re.S | re.I)
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
        "records": records
    }
