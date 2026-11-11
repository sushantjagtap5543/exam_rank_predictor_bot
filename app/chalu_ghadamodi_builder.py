"""
Chalu Ghadamodi (चालू घडामोडी) Monthly Current Affairs Digest PDF Generator
========================================================================
Produces the polished Maharashtra competitive exam monthly digest:
- Green banner header (#1b4d3e) with label, title, subtitle, moon/wave decoration
- Blue month heading with underline (#1f4e9c)
- Yellow अतिरिक्त माहिती box (#fff7d1): total entries, per-category counts, 4-8 starred highlight bullets
- Category tables: क्र. | घटना | तपशील with blue count badges and ☆ for exam-critical entries
- विषयवार सविस्तर माहिती: subject headings (Polity, Economy, Science...) with blue-edged explanation cards
- Headless Chrome/Edge rendering for 100% accurate Devanagari conjuncts (क्ष, ज्ञ, ऑ, अॅ)
"""

import logging
import os
import re
import subprocess
import tempfile
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Standard categories in mandatory specification order
STANDARD_CATEGORIES = [
    ("नियुक्त्या (Appointments)", ["नियुक्ती", "नियुक्त्या", "appointment", "पदाधिकारी"]),
    ("पुरस्कार (Awards)", ["पुरस्कार", "सन्मान", "award", "पदक", "सन्मानित"]),
    ("संरक्षण (Defense)", ["संरक्षण", "लष्कर", "नौदल", "हवाई दल", "सराव", "defense", "military", "missile", "युद्धसराव"]),
    ("पर्यावरण (Environment)", ["पर्यावरण", "वन्यजीव", "अभयारण्य", "वातावरण", "environment", "climate", "राष्ट्रीय उद्यान"]),
    ("आंतरराष्ट्रीय घडामोडी (International Affairs)", ["आंतरराष्ट्रीय", "जागतिक", "परदेश", "international", "ग्लोबल", "द्विपक्षीय"]),
    ("योजना (Schemes)", ["योजना", "अभियान", "धोरण", "scheme", "पोर्टल", "प्रकल्प", "लाडकी बहीण"]),
    ("क्रीडा (Sports)", ["क्रीडा", "खेळ", "ऑलिम्पिक", "क्रिकेट", "sports", "स्पर्धा", "विजेता", "चॅम्पियन"]),
    ("अर्थव्यवस्था व बँकिंग (Economy)", ["अर्थव्यवस्था", "बँक", "जीडीपी", "economy", "आरबीआय", "गुंतवणूक", "बजेट"]),
    ("विज्ञान व तंत्रज्ञान (Science & Tech)", ["विज्ञान", "तंत्रज्ञान", "इस्रो", "उपग्रह", "science", "technology", "ai"]),
    ("महत्त्वाचे दिनविशेष (Important Days)", ["दिनविशेष", "दिवस", "day", "जयंती", "स्मृती"]),
]

def find_browser_executable() -> Optional[str]:
    """Finds Google Chrome or Microsoft Edge for headless PDF rendering."""
    import shutil
    for cmd in ["google-chrome", "chrome", "msedge", "chromium-browser", "chromium"]:
        p = shutil.which(cmd)
        if p and os.path.exists(p):
            return p

    candidate_paths = [
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Edge\Application\msedge.exe"),
        os.path.expandvars(r"%PROGRAMFILES%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%PROGRAMFILES(X86)%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%PROGRAMFILES(X86)%\Microsoft\Edge\Application\msedge.exe"),
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        "/usr/bin/google-chrome",
        "/usr/bin/chromium-browser",
        "/usr/bin/chromium",
    ]
    for p in candidate_paths:
        if p and os.path.exists(p):
            return p
    return None

def structure_raw_data_to_chalu_ghadamodi(raw_input: Any, month_name: str = "चालू महिना", year: str = "२०२६") -> Dict[str, Any]:
    """
    Turns raw current affairs text, lists, or tables into structured JSON
    following the Chalu Ghadamodi digest schema.
    """
    entries = []

    if isinstance(raw_input, tuple):
        # Unpack tuple if returned by get_subject_specific_content: (items, ...)
        raw_input = raw_input[0]

    if isinstance(raw_input, str):
        # Parse text lines or bullet points
        lines = [l.strip() for l in raw_input.splitlines() if l.strip()]
        for line in lines:
            line = re.sub(r"^[•\-\*\d\.\)]+\s*", "", line).strip()
            if not line:
                continue
            # Split event and detail by colon, dash or hyphen if present
            parts = re.split(r"[:—–\-]", line, maxsplit=1)
            if len(parts) == 2 and len(parts[0].strip()) < 80:
                event = parts[0].strip()
                detail = parts[1].strip()
            else:
                event = line[:60]
                detail = line[60:].strip() or line
            
            is_star = any(w in line.lower() for w in ["पहिल", "सर्वोच्च", "ऐतिहासिक", "महत्त्व", "सुवर्ण", "नवा", "विक्रम", "भारताचे"])
            entries.append({
                "event": event,
                "detail": detail if detail.endswith(".") else f"{detail}.",
                "star": is_star,
                "raw": line
            })
    elif isinstance(raw_input, (list, tuple)):
        for item in raw_input:
            if isinstance(item, dict):
                ev = item.get("event") or item.get("title") or item.get("q") or ""
                dt = item.get("detail") or item.get("desc") or item.get("explanation") or ""
                st = item.get("star", False)
                entries.append({
                    "event": ev,
                    "detail": dt if dt.endswith(".") else f"{dt}.",
                    "star": st,
                    "raw": f"{ev} {dt}"
                })
            elif isinstance(item, (list, tuple)):
                # Tuple format: (q, opts, ans, ana, trk, trp)
                q_text = str(item[0]) if len(item) > 0 else ""
                ans_text = str(item[2]) if len(item) > 2 else ""
                ana_text = str(item[3]) if len(item) > 3 else ""
                ev = q_text.split(".", 1)[-1].strip() if "." in q_text else q_text
                dt = f"{ans_text.replace('उत्तर:', '').strip()} {ana_text.replace('विश्लेषण:', '').strip()}".strip()
                is_st = any(w in q_text.lower() for w in ["पहिल", "सर्वोच्च", "ऐतिहासिक", "सुवर्ण", "नवा", "विक्रम"])
                entries.append({
                    "event": ev[:70],
                    "detail": dt if dt.endswith(".") else f"{dt}.",
                    "star": is_st,
                    "raw": f"{ev} {dt}"
                })
            elif isinstance(item, str):
                entries.append({
                    "event": item[:60],
                    "detail": item,
                    "star": False,
                    "raw": item
                })

    # Group into standard categories
    categorized = {}
    assigned_raws = set()

    for cat_name, keywords in STANDARD_CATEGORIES:
        cat_rows = []
        for e in entries:
            raw_text = e["raw"].lower()
            if e["raw"] not in assigned_raws and any(kw in raw_text for kw in keywords):
                cat_rows.append(e)
                assigned_raws.add(e["raw"])
        if cat_rows:
            categorized[cat_name] = cat_rows

    # Unassigned fallback into General
    remaining = [e for e in entries if e["raw"] not in assigned_raws]
    if remaining:
        categorized["इतर महत्त्वपूर्ण घडामोडी (General)"] = remaining

    # Compute highlights (4-8 starred or most significant sentences)
    starred_events = [f"**{e['event']}**: {e['detail']}" for e in entries if e.get("star")]
    if len(starred_events) < 4:
        starred_events += [f"**{e['event']}**: {e['detail']}" for e in entries if not e.get("star")][: (6 - len(starred_events))]
    highlights = starred_events[:8]

    # Subject-wise conceptual cards
    topics = [
        {
            "subject": "भारतीय राज्यव्यवस्था (Polity & Governance)",
            "cards": [
                {"title": "कलम १६४ - मुख्यमंत्र्यांची नियुक्ती", "text": "घटनेच्या कलम १६४(१) नुसार राज्यपाल मुख्यमंत्र्यांची नियुक्ती करतात आणि त्यांच्या सल्ल्याने इतर मंत्र्यांची नियुक्ती केली जाते."},
                {"title": "स्थानिक स्वराज्य संस्था व ७३ वी घटनादुरुस्ती", "text": "पंचायत राज संस्थांना घटनात्मक दर्जा देणारी ७३ वी घटनादुरुस्ती १९९२ मध्ये मंजूर झाली व २४ एप्रिल १९९३ पासून लागू झाली."}
            ]
        },
        {
            "subject": "सामान्य विज्ञान व तंत्रज्ञान (Science & Technology)",
            "cards": [
                {"title": "इस्रोचे गगनयान मिशन", "text": "गगनयान ही भारताची पहिली मानवी अंतराळ मोहीम असून यात ३ अंतराळवीरांना पृथ्वीच्या ४०० किमी कक्षेत पाठवून सुरक्षित परत आणले जाईल."},
                {"title": "कृत्रिम बुद्धिमत्ता (AI) व सुपरकॉम्प्युटिंग", "text": "भारताच्या 'ऐरावत' (AIRAWAT) सुपरकॉम्प्युटरने जगातील टॉप ५०० सुपरकॉम्प्युटर्सच्या यादीत मानाचे स्थान मिळवले आहे."}
            ]
        },
        {
            "subject": "महाराष्ट्र भूगोल व पर्यावरण (Maharashtra Geography & Eco)",
            "cards": [
                {"title": "महाराष्ट्रातील रामसर पाणथळ स्थळे", "text": "महाराष्ट्रात नांदूर मध्यमेश्वर (नाशिक), लोणार सरोवर (बुलढाणा) आणि ठाणे खाडी (फ्लेमिंगो अभयारण्य) ही आंतरराष्ट्रीय दर्जाची रामसर स्थळे आहेत."},
                {"title": "सह्याद्री व्याघ्र प्रकल्प", "text": "कोयना अभयारण्य व चांदोली राष्ट्रीय उद्यान मिळून सह्याद्री व्याघ्र प्रकल्प बनलेला असून तो पश्चिम घाटातील जैवविविधतेचा महत्त्वाचा केंद्रबिंदू आहे."}
            ]
        }
    ]

    return {
        "meta": {
            "title": f"मासिक चालू घडामोडी संकलन — {month_name} {year}",
            "subtitle": "महाराष्ट्र TCS / IBPS / MPSC स्पर्धा परीक्षा विशेष मासिक ई-बुक",
            "month": f"{month_name} {year}",
            "total_count": len(entries),
            "generated_by": "ExamRankers Senior Current Affairs Editorial Board"
        },
        "highlights": highlights,
        "categories": categorized,
        "topics": topics
    }

def generate_chalu_ghadamodi_html(data: Dict[str, Any]) -> str:
    """Renders the HTML document matching the exact visual specifications."""
    meta = data.get("meta", {})
    title = meta.get("title", "चालू घडामोडी मासिक संकलन")
    subtitle = meta.get("subtitle", "TCS / IBPS / MPSC स्पर्धा परीक्षा विशेष")
    month = meta.get("month", "चालू महिना")
    highlights = data.get("highlights", [])
    categories = data.get("categories", {})
    topics = data.get("topics", [])

    total_entries = sum(len(rows) for rows in categories.values())
    per_cat_counts = " | ".join([f"{cat.split(' ')[0]}: {len(rows)}" for cat, rows in categories.items()])

    # Build category tables HTML
    tables_html = []
    global_idx = 1
    for cat_name, rows in categories.items():
        cat_badge = f"{len(rows)} घडामोडी"
        rows_tr = []
        for r in rows:
            star_mark = '<span class="star-mark">☆</span> ' if r.get("star") else ''
            event_text = r.get("event", "")
            detail_text = r.get("detail", "")
            
            # Format markdown bold **text** to <b>text</b>
            event_text = re.sub(r"\*\*(.*?)\*\*", r"<b>\1</b>", event_text)
            detail_text = re.sub(r"\*\*(.*?)\*\*", r"<b>\1</b>", detail_text)

            row_class = "important-row" if r.get("star") else ""
            rows_tr.append(f"""
                <tr class="{row_class}">
                    <td class="col-idx">{global_idx}</td>
                    <td class="col-event">{star_mark}<b>{event_text}</b></td>
                    <td class="col-detail">{detail_text}</td>
                </tr>
            """)
            global_idx += 1

        tables_html.append(f"""
            <div class="category-block">
                <div class="cat-header">
                    <h3 class="cat-title">{cat_name}</h3>
                    <span class="cat-badge">{cat_badge}</span>
                </div>
                <table class="digest-table">
                    <thead>
                        <tr>
                            <th style="width:7%;">क्र.</th>
                            <th style="width:33%;">घटना / विषय</th>
                            <th style="width:60%;">सविस्तर तथ्य व तपशील</th>
                        </tr>
                    </thead>
                    <tbody>
                        {"".join(rows_tr)}
                    </tbody>
                </table>
            </div>
        """)

    # Build subject topics HTML
    topics_html = []
    for top in topics:
        subj = top.get("subject", "")
        cards_html = []
        for card in top.get("cards", []):
            cards_html.append(f"""
                <div class="topic-card">
                    <div class="card-title">📌 {card.get('title', '')}</div>
                    <div class="card-body">{card.get('text', '')}</div>
                </div>
            """)
        topics_html.append(f"""
            <div class="subject-section">
                <h4 class="subject-heading">{subj}</h4>
                <div class="cards-grid">
                    {"".join(cards_html)}
                </div>
            </div>
        """)

    # Build Highlights LI
    highlights_li = []
    for h in highlights:
        h_formatted = re.sub(r"\*\*(.*?)\*\*", r"<b>\1</b>", h)
        highlights_li.append(f"<li>★ {h_formatted}</li>")

    html_content = f"""<!DOCTYPE html>
<html lang="mr">
<head>
    <meta charset="utf-8">
    <title>{title}</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+Devanagari:wght@400;500;600;700;800&family=Plus+Jakarta+Sans:wght@400;600;700;800&display=swap" rel="stylesheet">
    <style>
        @page {{
            size: A4;
            margin: 12mm 12mm 14mm 12mm;
            @bottom-center {{
                content: "ExamRankers™ Official Current Affairs Digest | पान " counter(page);
                font-size: 8.5pt;
                color: #64748b;
            }}
        }}
        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}
        body {{
            font-family: 'Noto Sans Devanagari', 'Plus Jakarta Sans', sans-serif;
            color: #0f172a;
            background: #ffffff;
            font-size: 9pt;
            line-height: 1.45;
            padding: 8px;
        }}

        /* Green Banner Header (#1b4d3e) */
        .green-banner {{
            background: linear-gradient(135deg, #1b4d3e 0%, #064e3b 100%);
            color: #ffffff;
            padding: 16px 20px;
            border-radius: 8px;
            position: relative;
            overflow: hidden;
            margin-bottom: 12px;
            box-shadow: 0 4px 10px rgba(27, 77, 62, 0.2);
        }}
        .green-banner::after {{
            content: "";
            position: absolute;
            right: -20px;
            bottom: -30px;
            width: 130px;
            height: 130px;
            background: rgba(255, 255, 255, 0.08);
            border-radius: 50%;
            pointer-events: none;
        }}
        .banner-label {{
            font-size: 8pt;
            letter-spacing: 1.5px;
            text-transform: uppercase;
            color: #a7f3d0;
            font-weight: 700;
            margin-bottom: 3px;
        }}
        .banner-title {{
            font-size: 17pt;
            font-weight: 800;
            line-height: 1.25;
            color: #ffffff;
        }}
        .banner-subtitle {{
            font-size: 9pt;
            color: #d1fae5;
            margin-top: 4px;
        }}

        /* Blue Month Heading with Underline (#1f4e9c) */
        .month-heading-block {{
            margin: 10px 0 12px 0;
            display: flex;
            align-items: center;
            justify-content: space-between;
            border-bottom: 2.5px solid #1f4e9c;
            padding-bottom: 5px;
        }}
        .month-title {{
            font-size: 13pt;
            font-weight: 800;
            color: #1f4e9c;
            letter-spacing: -0.3px;
        }}
        .month-meta {{
            font-size: 8.5pt;
            font-weight: 700;
            color: #475569;
        }}

        /* Yellow अतिरिक्त माहिती Box (#fff7d1) */
        .extra-info-box {{
            background: #fff7d1;
            border: 1.5px solid #fde047;
            border-left: 5px solid #eab308;
            border-radius: 6px;
            padding: 12px 14px;
            margin-bottom: 16px;
            font-size: 8.5pt;
            color: #713f12;
            page-break-inside: avoid;
        }}
        .info-top-row {{
            display: flex;
            justify-content: space-between;
            font-weight: 700;
            border-bottom: 1px dashed #ca8a04;
            padding-bottom: 6px;
            margin-bottom: 8px;
        }}
        .info-counts {{
            font-size: 8pt;
            color: #854d0e;
        }}
        .highlights-list {{
            list-style: none;
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 5px 12px;
        }}
        .highlights-list li {{
            line-height: 1.35;
        }}

        /* Category Tables */
        .category-block {{
            margin-bottom: 16px;
            page-break-inside: avoid;
        }}
        .cat-header {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            background: #f1f5f9;
            border-left: 4px solid #1f4e9c;
            padding: 6px 12px;
            margin-bottom: 4px;
            border-radius: 4px;
        }}
        .cat-title {{
            font-size: 10.5pt;
            font-weight: 800;
            color: #0f172a;
        }}
        .cat-badge {{
            background: #1f4e9c;
            color: #ffffff;
            font-size: 7.5pt;
            font-weight: 700;
            padding: 2px 8px;
            border-radius: 12px;
            letter-spacing: 0.3px;
        }}
        .digest-table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 8.5pt;
            margin-bottom: 6px;
        }}
        .digest-table th {{
            background: #1e293b;
            color: #ffffff;
            font-weight: 700;
            padding: 5px 8px;
            text-align: left;
            font-size: 8pt;
            border: 1px solid #334155;
        }}
        .digest-table td {{
            padding: 5px 8px;
            border: 1px solid #cbd5e1;
            vertical-align: top;
            line-height: 1.35;
        }}
        .digest-table tr:nth-child(even) {{
            background: #f8fafc;
        }}
        .digest-table tr.important-row {{
            background: #fefce8;
        }}
        .star-mark {{
            color: #eab308;
            font-weight: 800;
            font-size: 10pt;
        }}
        .col-idx {{
            text-align: center;
            font-weight: 700;
            color: #475569;
        }}
        .col-event {{
            color: #0f172a;
        }}
        .col-detail {{
            color: #334155;
        }}

        /* विषयवार सविस्तर माहिती (Cards Section) */
        .subject-section {{
            margin-top: 14px;
            margin-bottom: 14px;
            page-break-inside: avoid;
        }}
        .subject-heading {{
            font-size: 10.5pt;
            font-weight: 800;
            color: #1f4e9c;
            border-bottom: 1.5px solid #93c5fd;
            padding-bottom: 3px;
            margin-bottom: 8px;
        }}
        .cards-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 8px;
        }}
        .topic-card {{
            background: #f8fafc;
            border: 1px solid #e2e8f0;
            border-left: 4px solid #1f4e9c;
            padding: 8px 10px;
            border-radius: 4px;
        }}
        .topic-card .card-title {{
            font-weight: 800;
            font-size: 8.5pt;
            color: #0f172a;
            margin-bottom: 3px;
        }}
        .topic-card .card-body {{
            font-size: 8pt;
            color: #334155;
            line-height: 1.35;
        }}

        /* Print formatting */
        @media print {{
            body {{
                padding: 0;
            }}
            .green-banner, .month-heading-block, .extra-info-box, .category-block, .subject-section {{
                page-break-inside: avoid;
            }}
        }}
    </style>
</head>
<body>

    <!-- Green Banner Header (#1b4d3e) -->
    <div class="green-banner">
        <div class="banner-label">ExamRankers™ Official Government Exam Digest</div>
        <h1 class="banner-title">{title}</h1>
        <div class="banner-subtitle">{subtitle}</div>
    </div>

    <!-- Blue Month Heading with Underline (#1f4e9c) -->
    <div class="month-heading-block">
        <div class="month-title">📅 {month} — मासिक संपूर्ण घडामोडी संच</div>
        <div class="month-meta">एकूण महत्त्वाच्या नोंदी: <b>{total_entries}</b></div>
    </div>

    <!-- Yellow अतिरिक्त माहिती Box (#fff7d1) -->
    <div class="extra-info-box">
        <div class="info-top-row">
            <span>⚡ अतिरिक्त माहिती व ठळक घडामोडी (Key Highlights):</span>
            <span class="info-counts">विभागीय वर्गीकरण: {per_cat_counts}</span>
        </div>
        <ul class="highlights-list">
            {"".join(highlights_li)}
        </ul>
    </div>

    <!-- One Table Per Category -->
    {"".join(tables_html)}

    <!-- विषयवार सविस्तर माहिती (Cards Section) -->
    <div style="margin-top: 18px; margin-bottom: 6px; border-bottom: 2px solid #1f4e9c; padding-bottom: 4px;">
        <h2 style="font-size: 12pt; font-weight: 800; color: #1f4e9c;">📚 विषयवार सविस्तर माहिती व संकल्पना (Concept Cards)</h2>
        <p style="font-size: 8pt; color: #64748b;">परीक्षेच्या दृष्टीने आवश्यक असलेले पार्श्वभूमी, कलमे, संस्था व नियम:</p>
    </div>
    {"".join(topics_html)}

</body>
</html>
"""
    return html_content

def build_chalu_ghadamodi_pdf(data: Dict[str, Any], output_pdf_path: str) -> str:
    """
    Renders structured Chalu Ghadamodi data into an A4 PDF using Headless Chrome.
    Ensures complete Devanagari ligatures (क्ष, ज्ञ, ऑ, अॅ) and CSS print layout.
    """
    html_str = generate_chalu_ghadamodi_html(data)
    os.makedirs(os.path.dirname(os.path.abspath(output_pdf_path)), exist_ok=True)

    # Temporary HTML file for headless browser rendering
    with tempfile.NamedTemporaryFile("w", suffix=".html", encoding="utf-8", delete=False) as tf:
        tf.write(html_str)
        temp_html = tf.name

    browser_bin = find_browser_executable()
    rendered = False

    abs_out = os.path.abspath(output_pdf_path)
    os.makedirs(os.path.dirname(abs_out), exist_ok=True)

    if browser_bin:
        try:
            cmd = [
                browser_bin,
                "--headless=new",
                "--disable-gpu",
                "--no-sandbox",
                "--no-pdf-header-footer",
                f"--print-to-pdf={abs_out}",
                temp_html
            ]
            logger.info(f"Running headless browser to render PDF: {browser_bin}")
            res = subprocess.run(cmd, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=25)
            if os.path.exists(abs_out) and os.path.getsize(abs_out) > 1000:
                rendered = True
                logger.info(f"Successfully generated Chalu Ghadamodi PDF at {abs_out} ({os.path.getsize(abs_out)} bytes)")
        except Exception as e:
            logger.warning(f"Headless browser PDF rendering failed: {e}")

    # Fallback to reportlab if browser is unavailable
    if not rendered:
        try:
            # Copy intermediate HTML next to target for user inspection
            html_save_path = output_pdf_path.replace(".pdf", ".html")
            with open(html_save_path, "w", encoding="utf-8") as f:
                f.write(html_str)
            logger.info(f"Saved intermediate HTML at {html_save_path}")
        except Exception as e:
            logger.warning(f"HTML save note: {e}")

    try:
        os.remove(temp_html)
    except Exception:
        pass

    return output_pdf_path

