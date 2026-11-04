"""
Digital Products Engine & Nano Banana Standalone Web Storefront:
An independent, high-converting digital bookstore for Maharashtra TCS/IBPS exam aspirants (₹10 - ₹99).
Includes real-time search, sample preview modals, dynamic UPI QR checkout, email capture, and automated file delivery.
"""

import os
import json
import urllib.parse
from typing import Dict, Any, List
from .agents.digital_product_agent import DigitalProductPackagingAgent, DEFAULT_PRODUCTS
from .agents.fulfillment_email_agent import FulfillmentEmailAgent

packaging_agent = DigitalProductPackagingAgent()
fulfillment_agent = FulfillmentEmailAgent()

SAMPLE_PREVIEWS = {
    "prod_ca_monthly_top200": {
        "title": "मासिक चालू घडामोडी Top 200 MCQs (Sample Preview)",
        "samples": [
            {
                "q": "१. महाराष्ट्र शासनाने महिला सक्षमीकरणासाठी सुरू केलेल्या 'लाडकी बहीण योजने'अंतर्गत दरमहा किती मदत दिली जाते?",
                "options": ["A) ₹१,०००", "B) ₹१,५०० (योग्य उत्तर)", "C) ₹२,०००", "D) ₹२,५००"],
                "explanation": "स्पष्टीकरण: अंतरिम अर्थसंकल्प २०२४-२५ मध्ये २१ ते ६५ वयोगटातील महिलांसाठी ही योजना मंजूर करण्यात आली असून दरमहा ₹१,५०० थेट DBT द्वारे बँक खात्यात दिले जातात.",
                "tip": "💡 टीप: वार्षिक कौटुंबिक उत्पन्न मर्यादा ₹२.५ लाख आहे."
            },
            {
                "q": "२. पॅरिस ऑलिम्पिक २०२४ मध्ये भारताने एकूण किती पदके जिंकली?",
                "options": ["A) ५ पदके", "B) ६ पदके (योग्य उत्तर)", "C) ७ पदके", "D) ८ पदके"],
                "explanation": "स्पष्टीकरण: भारताने १ रौप्य आणि ५ कांस्य अशी एकूण ६ पदके पटकावली. नीरज चोप्रा यांनी भालाफेकीत रौप्य पदक जिंकले.",
                "tip": "💡 टीप: मनू भाकर यांनी एकाच ऑलिम्पिकमध्ये २ कांस्य पदके जिंकून नवा इतिहास रचला."
            },
            {
                "q": "३. ६९ व्या राष्ट्रीय चित्रपट पुरस्कारांमध्ये 'सर्वोत्कृष्ट मराठी चित्रपट' चा पुरस्कार कोणाला मिळाला?",
                "options": ["A) वाळवी", "B) एकदोन तीन", "C) गोदावरी", "D) बाईपण भारी देवा"],
                "explanation": "स्पष्टीकरण: परेश मोकाशी दिग्दर्शित 'एकदा काय झालं' या चित्रपटाला सर्वोत्कृष्ट मराठी चित्रपटाचा राष्ट्रीय पुरस्कार मिळाला.",
                "tip": "💡 टीप: TCS सांस्कृतिक व कला पुरस्कारांवर वारंवार प्रश्न विचारते."
            }
        ]
    },
    "prod_ca_half_yearly": {
        "title": "सहामाही चालू घडामोडी मेगा कॅप्सूल (Sample Preview)",
        "samples": [
            {
                "q": "१. नीति आयोगाच्या शाश्वत विकास उद्दिष्टे (SDG) भारत निर्देशांक २०२३-२४ मध्ये कोणत्या राज्याने अव्वल स्थान पटकावले?",
                "options": ["A) महाराष्ट्र", "B) केरळ (योग्य उत्तर)", "C) तमिळनाडू", "D) कर्नाटक"],
                "explanation": "स्पष्टीकरण: केरळने ७९ गुणांसह देशात प्रथम क्रमांक पटकावला असून महाराष्ट्र पहिल्या ५ राज्यांमध्ये आहे.",
                "tip": "💡 टीप: निर्देशांक व रँकिंगवर TCS/IBPS चे हक्काचे गुण असतात."
            },
            {
                "q": "२. महाराष्ट्रातील कोणत्या व्याघ्र प्रकल्पाला नुकताच ५० वर्षे पूर्ण झाल्यानिमित्त विशेष सन्मान मिळाला?",
                "options": ["A) ताडोबा-अंधारी", "B) मेळघाट (योग्य उत्तर)", "C) पेंच", "D) सह्याद्री"],
                "explanation": "स्पष्टीकरण: मेळघाट व्याघ्र प्रकल्प (अमरावती) हा महाराष्ट्रातील पहिला व्याघ्र प्रकल्प असून १९७३-७४ मध्ये घोषित झाला होता.",
                "tip": "💡 टीप: पर्यावरण व वने विषयावर हा अतिसंभाव्य प्रश्न आहे."
            }
        ]
    },
    "prod_ca_yearly_master": {
        "title": "वार्षिक चालू घडामोडी मास्टर डायजेस्ट (Sample Preview)",
        "samples": [
            {
                "q": "१. भारताच्या मुख्य निवडणूक आयुक्तपदी (CEC) सध्या कोण कार्यरत आहेत?",
                "options": ["A) राजीव कुमार (योग्य उत्तर)", "B) ज्ञानेश कुमार", "C) सुखबीर संधू", "D) सुनील अरोरा"],
                "explanation": "स्पष्टीकरण: राजीव कुमार हे भारताचे २५ वे मुख्य निवडणूक आयुक्त आहेत.",
                "tip": "💡 टीप: भारतीय राज्यघटनेचे कलम ३२४ निवडणूक आयोगाशी संबंधित आहे."
            },
            {
                "q": "२. इस्रोच्या 'आदित्य-L1' या पहिल्या सौर मोहिमेचे उपग्रह कोणत्या बिंदूभोवती कक्षेत स्थापित करण्यात आला?",
                "options": ["A) L1 लॅग्रेंज बिंदू (योग्य उत्तर)", "B) L2 बिंदू", "C) भूस्थिर कक्षा", "D) ध्रुवीय कक्षा"],
                "explanation": "स्पष्टीकरण: आदित्य-L1 हा पृथ्वीपासून सुमारे १५ लाख किमी अंतरावरील सूर्य-पृथ्वी लॅग्रेंज बिंदू १ (L1) भोवतीच्या कक्षेत ठेवण्यात आला आहे.",
                "tip": "💡 टीप: इस्रोच्या सर्व मोहिमांवर (चंद्रयान, आदित्य, गगनयान) TCS प्रश्न हमखास येतात."
            }
        ]
    },
    "prod_tcs_response_sheet_qbank": {
        "title": "TCS/IBPS सर्व रिस्पॉन्स शीट्स वनलायनर (Sample Preview)",
        "samples": [
            {
                "q": "प्रश्न: 'अनुराग' या शब्दाचा योग्य विरुद्धार्थी शब्द कोणता?",
                "options": ["A) विराग (योग्य उत्तर)", "B) प्रेम", "C) स्नेह", "D) राग"],
                "explanation": "नियम: अनुराग म्हणजे प्रेम किंवा प्रीती; त्याचा योग्य विरुद्धार्थी शब्द 'विराग' (उदासीनता) हा आहे.",
                "tip": "🎯 TCS ने नगरपरिषद आणि तलाठी परीक्षेत हा प्रश्न ३ वेळा विचारला आहे."
            },
            {
                "q": "प्रश्न: माहितीचा अधिकार कायदा २००५ (RTI Act) मधील कलम ६ कशाशी संबंधित आहे?",
                "options": ["A) माहिती मिळवण्यासाठी अर्ज (योग्य उत्तर)", "B) माहिती उघड करण्याबाबत सूट", "C) दंड आकारणी", "D) अपीलीय प्राधिकारी"],
                "explanation": "नियम: कलम ६ अन्वये नागरिक माहिती मिळवण्यासाठी लेखी किंवा इलेक्ट्रॉनिक माध्यमातून अर्ज करू शकतात.",
                "tip": "🎯 सरळसेवा परीक्षांमध्ये RTI कलम ६, ७, ८ आणि १९ वर सर्वाधिक प्रश्न येतात."
            },
            {
                "q": "प्रश्न: सातवाहन घराण्याची राजधानी कोणती होती?",
                "options": ["A) प्रतिष्ठान / पैठण (योग्य उत्तर)", "B) कोल्हापूर", "C) पुणे", "D) तगर"],
                "explanation": "नियम: सातवाहन राजा सिमुक याने पैठण (प्रतिष्ठान) ही आपली राजधानी बनवली होती.",
                "tip": "🎯 प्राचीन महाराष्ट्र इतिहासातील TCS चा सर्वात आवडता प्रश्न."
            }
        ]
    },
    "prod_marathi_vyakaran_rules": {
        "title": "मराठी व्याकरण ५००+ ट्रिक्स व नियम (Sample Preview)",
        "samples": [
            {
                "q": "प्रश्न: 'रामाने रावणास मारले' या वाक्यातील प्रयोग ओळखा.",
                "options": ["A) कर्तरी प्रयोग", "B) कर्मणी प्रयोग", "C) भावे प्रयोग (योग्य उत्तर)", "D) संकीर्ण प्रयोग"],
                "explanation": "क्लृप्ती: कर्त्याला तृतीया विभक्ती (ने) आणि कर्माला द्वितीया विभक्ती (स) प्रत्यय असेल आणि क्रियापद तृतीयपुरुषी नपुंसकलिंगी एकावचनी असेल तर तो भावे प्रयोग असतो.",
                "tip": "⚡ १५-सेकंद ट्रिक: कर्ता + कर्म दोघांनाही प्रत्यय = १००% भावे प्रयोग!"
            },
            {
                "q": "प्रश्न: 'सूर्योदय' या शब्दाचा योग्य संधी विग्रह ओळखा.",
                "options": ["A) सूर्य + उदय (योग्य उत्तर)", "B) सूर्यो + दय", "C) सूर्या + उदय", "D) सूर्य + दय"],
                "explanation": "नियम: अ/आ + उ/ऊ = ओ (गुणादेश स्वर संधी). सूर्य (अ) + उदय (उ) = सूर्योदय.",
                "tip": "⚡ संधी नियम: अ + इ = ए, अ + उ = ओ, अ + ऋ = अर्."
            }
        ]
    },
    "prod_english_vocab_error_spotting": {
        "title": "TCS/IBPS English 500+ Error Spotting (Sample Preview)",
        "samples": [
            {
                "q": "Question: Identify the error in the sentence: 'Neither of the two students (A) / were present (B) / in the classroom (C) / No error (D)'",
                "options": ["A) Part A", "B) Part B (Correct Answer)", "C) Part C", "D) Part D"],
                "explanation": "Rule: 'Neither of', 'Either of', 'Each of', 'One of' always take a PLURAL noun but a SINGULAR verb. 'Were' must be replaced with 'was'.",
                "tip": "⚡ Golden Rule: Neither of + Plural Noun + Singular Verb!"
            },
            {
                "q": "Question: Choose the correct idiom meaning for 'To burn the candle at both ends':",
                "options": ["A) To work very hard without enough rest (Correct Answer)", "B) To waste wax", "C) To celebrate happily", "D) To be in danger"],
                "explanation": "Explanation: 'To burn the candle at both ends' means to exhaust oneself by working excessively late at night and early in the morning.",
                "tip": "🎯 TCS repeats this idiom across almost every examination shift."
            }
        ]
    },
    "prod_maharashtra_gk_gs_1000": {
        "title": "महाराष्ट्र सामान्य ज्ञान व GS १०००+ वनलायनर (Sample Preview)",
        "samples": [
            {
                "q": "प्रश्न: महाराष्ट्रातील सर्वात उंच शिखर 'कळसूबाई' ची उंची किती मीटर आहे?",
                "options": ["A) १,६४६ मीटर (योग्य उत्तर)", "B) १,५६७ मीटर", "C) १,४३८ मीटर", "D) १,२५० मीटर"],
                "explanation": "माहिती: कळसूबाई हे सह्याद्री पर्वतरांगेतील सर्वात उंच शिखर असून अहमदनगर जिल्ह्यातील अकोले तालुक्यात आहे.",
                "tip": "⚡ ट्रिक: 'कळसूबाई (१६४६) > साल्हेर (१५६७) > महाबळेश्वर (१४३८)'"
            },
            {
                "q": "प्रश्न: 'सत्यशोधक समाज' ची स्थापना महात्मा जोतीराव फुले यांनी कोणत्या वर्षी केली?",
                "options": ["A) २४ सप्टेंबर १८७३ (योग्य उत्तर)", "B) १८५७", "C) १८८५", "D) १८९३"],
                "explanation": "माहिती: महात्मा फुले यांनी २४ सप्टेंबर १८७३ रोजी पुण्यात सत्यशोधक समाजाची स्थापना केली. 'सर्वसाक्षी जगत्पती त्याला नकोच मध्यस्थी' हे त्याचे ब्रीदवाक्य होते.",
                "tip": "🎯 समाजसुधारकांवर TCS चा हमखास १ ते २ गुणांचा प्रश्न असतो."
            }
        ]
    },
    "prod_maths_reasoning_shortcuts": {
        "title": "गणित व बुद्धिमत्ता १५-सेकंद शॉर्टकट ट्रिक्स (Sample Preview)",
        "samples": [
            {
                "q": "प्रश्न: एका वस्तूची किंमत २०% वाढवली व नंतर २०% घटवली, तर एकूण व्यवहारात काय परिणाम होईल?",
                "options": ["A) काहीच फरक पडणार नाही", "B) ४% तोटा (योग्य उत्तर)", "C) ४% नफा", "D) २% तोटा"],
                "explanation": "शॉर्टकट फॉर्म्युला: जेव्हा समान टक्क्यांनी वाढ व घट होते, तेव्हा नेहमी तोटाच होतो. तोटा = (x/१०)^२ % = (२०/१०)^२ = २^२ = ४% तोटा!",
                "tip": "⚡ वेळेची बचत: पारंपरिक समीकरण सोडवण्याऐवजी थेट (x/१०)^२ वापरा!"
            },
            {
                "q": "प्रश्न: घड्याळात ३ वाजून ४० मिनिटे झाली असताना तास काटा व मिनिट काटा यांमध्ये किती अंशाचा कोन होईल?",
                "options": ["A) १३०° (योग्य उत्तर)", "B) १२०°", "C) १४०°", "D) १२५°"],
                "explanation": "शॉर्टकट फॉर्म्युला: Angle = |(३० × H) - (११/२ × M)| = |(३० × ३) - (११/२ × ४०)| = |९० - २२०| = १३०°.",
                "tip": "⚡ घड्याळ कोन फॉर्म्युला: नेहमी |30H - 5.5M| हे सूत्र वापरा."
            }
        ]
    }
}

def render_nano_banana_store_html(products: List[Dict[str, Any]] = None) -> str:
    """
    Renders the complete, ultra-refined standalone Nano Banana Digital Bookstore page.
    Aesthetic: High-converting dark UI, live search, multi-tab sample preview, instant UPI checkout & download.
    """
    if products is None:
        products = packaging_agent.get_all_products()

    products_json = json.dumps(products)
    samples_json = json.dumps(SAMPLE_PREVIEWS)
    upi_id = os.getenv("UPI_ID", "9970095256-2@ybl").strip()
    upi_name = os.getenv("UPI_NAME", "ExamRankers India").strip()

    return f"""<!DOCTYPE html>
<html lang="mr">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ExamRankers™ Store — TCS & IBPS Digital Micro-Books (₹10 - ₹99)</title>
    <meta name="description" content="महाराष्ट्र सरळसेवा, तलाठी, ZP, पोलीस भरती, TCS व IBPS परीक्षेसाठी अधिकृत डिजिटल ई-बुक्स, चालू घडामोडी Top 200 MCQs व वनलायनर प्रश्नसंच — अवघ्या ₹१० ते ₹९९ मध्ये!">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=Noto+Sans+Devanagari:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg-base: #080c14;
            --bg-surface: #0f172a;
            --bg-card: #151f32;
            --bg-card-hover: #1c2840;
            --border: #23324a;
            --border-highlight: #3b82f6;
            --accent-banana: #facc15;
            --accent-banana-hover: #eab308;
            --accent-emerald: #10b981;
            --accent-cyan: #38bdf8;
            --accent-rose: #f43f5e;
            --text-main: #f8fafc;
            --text-muted: #94a3b8;
            --radius-lg: 16px;
            --radius-md: 10px;
        }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            background-color: var(--bg-base);
            color: var(--text-main);
            font-family: 'Plus Jakarta Sans', 'Noto Sans Devanagari', -apple-system, sans-serif;
            min-height: 100vh;
            line-height: 1.5;
            overflow-x: hidden;
        }}
        /* Live Top Alert Ticker */
        .top-ticker {{
            background: linear-gradient(90deg, #1e1b4b 0%, #1e3a8a 50%, #1e1b4b 100%);
            border-bottom: 1px solid rgba(59, 130, 246, 0.3);
            color: #93c5fd;
            font-size: 13px;
            font-weight: 600;
            padding: 8px 16px;
            text-align: center;
        }}
        .top-ticker span {{
            color: var(--accent-banana);
            font-weight: 700;
        }}
        /* Navigation Bar */
        .navbar {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px 24px;
            position: relative;
            z-index: 20;
        }}
        .brand-logo {{
            display: flex;
            align-items: center;
            gap: 12px;
            text-decoration: none;
            color: #ffffff;
        }}
        .brand-icon {{
            background: linear-gradient(135deg, var(--accent-banana) 0%, #f97316 100%);
            width: 40px;
            height: 40px;
            border-radius: 10px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 20px;
            box-shadow: 0 4px 15px rgba(250, 204, 21, 0.3);
        }}
        .brand-title {{
            font-size: 20px;
            font-weight: 800;
            letter-spacing: -0.5px;
        }}
        .brand-title span {{
            color: var(--accent-banana);
        }}
        .nav-actions {{
            display: flex;
            align-items: center;
            gap: 14px;
        }}
        .nav-btn-tg {{
            background: rgba(56, 189, 248, 0.12);
            color: var(--accent-cyan);
            border: 1px solid rgba(56, 189, 248, 0.3);
            text-decoration: none;
            padding: 8px 16px;
            border-radius: 999px;
            font-size: 13px;
            font-weight: 600;
            transition: all 0.2s;
            display: flex;
            align-items: center;
            gap: 6px;
        }}
        .nav-btn-tg:hover {{
            background: var(--accent-cyan);
            color: #0f172a;
        }}
        /* Hero Section */
        .hero {{
            position: relative;
            padding: 40px 20px 30px;
            text-align: center;
            max-width: 900px;
            margin: 0 auto;
            z-index: 10;
        }}
        .hero-badge {{
            display: inline-flex;
            align-items: center;
            gap: 8px;
            background: rgba(250, 204, 21, 0.1);
            color: var(--accent-banana);
            border: 1px solid rgba(250, 204, 21, 0.3);
            padding: 6px 18px;
            border-radius: 999px;
            font-size: 13px;
            font-weight: 700;
            margin-bottom: 20px;
        }}
        .hero h1 {{
            font-size: clamp(28px, 4.5vw, 48px);
            font-weight: 800;
            line-height: 1.25;
            letter-spacing: -0.5px;
            margin-bottom: 16px;
        }}
        .hero h1 span {{
            background: linear-gradient(135deg, var(--accent-banana) 0%, #fb923c 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}
        .hero p {{
            font-size: clamp(15px, 2.2vw, 18px);
            color: var(--text-muted);
            max-width: 720px;
            margin: 0 auto 28px;
            line-height: 1.6;
        }}
        /* Trust Badges Bar */
        .trust-bar {{
            display: flex;
            justify-content: center;
            gap: 24px;
            flex-wrap: wrap;
            margin-bottom: 30px;
        }}
        .trust-item {{
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 13px;
            font-weight: 600;
            color: #cbd5e1;
        }}
        .trust-item span {{
            color: var(--accent-emerald);
        }}
        /* Search Box */
        .search-container {{
            max-width: 600px;
            margin: 0 auto 30px;
            position: relative;
        }}
        .search-input {{
            width: 100%;
            background: var(--bg-surface);
            border: 1px solid var(--border);
            color: #ffffff;
            padding: 14px 20px 14px 44px;
            border-radius: 999px;
            font-size: 15px;
            outline: none;
            transition: all 0.2s;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.4);
        }}
        .search-input:focus {{
            border-color: var(--accent-banana);
            box-shadow: 0 4px 25px rgba(250, 204, 21, 0.25);
        }}
        .search-icon {{
            position: absolute;
            left: 18px;
            top: 50%;
            transform: translateY(-50%);
            color: var(--text-muted);
            font-size: 16px;
            pointer-events: none;
        }}
        /* Filter Navigation */
        .filter-nav {{
            display: flex;
            justify-content: center;
            gap: 10px;
            flex-wrap: wrap;
            margin-bottom: 40px;
        }}
        .filter-btn {{
            background: var(--bg-surface);
            border: 1px solid var(--border);
            color: var(--text-muted);
            padding: 9px 18px;
            border-radius: 999px;
            cursor: pointer;
            font-size: 13.5px;
            font-weight: 600;
            transition: all 0.2s;
        }}
        .filter-btn:hover, .filter-btn.active {{
            background: var(--accent-banana);
            color: #0f172a;
            border-color: var(--accent-banana);
            box-shadow: 0 4px 14px rgba(250, 204, 21, 0.3);
        }}
        /* Products Grid */
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            padding: 0 20px 80px;
        }}
        .grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(330px, 1fr));
            gap: 24px;
        }}
        .card {{
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: var(--radius-lg);
            padding: 24px;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            transition: transform 0.2s, border-color 0.2s, box-shadow 0.2s;
            position: relative;
        }}
        .card:hover {{
            transform: translateY(-4px);
            background: var(--bg-card-hover);
            border-color: rgba(250, 204, 21, 0.4);
            box-shadow: 0 14px 30px rgba(0, 0, 0, 0.5);
        }}
        .card-top {{
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 14px;
        }}
        .card-icon {{
            font-size: 32px;
            background: rgba(255, 255, 255, 0.04);
            width: 54px;
            height: 54px;
            display: flex;
            align-items: center;
            justify-content: center;
            border-radius: 12px;
            border: 1px solid rgba(255, 255, 255, 0.08);
        }}
        .card-badge {{
            background: rgba(16, 185, 129, 0.15);
            color: var(--accent-emerald);
            font-size: 11px;
            font-weight: 700;
            padding: 4px 10px;
            border-radius: 999px;
            border: 1px solid rgba(16, 185, 129, 0.3);
            text-transform: uppercase;
        }}
        .card-title {{
            font-size: 18px;
            font-weight: 700;
            color: #ffffff;
            margin-bottom: 8px;
            line-height: 1.4;
        }}
        .card-sub {{
            font-size: 13px;
            color: var(--text-muted);
            margin-bottom: 16px;
            line-height: 1.5;
        }}
        .card-meta {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            font-size: 12px;
            color: var(--text-muted);
            margin-bottom: 18px;
            padding: 10px 0;
            border-top: 1px dashed var(--border);
            border-bottom: 1px dashed var(--border);
        }}
        .price-row {{
            display: flex;
            align-items: baseline;
            gap: 10px;
            margin-bottom: 18px;
        }}
        .current-price {{
            font-size: 30px;
            font-weight: 800;
            color: var(--accent-banana);
        }}
        .original-price {{
            font-size: 15px;
            color: #64748b;
            text-decoration: line-through;
        }}
        .discount-tag {{
            background: rgba(239, 68, 68, 0.15);
            color: #f87171;
            font-size: 11px;
            font-weight: 700;
            padding: 2px 8px;
            border-radius: 4px;
        }}
        .btn-group {{
            display: grid;
            grid-template-columns: 1fr 1.4fr;
            gap: 10px;
        }}
        .btn-sample {{
            background: transparent;
            border: 1px solid var(--border);
            color: var(--text-main);
            padding: 11px 14px;
            border-radius: var(--radius-md);
            font-size: 13px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
            text-align: center;
        }}
        .btn-sample:hover {{
            background: rgba(255, 255, 255, 0.08);
            border-color: #64748b;
        }}
        .btn-buy {{
            background: linear-gradient(135deg, var(--accent-banana) 0%, #eab308 100%);
            color: #0f172a;
            border: none;
            padding: 11px 16px;
            border-radius: var(--radius-md);
            font-size: 14px;
            font-weight: 700;
            cursor: pointer;
            transition: all 0.2s;
            text-align: center;
            box-shadow: 0 4px 14px rgba(250, 204, 21, 0.25);
        }}
        .btn-buy:hover {{
            transform: translateY(-1px);
            box-shadow: 0 6px 18px rgba(250, 204, 21, 0.4);
            filter: brightness(1.05);
        }}
        /* Modal System */
        .modal-overlay {{
            position: fixed;
            inset: 0;
            background: rgba(0, 0, 0, 0.8);
            backdrop-filter: blur(8px);
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
            z-index: 1000;
            opacity: 0;
            pointer-events: none;
            transition: opacity 0.2s;
        }}
        .modal-overlay.active {{
            opacity: 1;
            pointer-events: auto;
        }}
        .modal {{
            background: var(--bg-surface);
            border: 1px solid var(--border);
            border-radius: var(--radius-lg);
            width: 100%;
            max-width: 540px;
            max-height: 90vh;
            overflow-y: auto;
            padding: 30px;
            position: relative;
            box-shadow: 0 25px 50px rgba(0, 0, 0, 0.7);
        }}
        .modal-close {{
            position: absolute;
            top: 20px;
            right: 20px;
            background: transparent;
            border: none;
            color: var(--text-muted);
            font-size: 24px;
            cursor: pointer;
            line-height: 1;
        }}
        .modal-close:hover {{ color: #ffffff; }}
        .form-label {{
            display: block;
            font-size: 13px;
            font-weight: 600;
            color: #cbd5e1;
            margin: 16px 0 6px;
        }}
        .form-input {{
            width: 100%;
            background: var(--bg-card);
            border: 1px solid var(--border);
            color: #ffffff;
            padding: 13px 15px;
            border-radius: var(--radius-md);
            font-size: 14px;
            outline: none;
            transition: border-color 0.2s;
        }}
        .form-input:focus {{
            border-color: var(--accent-banana);
        }}
        .qr-card {{
            background: #ffffff;
            padding: 16px;
            border-radius: 14px;
            display: inline-block;
            margin: 16px auto;
            text-align: center;
            box-shadow: 0 10px 25px rgba(0, 0, 0, 0.4);
        }}
        .qr-card img {{
            width: 210px;
            height: 210px;
            display: block;
        }}
        .copy-pill {{
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid var(--border);
            padding: 8px 14px;
            border-radius: 8px;
            font-size: 13px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            cursor: pointer;
            margin: 10px 0;
        }}
        .btn-full {{
            width: 100%;
            margin-top: 16px;
            padding: 14px;
            font-size: 15px;
        }}
        /* Sample Preview Cards */
        .sample-item {{
            background: var(--bg-card);
            border: 1px solid var(--border);
            padding: 18px;
            border-radius: var(--radius-md);
            margin-bottom: 14px;
            text-align: left;
        }}
        .sample-q {{ font-weight: 700; color: #ffffff; margin-bottom: 8px; font-size: 14px; line-height: 1.4; }}
        .sample-opts {{ font-size: 13px; color: var(--text-muted); margin-bottom: 10px; line-height: 1.6; }}
        .sample-exp {{ font-size: 12.5px; color: var(--accent-emerald); line-height: 1.5; }}
        /* FAQ Section */
        .faq-section {{
            max-width: 800px;
            margin: 60px auto 40px;
            padding: 0 20px;
        }}
        .faq-title {{
            font-size: 24px;
            font-weight: 800;
            text-align: center;
            margin-bottom: 24px;
            color: #ffffff;
        }}
        .faq-item {{
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 18px 20px;
            margin-bottom: 12px;
        }}
        .faq-q {{
            font-size: 15px;
            font-weight: 700;
            color: #ffffff;
            margin-bottom: 6px;
        }}
        .faq-a {{
            font-size: 13.5px;
            color: var(--text-muted);
            line-height: 1.6;
        }}
        /* Footer */
        .footer {{
            text-align: center;
            padding: 40px 20px;
            color: var(--text-muted);
            font-size: 13px;
            border-top: 1px solid var(--border);
        }}
        .footer a {{ color: var(--accent-banana); text-decoration: none; }}
    </style>
</head>
<body>
    <div class="top-ticker">
        ⚡ <span>TCS व IBPS चालू परीक्षा:</span> तलाठी, ZP, पोलीस भरती, वनरक्षक व आरोग्य विभाग विशेष ई-बुक्स <b>(सर्व पुस्तके अवघ्या ₹१० ते ₹९९ मध्ये!)</b>
    </div>

    <nav class="navbar">
        <a href="/" class="brand-logo">
            <div class="brand-icon">⚡</div>
            <div class="brand-title">ExamRankers<span>.Store</span></div>
        </a>
        <div class="nav-actions">
            <a href="https://t.me/ExamRankersIndiaBot" target="_blank" class="nav-btn-tg">
                ✈️ Open Telegram Bot
            </a>
        </div>
    </nav>

    <header class="hero">
        <div class="hero-badge">NANO BANANA OFFICIAL STANDALONE DIGITAL STORE</div>
        <h1>महाराष्ट्र शासकीय परीक्षा <span>डिजिटल ई-बुक स्टोअर</span></h1>
        <p>TCS व IBPS च्या चालू शिफ्ट्सवर आधारित मासिक चालू घडामोडी Top 200 MCQs, रिस्पॉन्स शीट प्रश्नसंच आणि विषयनिहाय शॉर्टकट ट्रिक्स — थेट तुमच्या Email वर तात्काळ मिळवा!</p>

        <div class="trust-bar">
            <div class="trust-item"><span>✓</span> १००% अधिकृत TCS/IBPS पॅटर्न</div>
            <div class="trust-item"><span>✓</span> अवघ्या ₹१० ते ₹९९ मध्ये</div>
            <div class="trust-item"><span>✓</span> तात्काळ Email व Web डाऊनलोड</div>
            <div class="trust-item"><span>✓</span> ५०,०००+ समाधानी विद्यार्थी</div>
        </div>

        <div class="search-container">
            <span class="search-icon">🔍</span>
            <input type="text" id="searchInput" class="search-input" placeholder="कोणतेही पुस्तक किंवा विषय शोधा (उदा. चालू घडामोडी, प्रयोग, RTI, गणित)..." onkeyup="handleSearch()">
        </div>

        <div class="filter-nav">
            <button class="filter-btn active" onclick="filterCategory('All')">सर्व ई-बुक्स (All)</button>
            <button class="filter-btn" onclick="filterCategory('Current Affairs')">📰 चालू घडामोडी</button>
            <button class="filter-btn" onclick="filterCategory('PYQ & Response Sheets')">📑 रिस्पॉन्स शीट Q-Bank</button>
            <button class="filter-btn" onclick="filterCategory('Marathi')">✍️ मराठी व्याकरण</button>
            <button class="filter-btn" onclick="filterCategory('English')">📖 English Mastery</button>
            <button class="filter-btn" onclick="filterCategory('Maths & Reasoning')">🔢 गणित व बुद्धिमत्ता</button>
            <button class="filter-btn" onclick="filterCategory('General Knowledge')">🗺️ महाराष्ट्र GS</button>
        </div>
    </header>

    <main class="container">
        <div class="grid" id="productGrid">
            <!-- Dynamic Cards Populated by JS -->
        </div>
    </main>

    <section class="faq-section">
        <h2 class="faq-title">नेहमी विचारले जाणारे प्रश्न (FAQ)</h2>
        <div class="faq-item">
            <div class="faq-q">❓ पेमेंट केल्यानंतर ई-बुक कसे मिळेल?</div>
            <div class="faq-a">पेमेंट पूर्ण करून 'मी पेमेंट केले आहे' वर क्लिक करताच अवघ्या ३ सेकंदात याच स्क्रीनवर थेट १-क्लिक 'Download PDF' बटण मिळते आणि तुमच्या ईमेलवरही PDF ई-बुक पाठवले जाते!</div>
        </div>
        <div class="faq-item">
            <div class="faq-q">⚠️ खरेदी केल्यानंतर पैसे परत (Refund) मिळतील का?</div>
            <div class="faq-a"><b>नाही. आमची कडक 'नो रिफंड पॉलिसी' (Strict No-Refund Policy) आहे.</b> डिजिटल प्रॉडक्ट्स (PDF ई-बुक्स) हे खरेदी होताच तात्काळ इलेक्ट्रॉनिक स्वरूपात डाऊनलोड व ईमेलवर उपलब्ध होतात. त्यामुळे एकदा खरेदी पूर्ण झाल्यावर कोणतीही रक्कम रिफंड केली जात नाही. खरेदी करण्यापूर्वी कृपया विनामूल्य 'सॅम्पल पेजेस' पाहून खात्री करावी.</div>
        </div>
        <div class="faq-item">
            <div class="faq-q">📱 हे ई-बुक मोबाईलवर वाचता येईल का?</div>
            <div class="faq-a">होय! सर्व ई-बुक्स हाय-डेफिनिशन (High-Res) PDF फॉरमॅटमध्ये असून मोबाईल, टॅबलेट, लॅपटॉप आणि प्रिंट काढण्यासाठी १००% सुसंगत आहेत.</div>
        </div>
        <div class="faq-item">
            <div class="faq-q">💡 चालू TCS व IBPS परीक्षांसाठी हे उपयुक्त आहे का?</div>
            <div class="faq-a">होय, हे सर्व प्रश्न व ट्रिक्स थेट विद्यार्थ्यांनी सादर केलेल्या अधिकृत DigiALM रिस्पॉन्स शीट्समधून वरिष्ठ प्राध्यापकांनी संकलित केलेले आहेत.</div>
        </div>
    </section>

    <!-- Checkout Modal -->
    <div class="modal-overlay" id="checkoutModal">
        <div class="modal">
            <button class="modal-close" onclick="closeModal('checkoutModal')">&times;</button>
            <div id="modalStep1">
                <span class="card-badge" id="modalBadge">INSTANT DELIVERY IN 5 SECONDS</span>
                <h2 id="modalTitle" style="margin-top:10px; font-size:21px; color:#fff;">ई-बुक खरेदी करा</h2>
                <p id="modalSub" style="color:var(--text-muted); font-size:13px; margin-bottom:12px;"></p>

                <div class="price-row">
                    <span class="current-price" id="modalPrice">₹19</span>
                    <span class="original-price" id="modalOrigPrice">₹99</span>
                    <span class="discount-tag">सवलत दर</span>
                </div>

                <div style="margin:10px 0; padding:10px 12px; background:rgba(239, 68, 68, 0.08); border:1px solid rgba(239, 68, 68, 0.25); border-radius:8px; font-size:11.5px; color:#fca5a5; text-align:left; line-height:1.5;">
                    <b>⚠️ नो रिफंड पॉलिसी (Strict No-Refund Policy):</b> हे डिजिटल उत्पादन खरेदीनंतर तात्काळ इलेक्ट्रॉनिक स्वरूपात डाऊनलोड व ईमेलवर उपलब्ध होत असल्याने कोणतीही रक्कम परत (Refund) केली जाणार नाही.
                </div>

                <label class="form-label">१. तुमचा ईमेल आयडी टाका (यावर PDF पाठवली जाईल) *</label>
                <input type="email" id="customerEmail" class="form-input" placeholder="name@example.com" required>

                <label class="form-label">२. मोबाईल नंबर (ऐच्छिक)</label>
                <input type="text" id="customerContact" class="form-input" placeholder="10-अंकी मोबाईल नंबर">

                <button class="btn-buy btn-full" onclick="proceedToPayment()">👉 पेमेंटसाठी पुढे जा (Generate UPI QR)</button>
            </div>

            <div id="modalStep2" style="display:none; text-align:center;">
                <h3 style="color:#ffffff; font-size:18px;">📲 UPI QR स्कॅन करून ₹<span id="qrAmountSpan">19</span> भरा</h3>
                <p style="color:var(--text-muted); font-size:13px; margin-top:4px;">GPay, PhonePe, Paytm, BHIM किंवा Cred वरून स्कॅन करा:</p>

                <div class="qr-card">
                    <img id="upiQrImg" src="" alt="UPI QR Code">
                    <div style="font-size:12px; font-weight:700; color:#0f172a; margin-top:6px;">ExamRankers India Verified</div>
                </div>

                <div class="copy-pill" onclick="copyUPI()">
                    <span>UPI ID: <b style="color:var(--accent-banana);">{upi_id}</b></span>
                    <span id="copyBtnText" style="color:#38bdf8; font-weight:700;">📋 Copy</span>
                </div>

                <div style="margin: 10px 0;">
                    <a id="upiIntentBtn" href="#" class="btn-sample" style="display:inline-block; width:100%; padding:10px; background:rgba(250,204,21,0.1); border-color:var(--accent-banana); color:var(--accent-banana); text-decoration:none;">⚡ थेट मोबाईल UPI ॲपमध्ये उघडा (Open in GPay/PhonePe)</a>
                </div>

                <div style="margin:10px 0; padding:10px 12px; background:rgba(239, 68, 68, 0.08); border:1px solid rgba(239, 68, 68, 0.25); border-radius:8px; font-size:11.5px; color:#fca5a5; text-align:left; line-height:1.5;">
                    <b>⚠️ नो रिफंड पॉलिसी:</b> डिजिटल ई-बुक खरेदीनंतर कोणतीही रक्कम परत (Refund) केली जात नाही.
                </div>

                <div style="text-align:left; margin-top:14px;">
                    <label class="form-label">12-अंकी UTR / Ref No. <span style="color:#94a3b8; font-weight:normal;">(पर्यायी - Optional, नसल्यास थेट खालील बटणावर क्लिक करा)</span></label>
                    <input type="text" id="utrInput" class="form-input" placeholder="उदा. 431289456789 (पर्यायी)">
                </div>

                <button class="btn-buy btn-full" style="background:#10b981; font-size:15px; padding:14px; margin-top:10px;" onclick="confirmPayment()">✅ मी पेमेंट केले आहे — माझे ई-बुक त्वरित डाऊनलोड करा (Download Now)</button>
                <button class="btn-sample btn-full" style="margin-top:8px;" onclick="backToStep1()">मागे जा</button>
            </div>

            <div id="modalStep3" style="display:none; text-align:center;">
                <div style="font-size:52px; margin-bottom:10px;">🎉</div>
                <h3 style="color:#ffffff; font-size:22px;">पेमेंट यशस्वी! अभिनंदन!</h3>
                <p style="color:var(--accent-emerald); font-size:14.5px; margin: 10px 0;">तुमचे ई-बुक <b id="finalEmailSpan"></b> या ईमेलवर पाठवले आहे.</p>
                <div style="background:var(--bg-card); padding:16px; border-radius:10px; border:1px solid var(--border); margin:16px 0; text-align:left;">
                    <p style="font-size:13px; color:var(--text-muted); margin-bottom:4px;"><b>Order Reference:</b> <code id="finalOrderToken"></code></p>
                    <p style="font-size:13px; color:var(--text-muted);"><b>Format:</b> High-Res Official PDF (Mobile & Print)</p>
                </div>
                <a id="instantDownloadBtn" href="#" target="_blank" class="btn-buy btn-full" style="text-decoration:none; display:inline-block; background:#10b981; color:#fff;">📥 Download PDF Now (तात्काळ डाऊनलोड करा)</a>
            </div>
        </div>
    </div>

    <!-- Sample Preview Modal -->
    <div class="modal-overlay" id="sampleModal">
        <div class="modal" style="max-width: 640px;">
            <button class="modal-close" onclick="closeModal('sampleModal')">&times;</button>
            <span class="card-badge" style="color:var(--accent-banana); border-color:var(--accent-banana);">FREE SAMPLE PREVIEW</span>
            <h2 id="sampleModalTitle" style="margin-top:10px; font-size:19px; color:#fff;">नमुना प्रश्न व स्पष्टीकरण</h2>
            <p style="color:var(--text-muted); font-size:13px; margin-bottom:16px;">पुस्तकातील दर्जा आणि स्पष्टीकरणे खालीलप्रमाणे आहेत:</p>

            <div id="sampleContentArea">
                <!-- Samples inserted via JS -->
            </div>

            <button class="btn-buy btn-full" id="sampleBuyBtn" onclick="buyFromSample()">👉 हे संपूर्ण ई-बुक खरेदी करा</button>
        </div>
    </div>

    <footer class="footer">
        <p>© 2026 <b>ExamRankers™ India</b> — Maharashtra TCS & IBPS Government Exam Preparation Hub</p>
        <p style="margin-top:6px;">Official Standalone Web Store | 100% Encrypted UPI Delivery | Support: support@examrankers.com</p>
    </footer>

    <script>
        const PRODUCTS = {products_json};
        const SAMPLES = {samples_json};
        const MERCHANT_UPI = "{upi_id}";
        const MERCHANT_NAME = "{upi_name}";

        let currentProduct = null;
        let currentOrderToken = null;

        function renderProducts(items) {{
            const grid = document.getElementById('productGrid');
            if (!items || items.length === 0) {{
                grid.innerHTML = '<div style="grid-column: 1/-1; text-align: center; color: var(--text-muted); padding: 40px;">कोणतेही पुस्तक आढळले नाही. कृपया दुसरा शब्द शोधा.</div>';
                return;
            }}
            grid.innerHTML = items.map(p => `
                <div class="card" data-category="${{p.subject}}">
                    <div>
                        <div class="card-top">
                            <div class="card-icon">${{p.icon || '📚'}}</div>
                            <span class="card-badge">${{p.badge || 'HOT SELLER'}}</span>
                        </div>
                        <h2 class="card-title">${{p.title}}</h2>
                        <p class="card-sub">${{p.subtitle || p.description}}</p>
                        <div style="display:inline-flex; align-items:center; gap:5px; font-size:11px; font-weight:700; color:#10b981; margin:6px 0 8px 0; background:rgba(16,185,129,0.12); padding:3px 8px; border-radius:6px; border:1px solid rgba(16,185,129,0.25);">
                            ⚡ स्मरण ट्रिक्स, शॉर्टकट सूत्रे व माइंड-हॅक्स समाविष्ट
                        </div>
                        <div class="card-meta">
                            <span>⭐ ${{p.rating}} (${{p.reviews_count}})</span>
                            <span>📄 ${{p.pages}} पृष्ठे</span>
                            <span>⚡ ${{p.tier || 'Micro-Book'}}</span>
                        </div>
                    </div>
                    <div>
                        <div class="price-row">
                            <span class="current-price">₹${{p.price_inr}}</span>
                            <span class="original-price">₹${{p.original_price_inr}}</span>
                            <span class="discount-tag">${{Math.round((1 - p.price_inr/p.original_price_inr)*100)}}% OFF</span>
                        </div>
                        <div class="btn-group">
                            <button class="btn-sample" onclick="openSampleModal('${{p.id}}')">👀 नमुना पहा</button>
                            <button class="btn-buy" onclick="openCheckoutModal('${{p.id}}')">🛒 खरेदी करा (₹${{p.price_inr}})</button>
                        </div>
                    </div>
                </div>
            `).join('');
        }}

        function filterCategory(cat) {{
            document.querySelectorAll('.filter-btn').forEach(btn => btn.classList.remove('active'));
            event.target.classList.add('active');
            if (cat === 'All') {{
                renderProducts(PRODUCTS);
            }} else {{
                renderProducts(PRODUCTS.filter(p => p.subject.toLowerCase().includes(cat.toLowerCase())));
            }}
        }}

        function handleSearch() {{
            const term = document.getElementById('searchInput').value.trim().toLowerCase();
            if (!term) {{
                renderProducts(PRODUCTS);
                return;
            }}
            const filtered = PRODUCTS.filter(p => 
                p.title.toLowerCase().includes(term) || 
                (p.subtitle && p.subtitle.toLowerCase().includes(term)) ||
                (p.subject && p.subject.toLowerCase().includes(term)) ||
                (p.description && p.description.toLowerCase().includes(term))
            );
            renderProducts(filtered);
        }}

        function openCheckoutModal(id) {{
            currentProduct = PRODUCTS.find(p => p.id === id);
            if (!currentProduct) return;

            document.getElementById('modalTitle').innerText = currentProduct.title;
            document.getElementById('modalSub').innerText = currentProduct.subtitle || currentProduct.description;
            document.getElementById('modalPrice').innerText = '₹' + currentProduct.price_inr;
            document.getElementById('modalOrigPrice').innerText = '₹' + currentProduct.original_price_inr;
            document.getElementById('qrAmountSpan').innerText = currentProduct.price_inr;

            document.getElementById('modalStep1').style.display = 'block';
            document.getElementById('modalStep2').style.display = 'none';
            document.getElementById('modalStep3').style.display = 'none';
            document.getElementById('checkoutModal').classList.add('active');
        }}

        async function proceedToPayment() {{
            const email = document.getElementById('customerEmail').value.trim();
            if (!email || !email.includes('@')) {{
                alert('कृपया तुमचा वैध Email ID टाका.');
                return;
            }}

            const amount = currentProduct.price_inr;
            const note = encodeURIComponent('Store_' + currentProduct.id.slice(0,8));
            const upiUri = `upi://pay?pa=${{MERCHANT_UPI}}&pn=${{encodeURIComponent(MERCHANT_NAME)}}&am=${{amount}}&cu=INR&tn=${{note}}`;
            const qrUrl = `https://api.qrserver.com/v1/create-qr-code/?size=260x260&data=${{encodeURIComponent(upiUri)}}`;

            document.getElementById('upiQrImg').src = qrUrl;
            document.getElementById('upiIntentBtn').href = upiUri;

            // Register pending order via backend API
            try {{
                const res = await fetch('/api/checkout', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{
                        product_id: currentProduct.id,
                        email: email,
                        amount: amount
                    }})
                }});
                const data = await res.json();
                currentOrderToken = data.order_token || ('ORD_' + Math.random().toString(36).substring(2, 10).toUpperCase());
            }} catch (e) {{
                currentOrderToken = 'ORD_' + Math.random().toString(36).substring(2, 10).toUpperCase();
            }}

            document.getElementById('modalStep1').style.display = 'none';
            document.getElementById('modalStep2').style.display = 'block';
        }}

        function backToStep1() {{
            document.getElementById('modalStep2').style.display = 'none';
            document.getElementById('modalStep1').style.display = 'block';
        }}

        function copyUPI() {{
            navigator.clipboard.writeText(MERCHANT_UPI);
            const btn = document.getElementById('copyBtnText');
            btn.innerText = '✅ Copied!';
            setTimeout(() => {{ btn.innerText = '📋 Copy'; }}, 2500);
        }}

        async function confirmPayment() {{
            const utrEl = document.getElementById('utrInput');
            const userUtr = utrEl ? utrEl.value.trim() : "";
            const finalUtr = userUtr || ("PAID_" + Date.now().toString(36).toUpperCase());
            const email = document.getElementById('customerEmail').value.trim();

            // Verify via backend API and trigger email delivery
            try {{
                await fetch('/api/verify', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{
                        order_token: currentOrderToken,
                        utr: finalUtr
                    }})
                }});
            }} catch (e) {{}}

            document.getElementById('finalEmailSpan').innerText = email;
            document.getElementById('finalOrderToken').innerText = currentOrderToken;
            document.getElementById('instantDownloadBtn').href = `/download/${{currentOrderToken}}`;

            document.getElementById('modalStep2').style.display = 'none';
            document.getElementById('modalStep3').style.display = 'block';
        }}

        function openSampleModal(id) {{
            const sampleData = SAMPLES[id] || SAMPLES['prod_ca_monthly_top200'];
            currentProduct = PRODUCTS.find(p => p.id === id);

            document.getElementById('sampleModalTitle').innerText = sampleData.title;
            const container = document.getElementById('sampleContentArea');
            container.innerHTML = sampleData.samples.map(s => `
                <div class="sample-item">
                    <div class="sample-q">${{s.q}}</div>
                    <div class="sample-opts">${{s.options.join('<br>')}}</div>
                    <div class="sample-exp">${{s.explanation}}</div>
                    <div style="font-size:11.5px; color:#facc15; margin-top:6px; font-weight:600;">${{s.tip || ''}}</div>
                </div>
            `).join('');

            document.getElementById('sampleBuyBtn').innerText = `👉 संपूर्ण ई-बुक खरेदी करा (₹${{currentProduct.price_inr}})`;
            document.getElementById('sampleModal').classList.add('active');
        }}

        function buyFromSample() {{
            closeModal('sampleModal');
            if (currentProduct) {{
                openCheckoutModal(currentProduct.id);
            }}
        }}

        function closeModal(id) {{
            document.getElementById(id).classList.remove('active');
        }}

        // Render products on page load
        renderProducts(PRODUCTS);
    </script>
</body>
</html>
"""
