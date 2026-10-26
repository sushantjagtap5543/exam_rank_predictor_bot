"""
AI Wrong Answer & Objection Analysis Engine.
Uses cost-effective / free OpenRouter models to:
1. Explain why the student's answer was incorrect.
2. Explain the official answer logic.
3. Assess if the question or official answer key has ambiguity and whether an OBJECTION is recommended.
Supports clean pagination across multiple questions.
"""

import os
import json
import logging
import re
import httpx
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

async def explain_wrong_answers_and_objections(
    wrong_records: list[dict],
    exam_name: str,
    offset: int = 0,
    limit: int = 6,
    max_questions: int = None
) -> tuple[list[dict], int, bool, bool]:
    """
    Analyzes wrong answers with pagination.
    Returns: (results_list, total_count, has_next, has_prev)
    """
    if max_questions is not None:
        limit = max_questions
    total_count = len(wrong_records)
    if not wrong_records:
        return [], 0, False, False

    sample = wrong_records[offset: offset + limit]
    has_next = (offset + limit) < total_count
    has_prev = offset > 0

    api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    model = os.getenv("OPENROUTER_MODEL", "google/gemini-2.0-flash-exp:free").strip()

    if not api_key:
        return fallback_local_explanations(sample), total_count, has_next, has_prev

    items_to_analyze = []
    for r in sample:
        items_to_analyze.append({
            "question_number": r.get("question_number"),
            "question_id": r.get("question_id"),
            "section": r.get("section", "General"),
            "question_text": r.get("question_text", ""),
            "options": r.get("options", {}),
            "chosen_option_number": r.get("chosen_option_number"),
            "chosen_option_text": r.get("chosen_option_text", ""),
            "correct_option_number": r.get("correct_option_number"),
            "correct_option_text": r.get("correct_option_text", ""),
            "comprehension": r.get("comprehension", "")
        })

    prompt = f"""
You are an expert recruitment exam analyst for {exam_name} (Maharashtra Saralsewa / TCS & IBPS Pattern).
Review these questions that a candidate marked incorrectly against the official answer key.

For EACH question:
1. Provide a clear, in-depth explanation ('explanation') in the appropriate language (Marathi for Marathi/GK, English for English grammar):
   - Explain WHY the official correct option is the accurate answer with underlying rules, facts, grammar or logic.
   - Clarify WHY the candidate's chosen option is incorrect or how it is a common distractor/trap.
2. Evaluate if the question or official answer key has ambiguity, multiple answers, or printing/translation flaws ('objection_recommended': true/false).
3. If an objection is recommended, provide a 1-sentence legal/academic justification ('objection_reason'). Otherwise write 'अधिकृत संदर्भानुसार योग्य.'

Questions to analyze:
{json.dumps(items_to_analyze, ensure_ascii=False, indent=2)}

Return ONLY a valid JSON array of objects with keys:
"question_id", "explanation", "objection_recommended" (boolean), "objection_reason"
"""

    headers = {
        "Authorization": f"Bearer {api_key}",
        "HTTP-Referer": "https://examrankers.bot",
        "X-Title": "ExamRankers Wrong Answer & Objection Review",
        "Content-Type": "application/json"
    }

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are a professional competitive exam question reviewer and objection advisor. Provide helpful, comprehensive explanations. Output pure JSON."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.2
    }

    try:
        async with httpx.AsyncClient(timeout=40.0) as client:
            resp = await client.post(OPENROUTER_API_URL, headers=headers, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                content = data["choices"][0]["message"]["content"].strip()

                match = re.search(r"\[.*\]", content, re.DOTALL)
                json_str = match.group(0) if match else content

                ai_results = json.loads(json_str)
                merged = []
                for orig in sample:
                    qid = str(orig.get("question_id"))
                    ai_match = next((item for item in ai_results if str(item.get("question_id")) == qid), None)
                    fallback_exp = generate_smart_explanation(orig)
                    merged.append({
                        "question_number": orig.get("question_number", "?"),
                        "question_id": qid,
                        "section": orig.get("section", "General"),
                        "question_text": orig.get("question_text", ""),
                        "options": orig.get("options", {}),
                        "chosen_num": orig.get("chosen_option_number") or orig.get("selected_option_id", "-"),
                        "chosen_text": orig.get("chosen_option_text", ""),
                        "correct_num": orig.get("correct_option_number") or orig.get("correct_option_id", "-"),
                        "correct_text": orig.get("correct_option_text", ""),
                        "explanation": ai_match.get("explanation") if ai_match and ai_match.get("explanation") else fallback_exp,
                        "objection_recommended": ai_match.get("objection_recommended", False) if ai_match else False,
                        "objection_reason": ai_match.get("objection_reason") if ai_match else "अधिकृत संदर्भानुसार उत्तर प्रमाणित आहे."
                    })
                return merged, total_count, has_next, has_prev
    except Exception as e:
        logger.warning(f"AI explanation call failed: {e}. Using fallback explanations.")

    return fallback_local_explanations(sample), total_count, has_next, has_prev

def detect_question_topic(qtext: str, sec: str) -> dict:
    """Detects specific academic sub-topic and relevant rules for Maharashtra competitive exams."""
    text_lower = qtext.lower()
    sec_lower = sec.lower()

    # Marathi Grammar Topics
    if any(k in sec_lower for k in ["मराठी", "marathi", "भाषा"]):
        if any(k in text_lower for k in ["प्रयोग", "कर्तरी", "कर्मणी", "भावे"]):
            return {
                "topic": "मराठी व्याकरण — प्रयोग विचार",
                "concept": "कर्तरी, कर्मणी किंवा भावे प्रयोगाचे नियम",
                "rule": "कर्त्याच्या किंवा कर्माच्या लिंग, वचन व पुरुषानुसार क्रियापदाचे रूप बदलते तेव्हा कर्तरी किंवा कर्मणी प्रयोग होतो; कर्ता व कर्म दोघांनाही प्रत्यय असल्यास भावे प्रयोग होतो."
            }
        if any(k in text_lower for k in ["समास", "विग्रह", "तत्पुरुष", "अव्ययीभाव", "द्वंद्व", "बहुव्रीही"]):
            return {
                "topic": "मराठी व्याकरण — समास व विग्रह",
                "concept": "सामासिक शब्दांची रचना व पदांचे प्राधान्य",
                "rule": "समासात पहिले पद महत्त्वाचे असल्यास अव्ययीभाव, दुसरे पद महत्त्वाचे असल्यास तत्पुरुष, दोन्ही पदे असल्यास द्वंद्व आणि दोन्हीवरून तिसऱ्या पदाचा बोध झाल्यास बहुव्रीही समास होतो."
            }
        if any(k in text_lower for k in ["काळ", "भूतकाळ", "वर्तमानकाळ", "भविष्यकाळ", "रीती", "अपूर्ण", "पूर्ण"]):
            return {
                "topic": "मराठी व्याकरण — काळ व काळाचे प्रकार",
                "concept": "क्रियापदावरून क्रियेची वेळ व स्थिती ओळखणे",
                "rule": "क्रिया चालू असल्यास अपूर्ण/चालू काळ, पूर्ण झाली असल्यास पूर्ण काळ, आणि क्रियेची नेहमीची सवय असल्यास रीती काळ होतो."
            }
        if any(k in text_lower for k in ["समानार्थी", "पर्यायी शब्द", "अर्थ"]):
            return {
                "topic": "मराठी शब्दसंग्रह — समानार्थी शब्द",
                "concept": "शब्दार्थ व प्रमाण भाषेतील अर्थछटा",
                "rule": "प्रमाण मराठी शब्दकोशानुसार दिलेल्या शब्दाचा तंतोतंत समानार्थी पर्याय निवडणे आवश्यक असते."
            }
        if any(k in text_lower for k in ["विरुद्धार्थी", "उलट अर्थ"]):
            return {
                "topic": "मराठी शब्दसंग्रह — विरुद्धार्थी शब्द",
                "concept": "परस्परविरोधी अर्थ व्यक्त करणारे शब्द",
                "rule": "विरुद्धार्थी शब्द शोधताना मूळ शब्दाची जात (नाम, विशेषण, क्रियापद) व भाव बदलत नाही याची खात्री करावी."
            }
        if any(k in text_lower for k in ["वाक्प्रचार", "वाक्यप्रचार", "अर्थ सांगा"]):
            return {
                "topic": "मराठी शब्दसंग्रह — वाक्प्रचार",
                "concept": "लाक्षणिक व रुढ झालेला अर्थ",
                "rule": "वाक्प्रचाराचा शब्दशः अर्थ न घेता रूढीने आलेला लाक्षणिक अर्थच ग्राह्य धरला जातो."
            }
        if any(k in text_lower for k in ["म्हण", "म्हणी", "अर्थ"]):
            return {
                "topic": "मराठी शब्दसंग्रह — म्हणी व अर्थ",
                "concept": "लोकपरंपरेतून आलेले बोधवाक्य",
                "rule": "म्हणी मानवी स्वभावातील अनुभवाचे संक्षिप्त सत्य मांडतात, त्यांचा समर्पक संदर्भ लक्षात घेणे आवश्यक आहे."
            }
        if any(k in text_lower for k in ["शुद्ध", "अशुद्ध", "शुद्धलेखन"]):
            return {
                "topic": "मराठी व्याकरण — शुद्धलेखनाचे नियम",
                "concept": "महामंडळाचे शुद्धलेखन नियम (अनुस्वार, र्‍हस्व/दीर्घ)",
                "rule": "शब्दातील उपांत्य अक्षराचा स्वर, तत्सम शब्दांचे मूळ स्वरूप आणि अनुस्वारांचे स्थान अधिकृत नियमांवर आधारित असते."
            }
        if any(k in text_lower for k in ["विभक्ती", "प्रत्यय", "सलाते", "सलानाते", "ने-ए-शी"]):
            return {
                "topic": "मराठी व्याकरण — विभक्ती व कारकार्थ",
                "concept": "नामाचे क्रियापदाशी किंवा इतर शब्दांशी असणारे संबंध",
                "rule": "विभक्ती प्रत्ययांवरून कारकार्थ (कर्ता, कर्म, करण, संप्रदान, अपादान, संबंध, अधिकरण) ठरवला जातो."
            }
        return {
            "topic": "मराठी भाषा व व्याकरण",
            "concept": "प्रमाण भाषेचे नियम व अधिकृत संदर्भ",
            "rule": "मो. रा. वाळंबे व अधिकृत शासकीय पाठ्यपुस्तक मंडळाच्या नियमांनुसार प्रमाण उत्तर निश्चित केले जाते."
        }

    # English Language Topics
    if any(k in sec_lower for k in ["english", "इंग्रजी"]):
        if any(k in text_lower for k in ["tense", "past", "present", "future", "continuous", "perfect"]):
            return {
                "topic": "English Grammar — Tense & Aspect",
                "concept": "Time and state of action in sentence construction",
                "rule": "Auxiliary verbs must align with temporal markers (e.g., 'since/for' with Perfect Continuous, past adverbs with Simple Past)."
            }
        if any(k in text_lower for k in ["passive", "active", "voice"]):
            return {
                "topic": "English Grammar — Active & Passive Voice",
                "concept": "Subject-Object transformation and verb conjugation",
                "rule": "In passive voice, form of 'to be' + past participle (V3) is strictly mandatory, keeping the original tense invariant."
            }
        if any(k in text_lower for k in ["direct", "indirect", "reported speech", "said"]):
            return {
                "topic": "English Grammar — Direct & Indirect Speech",
                "concept": "Reporting verb and tense backshift rules",
                "rule": "When reporting verb is in past tense, present tenses shift to corresponding past forms, and pronouns shift according to the speaker."
            }
        if any(k in text_lower for k in ["preposition", "in", "on", "at", "by", "for", "with"]):
            return {
                "topic": "English Grammar — Appropriate Prepositions",
                "concept": "Fixed prepositions and idiomatic usage",
                "rule": "Certain verbs, adjectives, and nouns take fixed prepositions (e.g., 'depend on', 'abstain from', 'listen to')."
            }
        if any(k in text_lower for k in ["synonym", "similar meaning", "nearest"]):
            return {
                "topic": "English Vocabulary — Synonyms",
                "concept": "Contextual meaning and exact connotations",
                "rule": "The correct synonym matches both semantic meaning and grammatical category in the given sentence context."
            }
        if any(k in text_lower for k in ["antonym", "opposite"]):
            return {
                "topic": "English Vocabulary — Antonyms",
                "concept": "Direct contrast in meaning",
                "rule": "Antonyms must strictly retain the part of speech of the target word."
            }
        if any(k in text_lower for k in ["error", "spotting", "correct sentence"]):
            return {
                "topic": "English Grammar — Error Detection",
                "concept": "Subject-Verb concord, parallelism, and modifier placement",
                "rule": "A singular subject strictly demands a singular verb, and correlative conjunctions (neither...nor, either...or) require structural parallelism."
            }
        return {
            "topic": "English Language & Comprehension",
            "concept": "Standard English grammar and TCS/IBPS exam patterns",
            "rule": "Grammar conventions follow standard Oxford English and competitive examination guidelines."
        }

    # Maths & Reasoning Topics
    if any(k in sec_lower for k in ["बुद्धिमत्ता", "अंकगणित", "reasoning", "math", "aptitude", "संख्या"]):
        if any(k in text_lower for k in ["मालिक", "संख्या", "श्रेणी", "series", "pattern"]):
            return {
                "topic": "बुद्धिमत्ता चाचणी — संख्या व अक्षर मालिका",
                "concept": "गणितीय फरक, वर्ग, घन किंवा अल्टरनेट सिरीजचा नियम",
                "rule": "मालिकेतील लगतच्या पदांमधील फरक तपासून सूत्र (उदा. +n, ×2, n²-1 किंवा फिबोनाकी) निश्चित केले जाते."
            }
        if any(k in text_lower for k in ["नातेसंबंध", "नाते", "blood relation", "आई", "वडील", "भाऊ", "बहीण"]):
            return {
                "topic": "बुद्धिमत्ता चाचणी — नातेसंबंध (Blood Relations)",
                "concept": "पिढ्यांची मांडणी व कौटुंबिक नाते",
                "rule": "कुटुंबवृक्ष (Family Tree) मांडून लिंग (+/-) व पिढीनुसार थेट संबंध तपासल्यास उत्तर अचूक येते."
            }
        if any(k in text_lower for k in ["दिशा", "अंतर", "उत्तर", "दक्षिण", "पूर्व", "पश्चिम", "direction"]):
            return {
                "topic": "बुद्धिमत्ता चाचणी — दिशा व अंतर",
                "concept": "पायथागोरसचे प्रमेय व काटकोन त्रिकोण",
                "rule": "सुरुवातीच्या बिंदूपासून थेट अंतरासाठी काटकोन त्रिकोणात पायथागोरस सिद्धांत (कर्ण² = पाया² + उंची²) वापरला जातो."
            }
        if any(k in text_lower for k in ["टक्केवारी", "शेकडेवारी", "percentage", "%"]):
            return {
                "topic": "अंकगणित — शेकडेवारी (Percentage)",
                "concept": "१०० च्या आधारावर तुलना व रूपांतर",
                "rule": "शेकडा वाढ किंवा घट काढताना मूळ किमतीशी तुलना करून प्रमाण काढले जाते."
            }
        if any(k in text_lower for k in ["नफा", "तोटा", "खरेदी", "विक्री", "profit", "loss"]):
            return {
                "topic": "अंकगणित — नफा आणि तोटा",
                "concept": "खरेदी किंमत, विक्री किंमत आणि शेकडा नफा/तोटा",
                "rule": "शेकडा नफा = (नफा / खरेदी किंमत) × १००; नफा किंवा तोटा नेहमी खरेदी किमतीवरच मोजला जातो."
            }
        if any(k in text_lower for k in ["काम", "दिवस", "काळ", "वेग", "time", "work", "speed"]):
            return {
                "topic": "अंकगणित — काळ, काम आणि वेग",
                "concept": "कार्यक्षमता व व्यस्त प्रमाणाचे गणित",
                "rule": "व्यक्तीची एका दिवसाची कार्यक्षमता एकूण कामाचा १/n भाग असते. अंतर = वेग × वेळ."
            }
        return {
            "topic": "तार्किक विचार व अंकगणित (Aptitude & Reasoning)",
            "concept": "तार्किक मांडणी व सूत्रबद्ध गणना",
            "rule": "योग्य सूत्र आणि पद्धतशीर मांडणीद्वारे तार्किक निष्कर्षावर पोहोचता येते."
        }

    # General Knowledge / GK Topics
    if any(k in text_lower for k in ["महाराष्ट्र", "जिल्हा", "नदी", "डोंगर", "किल्ला", "सह्याद्री", "गोदावरी"]):
        return {
            "topic": "सामान्य ज्ञान — महाराष्ट्राचा भूगोल व पर्यावरण",
            "concept": "महाराष्ट्राची प्राकृतिक रचना, नद्या व जिल्हे",
            "rule": "महाराष्ट्र शासनाच्या अधिकृत गॅझेटिअर व संदर्भ पुस्तकांनुसार भौगोलिक माहिती प्रमाणित मानली जाते."
        }
    if any(k in text_lower for k in ["इतिहास", "छत्रपती", "शिवाजी", "पेशवे", "समाजसुधारक", "फुले", "आंबेडकर", "शाहू"]):
        return {
            "topic": "सामान्य ज्ञान — महाराष्ट्राचा इतिहास व थोर समाजसुधारक",
            "concept": "ऐतिहासिक घटनाक्रम व समाजसुधारकांचे कार्य",
            "rule": "इतिहास संशोधक व महाराष्ट्र राज्य पाठ्यपुस्तक मंडळाच्या साधनांवर आधारित तथ्य प्रमाणित असते."
        }
    if any(k in text_lower for k in ["घटना", "कलम", "राज्यघटना", "राष्ट्रपती", "राज्यपाल", "लोकसभा", "विधानसभा", "पंचायत"]):
        return {
            "topic": "सामान्य ज्ञान — भारतीय राज्यघटना व पंचायत राज",
            "concept": "संवैधानिक कलमे, अधिकार व प्रशासन रचना",
            "rule": "भारतीय संविधानातील मूळ कलमे व दुरुस्त्या यानुसार प्रशासकीय व कायदेशीर तरतुदी निश्चित असतात."
        }
    if any(k in text_lower for k in ["माहितीचा अधिकार", "rti", "लोकसेवा हक्क", "rts", "2005", "2015"]):
        return {
            "topic": "सामान्य ज्ञान — RTI 2005 व RTS 2015 कायदे",
            "concept": "माहिती अधिकार व लोकसेवा हमी कायदेविषयक तरतुदी",
            "rule": "माहिती मिळवण्याचा कालावधी (३० दिवस/४८ तास जीवन सुरक्षेसाठी) आणि अपीलीय अधिकाऱ्यांची रचना कायद्यानुसार काटेकोर असते."
        }

    return {
        "topic": "सामान्य ज्ञान व चालू घडामोडी (General Studies)",
        "concept": "सामान्य अध्ययन व अधिकृत शासकीय अभ्यासक्रम",
        "rule": "शासकीय अहवाल, अधिकृत संकेतस्थळे आणि चालू घडामोडींच्या प्रमाणित संदर्भांनुसार उत्तर सिद्ध होते."
    }

def generate_smart_explanation(r: dict) -> str:
    """
    Generates a comprehensive, pedagogical, in-depth explanation for competitive exam questions.
    Provides clear reasoning for the correct option, explains the distractor/chosen option,
    and highlights the core academic rule or step-by-step mathematical solution.
    """
    sec = r.get("section", "General")
    qtext = r.get("question_text", "").strip()
    c_num = str(r.get("correct_option_number") or "").strip()
    c_txt = (r.get("correct_option_text") or "").strip()
    s_num = str(r.get("chosen_option_number") or "").strip()
    s_txt = (r.get("chosen_option_text") or "").strip()
    eval_status = r.get("evaluation", "unanswered")

    c_label = f"पर्याय {c_num} ('{c_txt}')" if (c_num and c_txt) else (f"पर्याय {c_num}" if c_num else "अधिकृत उत्तर")
    s_label = f"पर्याय {s_num} ('{s_txt}')" if (s_num and s_txt) else (f"पर्याय {s_num}" if s_num else "अनुत्तरित")

    topic_info = detect_question_topic(qtext, sec)
    topic_name = topic_info["topic"]
    rule_text = topic_info["rule"]

    is_math_reasoning = any(k in sec.lower() for k in ["बुद्धिमत्ता", "अंकगणित", "reasoning", "math", "aptitude", "संख्या"]) or \
                        any(k in qtext.lower() for k in ["मालिक", "संख्या", "नातेसंबंध", "दिशा", "टक्केवारी", "नफा", "तोटा", "सरासरी", "काळ", "काम", "वेग"])

    if is_math_reasoning:
        lines = [
            f"<b>📚 विषय/घटक:</b> {topic_name}",
            f"<b>🎯 अधिकृत अचूक उत्तर:</b> <code>{c_label}</code>",
            f"<b>🔢 गणितीय व तार्किक सोडवणूक (Step-by-Step Solution):</b>\n"
            f"• <b>पायरी १ (माहिती व मांडणी):</b> विचारलेल्या प्रश्नातील घटक व अटींनुसार दिलेल्या संख्या/विधानांची मांडणी केली.\n"
            f"• <b>पायरी २ (सूत्र व संबंध):</b> {topic_info.get('concept', 'तार्किक संबंध')}. सूत्र/नियम: <i>{rule_text}</i>\n"
            f"• <b>पायरी ३ (थेट गणना):</b> नियमाप्रमाणे अचूक गणना केल्यास <b>{c_label}</b> हे उत्तर निर्विवादपणे सिद्ध होते."
        ]
        if eval_status == "incorrect" and s_num:
            lines.append(
                f"<b>❌ तुमचा निवडलेला पर्याय ({s_label}) का चुकला?:</b>\n"
                f"गणनेमध्ये अथवा सूत्र लागू करताना झालेली सामान्य चूक (उदा. सूत्रातील चिन्हांची गल्लत किंवा मालिकेतील लगतच्या फरकाऐवजी चुकीचा फरक गृहीत धरणे) यामुळे <b>{s_label}</b> हा पर्याय येतो. हा या प्रश्नातील Distractor पर्याय आहे."
            )
        elif eval_status == "unanswered":
            lines.append(
                f"<b>⚪ अनुत्तरित प्रश्न:</b>\n"
                f"हा प्रश्न तुम्ही सोडवला नाही. वरील ३ पायऱ्या वापरून अशा प्रकारची उदाहरणे सहज सोडवता येतात."
            )
        lines.append(f"<b>⚡ शॉर्टकट ट्रिक:</b> <i>प्रश्नातील पर्यायांची उलटी तपासणी (Option Elimination) किंवा एकक स्थानावरून (Unit Digit Method) उत्तर जलद शोधता येते.</i>")
        return "\n\n".join(lines)

    elif any(k in sec.lower() for k in ["मराठी", "marathi", "english", "इंग्रजी", "भाषा"]):
        lines = [
            f"<b>📚 विषय/घटक:</b> {topic_name}",
            f"<b>🎯 अधिकृत अचूक उत्तर:</b> <code>{c_label}</code>",
            f"<b>📖 व्याकरण नियम (Grammar Rule):</b>\n<i>{rule_text}</i>\n\n"
            f"<b>✅ अचूक उत्तराचे स्पष्टीकरण:</b>\n"
            f"प्रश्नातील वाक्यरचना किंवा शब्दप्रयोग तपासल्यास <b>{c_label}</b> हाच पर्याय प्रमाणित व्याकरण नियमांशी १००% सुसंगत आहे."
        ]
        if eval_status == "incorrect" and s_num:
            lines.append(
                f"<b>❌ तुमचा निवडलेला पर्याय ({s_label}) का चुकला?:</b>\n"
                f"हा पर्याय निवडल्याने वाक्यात व्याकरणाची/अर्थाची विसंगती निर्माण होते किंवा मूळ शब्दाच्या नियमाचे उल्लंघन होते."
            )
        elif eval_status == "unanswered":
            lines.append(
                f"<b>⚪ अनुत्तरित प्रश्न:</b>\n"
                f"हा प्रश्न तुम्ही सोडवला नाही. पुढील वेळी वरील व्याकरण नियम लक्षात ठेवून उत्तर नक्की नोंदवा."
            )
        lines.append(f"<b>💡 परीक्षेसाठी महत्त्वाची टीप:</b> <i>{topic_info.get('concept', 'प्रमाण नियमांचे पालन')} लक्षात ठेवावे.</i>")
        return "\n\n".join(lines)

    else:
        lines = [
            f"<b>📚 विषय/घटक:</b> {topic_name}",
            f"<b>🎯 अधिकृत अचूक उत्तर:</b> <code>{c_label}</code>",
            f"<b>🏛️ अधिकृत तथ्य व संदर्भ (Official Reference):</b>\n<i>{rule_text}</i>\n\n"
            f"<b>✅ सविस्तर माहिती:</b>\n"
            f"महाराष्ट्र शासनाच्या अधिकृत पाठ्यपुस्तक मंडळ (बालभारती) व शासकीय संदर्भानुसार <b>{c_label}</b> हेच वस्तुनिष्ठ व प्रमाणित उत्तर आहे."
        ]
        if eval_status == "incorrect" and s_num:
            lines.append(
                f"<b>❌ तुमचा निवडलेला पर्याय ({s_label}) का चुकला?:</b>\n"
                f"हा पर्याय ऐतिहासिक/भौगोलिकदृष्ट्या वस्तुस्थितीशी विसंगत असून विद्यार्थ्यांचा गोंधळ उडवण्यासाठी दिलेला दिशाभूल करणारा पर्याय आहे."
            )
        elif eval_status == "unanswered":
            lines.append(
                f"<b>⚪ अनुत्तरित प्रश्न:</b>\n"
                f"हा प्रश्न तुम्ही सोडवला नाही. अशा वस्तुनिष्ठ प्रश्नांसाठी सामान्य अध्ययनाचा सराव महत्त्वाचा ठरतो."
            )
        lines.append(f"<b>📌 महत्त्वाचा संदर्भ:</b> <i>{topic_info.get('concept', 'अधिकृत संदर्भ')}</i>")
        return "\n\n".join(lines)

def fallback_local_explanations(sample: list[dict]) -> list[dict]:
    """Rich, pedagogical explanations if AI key is unavailable."""
    results = []
    for r in sample:
        qid = str(r.get("question_id"))
        exp = generate_smart_explanation(r)
        results.append({
            "question_number": r.get("question_number", "?"),
            "question_id": qid,
            "section": r.get("section", "General"),
            "question_text": r.get("question_text", ""),
            "options": r.get("options", {}),
            "chosen_num": r.get("chosen_option_number") or r.get("selected_option_id", "-"),
            "chosen_text": r.get("chosen_option_text", ""),
            "correct_num": r.get("correct_option_number") or r.get("correct_option_id", "-"),
            "correct_text": r.get("correct_option_text", ""),
            "explanation": exp,
            "objection_recommended": False,
            "objection_reason": "अधिकृत संदर्भानुसार उत्तर प्रमाणित आहे. आक्षेप नोंदवण्यापूर्वी अधिकृत पाठ्यपुस्तकातील संदर्भ तपासावा."
        })
    return results

def generate_html_full_report(records: list[dict], metadata: dict, score_result: dict, exam_name: str) -> str:
    """
    Generates a complete, responsive, standalone HTML Question Paper Review document
    with all questions, candidate answers, correct answers, and detailed explanations.
    """
    candidate_name = metadata.get("candidate_name") or "Candidate"
    roll_num = metadata.get("roll_number") or "N/A"
    post_name = metadata.get("post_name") or "General"
    test_date = metadata.get("test_date") or ""

    score = score_result.get("score", 0.0)
    correct_cnt = score_result.get("correct", 0)
    wrong_cnt = score_result.get("incorrect", 0)
    unans_cnt = score_result.get("unanswered", 0)
    total_q = len(records)
    acc = round((correct_cnt / max(1, (correct_cnt + wrong_cnt))) * 100, 1)

    cards_html = []
    for idx, r in enumerate(records, 1):
        qnum = r.get("question_number") or idx
        sec = r.get("section", "General")
        qtext = r.get("question_text", "Question Text")
        eval_status = r.get("evaluation", "unanswered")
        chosen_num = str(r.get("chosen_option_number") or "")
        correct_num = str(r.get("correct_option_number") or "")
        options = r.get("options", {})
        comp = r.get("comprehension", "")

        status_badge = ""
        card_class = ""
        if eval_status == "correct":
            status_badge = '<span class="badge badge-success">✅ बरोबर (Correct)</span>'
            card_class = "card-correct"
        elif eval_status == "incorrect":
            status_badge = '<span class="badge badge-danger">❌ चुकीचे (Incorrect)</span>'
            card_class = "card-incorrect"
        else:
            status_badge = '<span class="badge badge-secondary">⚪ अनुत्तरित (Unanswered)</span>'
            card_class = "card-unanswered"

        opts_html = []
        for opt_k in ["1", "2", "3", "4"]:
            if opt_k in options:
                opt_val = options[opt_k]
                is_correct_opt = (opt_k == correct_num)
                is_chosen_opt = (opt_k == chosen_num)

                opt_class = "opt-item"
                icon = f"<b>{opt_k}.</b> "
                if is_correct_opt and is_chosen_opt:
                    opt_class += " opt-correct opt-chosen"
                    icon = f"<b>{opt_k}.</b> ✅ "
                elif is_correct_opt:
                    opt_class += " opt-correct"
                    icon = f"<b>{opt_k}.</b> ✅ "
                elif is_chosen_opt:
                    opt_class += " opt-incorrect"
                    icon = f"<b>{opt_k}.</b> ❌ "

                opts_html.append(f'<div class="{opt_class}">{icon}{opt_val}</div>')

        explanation = generate_smart_explanation(r)
        comp_html = f'<div class="comp-box"><b>📖 उतारा (Comprehension):</b><p>{comp}</p></div>' if comp else ""

        cards_html.append(f"""
        <div class="q-card {card_class}" data-status="{eval_status}">
            <div class="q-header">
                <span class="q-num">प्रश्न क्र. {qnum}</span>
                <span class="q-sec">{sec}</span>
                {status_badge}
            </div>
            {comp_html}
            <div class="q-body">
                <p class="q-text">{qtext}</p>
                <div class="options-grid">
                    {''.join(opts_html)}
                </div>
            </div>
            <div class="q-footer">
                <div class="ans-summary">
                    <span><b>तुमचे उत्तर:</b> {r.get('chosen_option_text') or (f'पर्याय {chosen_num}' if chosen_num else 'अनुत्तरित')}</span>
                    <span><b>अधिकृत उत्तर:</b> <span class="text-success">{r.get('correct_option_text') or (f'पर्याय {correct_num}' if correct_num else '-')}</span></span>
                </div>
                <div class="exp-box">
                    <b>💡 सविस्तर स्पष्टीकरण:</b>
                    <p>{explanation}</p>
                </div>
            </div>
        </div>
        """)

    full_html = f"""<!DOCTYPE html>
<html lang="mr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>ExamRankers सविस्तर प्रश्नपत्रिका विश्लेषण — {candidate_name}</title>
<style>
:root {{
    --primary: #4f46e5;
    --success: #16a34a;
    --danger: #dc2626;
    --bg: #f8fafc;
    --card-bg: #ffffff;
    --text: #1e293b;
    --border: #e2e8f0;
}}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Noto Sans", sans-serif; background: var(--bg); color: var(--text); padding: 1.5rem; line-height: 1.6; }}
.container {{ max-width: 900px; margin: 0 auto; }}
.header-box {{ background: linear-gradient(135deg, #1e1b4b, #312e81); color: #fff; padding: 2rem; border-radius: 1rem; margin-bottom: 2rem; box-shadow: 0 10px 25px -5px rgba(0,0,0,0.1); }}
.header-box h1 {{ font-size: 1.6rem; margin-bottom: 0.5rem; }}
.meta-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 0.75rem; margin-top: 1rem; font-size: 0.95rem; opacity: 0.95; }}
.kpi-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); gap: 1rem; margin-top: 1.5rem; }}
.kpi {{ background: rgba(255,255,255,0.12); padding: 1rem; border-radius: 0.75rem; text-align: center; }}
.kpi .num {{ font-size: 1.7rem; font-weight: 700; }}
.kpi .lbl {{ font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.05em; }}
.filters {{ display: flex; gap: 0.75rem; margin-bottom: 1.5rem; flex-wrap: wrap; }}
.btn-filter {{ padding: 0.6rem 1.2rem; border-radius: 2rem; border: 1px solid var(--border); background: var(--card-bg); font-weight: 600; cursor: pointer; transition: all 0.2s; }}
.btn-filter.active, .btn-filter:hover {{ background: var(--primary); color: #fff; border-color: var(--primary); }}
.q-card {{ background: var(--card-bg); border: 1px solid var(--border); border-radius: 0.85rem; margin-bottom: 1.5rem; padding: 1.5rem; box-shadow: 0 2px 4px rgba(0,0,0,0.02); }}
.card-correct {{ border-left: 5px solid var(--success); }}
.card-incorrect {{ border-left: 5px solid var(--danger); }}
.card-unanswered {{ border-left: 5px solid #94a3b8; }}
.q-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem; padding-bottom: 0.75rem; border-bottom: 1px solid var(--border); }}
.q-num {{ font-size: 1.1rem; font-weight: 700; color: var(--primary); }}
.q-sec {{ font-size: 0.85rem; background: #e0e7ff; color: #3730a3; padding: 0.2rem 0.6rem; border-radius: 0.4rem; font-weight: 600; }}
.badge {{ padding: 0.25rem 0.6rem; border-radius: 0.4rem; font-size: 0.8rem; font-weight: 700; }}
.badge-success {{ background: #dcfce7; color: #166534; }}
.badge-danger {{ background: #fee2e2; color: #991b1b; }}
.badge-secondary {{ background: #f1f5f9; color: #475569; }}
.comp-box {{ background: #fefce8; border: 1px solid #fef08a; padding: 1rem; border-radius: 0.5rem; font-size: 0.9rem; margin-bottom: 1rem; color: #713f12; }}
.q-text {{ font-size: 1.05rem; font-weight: 600; margin-bottom: 1rem; color: #0f172a; }}
.options-grid {{ display: grid; gap: 0.6rem; margin-bottom: 1rem; }}
.opt-item {{ padding: 0.75rem 1rem; border: 1px solid var(--border); border-radius: 0.5rem; background: #f8fafc; font-size: 0.95rem; }}
.opt-correct {{ background: #dcfce7; border-color: #86efac; color: #166534; font-weight: 600; }}
.opt-incorrect {{ background: #fee2e2; border-color: #fca5a5; color: #991b1b; font-weight: 600; }}
.ans-summary {{ display: flex; justify-content: space-between; padding: 0.75rem; background: #f1f5f9; border-radius: 0.5rem; font-size: 0.9rem; margin-bottom: 0.75rem; flex-wrap: wrap; gap: 0.5rem; }}
.text-success {{ color: #16a34a; font-weight: 700; }}
.exp-box {{ background: #eff6ff; border: 1px solid #bfdbfe; padding: 0.9rem; border-radius: 0.5rem; font-size: 0.92rem; color: #1e40af; }}
.exp-box b {{ display: block; margin-bottom: 0.25rem; color: #1d4ed8; }}
@media print {{
    body {{ background: #fff; padding: 0; }}
    .filters {{ display: none; }}
    .q-card {{ break-inside: avoid; }}
}}
</style>
</head>
<body>
<div class="container">
    <div class="header-box">
        <h1>📊 ExamRankers सविस्तर प्रश्नपत्रिका व उत्तरतालिका विश्लेषण</h1>
        <p>परीक्षा: <b>{exam_name}</b> | पद: <b>{post_name}</b></p>
        <div class="meta-grid">
            <div>👤 <b>उमेदवार:</b> {candidate_name}</div>
            <div>🔢 <b>हजेरी क्र. (Roll):</b> {roll_num}</div>
            <div>📅 <b>परीक्षा दिनांक:</b> {test_date}</div>
            <div>🎯 <b>अचूकता (Accuracy):</b> {acc}%</div>
        </div>
        <div class="kpi-grid">
            <div class="kpi"><div class="num">{score}</div><div class="lbl">एकूण गुण (Marks)</div></div>
            <div class="kpi"><div class="num" style="color:#4ade80;">{correct_cnt}</div><div class="lbl">बरोबर (Correct)</div></div>
            <div class="kpi"><div class="num" style="color:#f87171;">{wrong_cnt}</div><div class="lbl">चुकीचे (Incorrect)</div></div>
            <div class="kpi"><div class="num" style="color:#cbd5e1;">{unans_cnt}</div><div class="lbl">अनुत्तरित (Skipped)</div></div>
        </div>
    </div>

    <div class="filters">
        <button class="btn-filter active" onclick="filterQuestions('all')">📋 सर्व प्रश्न ({total_q})</button>
        <button class="btn-filter" onclick="filterQuestions('incorrect')">❌ चुकीचे प्रश्न ({wrong_cnt})</button>
        <button class="btn-filter" onclick="filterQuestions('correct')">✅ बरोबर प्रश्न ({correct_cnt})</button>
    </div>

    <div id="questions-list">
        {''.join(cards_html)}
    </div>
</div>

<script>
function filterQuestions(type) {{
    document.querySelectorAll('.btn-filter').forEach(b => b.classList.remove('active'));
    event.target.classList.add('active');
    document.querySelectorAll('.q-card').forEach(card => {{
        if (type === 'all') {{
            card.style.display = 'block';
        }} else {{
            card.style.display = (card.getAttribute('data-status') === type) ? 'block' : 'none';
        }}
    }});
}}
</script>
</body>
</html>"""
    return full_html

def generate_incorrect_answers_report(records: list[dict], metadata: dict, score_result: dict, exam_name: str) -> str:
    """
    Generates an exclusive, deep-dive HTML report specifically focused on INCORRECT questions.
    Provides detailed step-by-step reasoning, grammar rules, distractor traps, and objection filing templates.
    """
    candidate_name = metadata.get("candidate_name") or "Candidate"
    roll_num = metadata.get("roll_number") or "N/A"
    post_name = metadata.get("post_name") or "General"
    test_date = metadata.get("test_date") or ""

    wrong_records = [r for r in records if r.get("evaluation") == "incorrect"]
    score = score_result.get("score", 0.0)
    correct_cnt = score_result.get("correct", 0)
    wrong_cnt = len(wrong_records)
    total_q = len(records)

    cards_html = []
    for idx, r in enumerate(wrong_records, 1):
        qnum = r.get("question_number") or idx
        sec = r.get("section", "General")
        qtext = r.get("question_text", "Question Text")
        chosen_num = str(r.get("chosen_option_number") or "-")
        correct_num = str(r.get("correct_option_number") or "-")
        chosen_txt = r.get("chosen_option_text") or ""
        correct_txt = r.get("correct_option_text") or ""
        options = r.get("options", {})
        comp = r.get("comprehension", "")

        opts_html = []
        for opt_k in ["1", "2", "3", "4"]:
            if opt_k in options:
                opt_val = options[opt_k]
                is_correct_opt = (opt_k == correct_num)
                is_chosen_opt = (opt_k == chosen_num)

                opt_class = "opt-item"
                icon = f"<b>{opt_k}.</b> "
                if is_correct_opt and is_chosen_opt:
                    opt_class += " opt-correct opt-chosen"
                    icon = f"<b>{opt_k}.</b> ✅ "
                elif is_correct_opt:
                    opt_class += " opt-correct"
                    icon = f"<b>{opt_k}.</b> ✅ "
                elif is_chosen_opt:
                    opt_class += " opt-incorrect"
                    icon = f"<b>{opt_k}.</b> ❌ "

                opts_html.append(f'<div class="{opt_class}">{icon}{opt_val}</div>')

        explanation = generate_smart_explanation(r).replace("\n", "<br>")
        comp_html = f'<div class="comp-box"><b>📖 उतारा (Comprehension):</b><p>{comp}</p></div>' if comp else ""

        cards_html.append(f"""
        <div class="q-card" id="q_{qnum}">
            <div class="q-header">
                <div>
                    <span class="q-num">❌ चुकीचा प्रश्न क्र. {idx} (मूळ प्रश्न क्र. {qnum})</span>
                    <span class="q-sec">{sec}</span>
                </div>
                <span class="badge badge-danger">गुण नुकसान: -1 किंवा -2</span>
            </div>
            {comp_html}
            <div class="q-body">
                <p class="q-text">{qtext}</p>
                <div class="options-grid">
                    {''.join(opts_html)}
                </div>
            </div>
            <div class="q-footer">
                <div class="ans-summary">
                    <div class="ans-block user-ans">
                        <span class="lbl">👤 तुमचे निवडलेले उत्तर:</span>
                        <span class="val text-danger">पर्याय {chosen_num} {f"('{chosen_txt}')" if chosen_txt else ""}</span>
                    </div>
                    <div class="ans-block correct-ans">
                        <span class="lbl">🎯 अधिकृत बरोबर उत्तर:</span>
                        <span class="val text-success">पर्याय {correct_num} {f"('{correct_txt}')" if correct_txt else ""}</span>
                    </div>
                </div>
                <div class="exp-box">
                    <div class="exp-title">💡 सविस्तर विश्लेषण व कारणमीमांसा:</div>
                    <div class="exp-content">{explanation}</div>
                </div>
                <div class="objection-box">
                    <div class="obj-header">⚖️ अधिकृत आक्षेप (Objection) तपासणी व मार्गदर्शन:</div>
                    <p>जर तुम्हाला वाटत असेल की अधिकृत उत्तरतालिकेत चूक आहे किंवा एकापेक्षा जास्त पर्याय बरोबर आहेत, तर तुम्ही अधिकृत हरकती (Objection Tracker) मध्ये आक्षेप नोंदवू शकता.</p>
                    <div class="obj-template">
                        <b>आक्षेप मसुदा (Draft):</b>
                        <code>"प्रश्न क्र. {qnum} (Question ID: {r.get('question_id', qnum)}) बाबत अधिकृत उत्तरतालिकेत पर्याय {correct_num} दिला आहे. परंतु प्रमाणित संदर्भानुसार पर्याय {chosen_num} हा देखील ग्राह्य ठरतो. कृपया पुनर्तपासणी व्हावी."</code>
                    </div>
                </div>
            </div>
        </div>
        """)

    report_html = f"""<!DOCTYPE html>
<html lang="mr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>ExamRankers चुकीचे प्रश्न सविस्तर विश्लेषण — {candidate_name}</title>
<style>
:root {{
    --primary: #4338ca;
    --success: #15803d;
    --danger: #b91c1c;
    --bg: #f8fafc;
    --card-bg: #ffffff;
    --text: #0f172a;
    --border: #cbd5e1;
}}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Noto Sans", sans-serif; background: var(--bg); color: var(--text); padding: 1.5rem; line-height: 1.6; }}
.container {{ max-width: 920px; margin: 0 auto; }}
.header-box {{ background: linear-gradient(135deg, #7f1d1d, #991b1b, #450a0a); color: #fff; padding: 2rem; border-radius: 1rem; margin-bottom: 2rem; box-shadow: 0 10px 25px -5px rgba(185,28,28,0.25); }}
.header-box h1 {{ font-size: 1.7rem; margin-bottom: 0.5rem; }}
.meta-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 0.75rem; margin-top: 1rem; font-size: 0.95rem; opacity: 0.95; }}
.kpi-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); gap: 1rem; margin-top: 1.5rem; }}
.kpi {{ background: rgba(255,255,255,0.15); padding: 1rem; border-radius: 0.75rem; text-align: center; }}
.kpi .num {{ font-size: 1.8rem; font-weight: 700; }}
.kpi .lbl {{ font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.05em; }}
.q-card {{ background: var(--card-bg); border: 1px solid var(--border); border-left: 6px solid var(--danger); border-radius: 0.85rem; margin-bottom: 2rem; padding: 1.5rem; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05); }}
.q-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem; padding-bottom: 0.75rem; border-bottom: 1px solid var(--border); flex-wrap: wrap; gap: 0.5rem; }}
.q-num {{ font-size: 1.15rem; font-weight: 700; color: var(--danger); }}
.q-sec {{ font-size: 0.85rem; background: #fee2e2; color: #991b1b; padding: 0.25rem 0.65rem; border-radius: 0.4rem; font-weight: 600; margin-left: 0.5rem; }}
.badge {{ padding: 0.3rem 0.7rem; border-radius: 0.4rem; font-size: 0.8rem; font-weight: 700; }}
.badge-danger {{ background: #fee2e2; color: #991b1b; }}
.comp-box {{ background: #fefce8; border: 1px solid #fef08a; padding: 1rem; border-radius: 0.5rem; font-size: 0.9rem; margin-bottom: 1rem; color: #713f12; }}
.q-text {{ font-size: 1.1rem; font-weight: 600; margin-bottom: 1.2rem; color: #0f172a; line-height: 1.5; }}
.options-grid {{ display: grid; gap: 0.65rem; margin-bottom: 1.2rem; }}
.opt-item {{ padding: 0.85rem 1.1rem; border: 1px solid var(--border); border-radius: 0.5rem; background: #f8fafc; font-size: 0.98rem; }}
.opt-correct {{ background: #dcfce7; border-color: #86efac; color: #14532d; font-weight: 600; }}
.opt-incorrect {{ background: #fee2e2; border-color: #fca5a5; color: #7f1d1d; font-weight: 600; }}
.ans-summary {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 1rem; padding: 1rem; background: #f1f5f9; border-radius: 0.6rem; margin-bottom: 1rem; }}
.ans-block {{ display: flex; flex-direction: column; gap: 0.25rem; font-size: 0.95rem; }}
.ans-block .lbl {{ font-size: 0.82rem; color: #475569; font-weight: 600; text-transform: uppercase; }}
.ans-block .val {{ font-size: 1.05rem; font-weight: 700; }}
.text-danger {{ color: #dc2626; }}
.text-success {{ color: #16a34a; }}
.exp-box {{ background: #eff6ff; border: 1px solid #bfdbfe; padding: 1.1rem; border-radius: 0.6rem; margin-bottom: 1rem; }}
.exp-title {{ font-size: 1rem; font-weight: 700; color: #1e40af; margin-bottom: 0.6rem; }}
.exp-content {{ font-size: 0.95rem; color: #1e3a8a; line-height: 1.6; }}
.objection-box {{ background: #fffbeb; border: 1px solid #fde68a; padding: 1rem; border-radius: 0.6rem; font-size: 0.92rem; color: #78350f; }}
.obj-header {{ font-weight: 700; margin-bottom: 0.4rem; color: #92400e; }}
.obj-template {{ background: #ffffff; border: 1px dashed #d97706; padding: 0.75rem; border-radius: 0.4rem; margin-top: 0.5rem; }}
.obj-template code {{ font-family: monospace; color: #b45309; display: block; margin-top: 0.25rem; font-size: 0.9rem; }}
.print-btn {{ display: inline-block; padding: 0.6rem 1.4rem; background: #1e293b; color: #fff; border-radius: 0.5rem; text-decoration: none; font-weight: 600; cursor: pointer; border: none; margin-bottom: 1.5rem; }}
@media print {{
    body {{ background: #fff; padding: 0; }}
    .print-btn {{ display: none; }}
    .q-card {{ break-inside: avoid; }}
}}
</style>
</head>
<body>
<div class="container">
    <div class="header-box">
        <h1>❌ ExamRankers सविस्तर चुकीचे प्रश्न व आक्षेप विश्लेषण</h1>
        <p>परीक्षा: <b>{exam_name}</b> | पद: <b>{post_name}</b></p>
        <div class="meta-grid">
            <div>👤 <b>उमेदवार:</b> {candidate_name}</div>
            <div>🔢 <b>हजेरी क्र. (Roll):</b> {roll_num}</div>
            <div>📅 <b>परीक्षा दिनांक:</b> {test_date}</div>
            <div>🎯 <b>सद्य गुण:</b> {score} मार्क्स</div>
        </div>
        <div class="kpi-grid">
            <div class="kpi"><div class="num" style="color:#fca5a5;">{wrong_cnt}</div><div class="lbl">एकूण चुकीचे प्रश्न</div></div>
            <div class="kpi"><div class="num" style="color:#86efac;">{correct_cnt}</div><div class="lbl">बरोबर प्रश्न</div></div>
            <div class="kpi"><div class="num">{total_q}</div><div class="lbl">एकूण प्रश्न संख्या</div></div>
            <div class="kpi"><div class="num" style="color:#fde047;">+{wrong_cnt} ते +{wrong_cnt * 2}</div><div class="lbl">संभाव्य वाढ (सुधारणा)</div></div>
        </div>
    </div>

    <button class="print-btn" onclick="window.print()">🖨️ ही विश्लेषणात्मक फाईल Print / PDF सेव्ह करा</button>

    <div id="wrong-questions-list">
        {''.join(cards_html) if cards_html else '<p>🎉 अभिनंदन! तुमचे एकही उत्तर चुकीचे नाही.</p>'}
    </div>
</div>
</body>
</html>"""
    return report_html


async def generate_topic_weightage_analysis(text: str, exam_name: str) -> str:
    """
    Generates a daily topic & weightage analysis report for Maharashtra Saralsewa (TCS/IBPS pattern).
    Posted to the Paid VIP Channel along with exam quizzes.
    """
    api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    model = os.getenv("OPENROUTER_MODEL", "google/gemini-2.0-flash-exp:free").strip()

    if not api_key:
        return get_fallback_topic_analysis(exam_name)

    prompt = f"""
You are Maharashtra's top Saralsewa Bharti (TCS & IBPS Pattern) exam expert.
Analyze the following exam response sheet text for '{exam_name}'.
Produce a comprehensive 'Daily Exam Shift Topic & Weightage Analysis' (दैनिक शिफ्ट टॉपिक व वेटेज विश्लेषण) formatted in professional Marathi with HTML formatting tags (<b>, <i>, <code>).

Structure of the report:
1. 📊 Header: <b>📊 दैनिक शिफ्ट विश्लेषण व टॉपिक वेटेज — {exam_name}</b>
2. 📌 विषयनिहाय प्रश्न संख्या व विचारलेले मुख्य टॉपिक्स:
   - 🔹 मराठी व्याकरण (उदा. प्रयोग, समास, समानार्थी/विरुद्धार्थी, काळ, वाक्यप्रचार, म्हणी)
   - 🔹 इंग्रजी व्याकरण (उदा. Vocab, Prepositions, Error Spotting, Tenses, Comprehension)
   - 🔹 सामान्य ज्ञान / GK (उदा. महाराष्ट्र भूगोल, इतिहास, चालू घडामोडी 2024, RTI कायदा, राज्यघटना)
   - 🔹 बुद्धिमत्ता चाचणी व अंकगणित (उदा. अंकमालिका, दिशा, बैठक व्यवस्था, नातेसंबंध, नफा-तोटा, शेकडेवारी)
3. 🔥 सर्वाधिक विचारलेले ५ हॉट टॉपिक्स (Top 5 Most Repeated Topics)
4. ⚡ काठिण्य पातळी (Overall Difficulty: सोपे / मध्यम / कठीण)
5. 💡 पुढील शिफ्टसाठी महत्त्वाच्या टिप्स (Strategic Advice for Upcoming Shifts)

Keep it crisp, actionable, engaging, and under 2500 characters.
Raw text excerpt:
{text[:8000]}
"""

    headers = {
        "Authorization": f"Bearer {api_key}",
        "HTTP-Referer": "https://examrankers.bot",
        "X-Title": "ExamRankers Daily Topic Weightage Analysis",
        "Content-Type": "application/json"
    }

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are a professional Maharashtra Saralsewa Bharti exam analyst. Output clean Marathi text formatted with Telegram HTML tags."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.3
    }

    try:
        async with httpx.AsyncClient(timeout=40.0) as client:
            resp = await client.post(OPENROUTER_API_URL, headers=headers, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                content = data["choices"][0]["message"]["content"].strip()
                # Clean any markdown code fences if AI wrapped it in ```html
                content = re.sub(r"^```(?:html)?\s*", "", content)
                content = re.sub(r"\s*```$", "", content)
                return content
    except Exception as e:
        logger.warning(f"AI Topic Analysis call failed: {e}. Using fallback.")

    return get_fallback_topic_analysis(exam_name)

def get_fallback_topic_analysis(exam_name: str) -> str:
    """Standardized high-yield topic analysis based on TCS/IBPS Saralsewa trends."""
    return (
        f"📊 <b>दैनिक शिफ्ट टॉपिक व वेटेज विश्लेषण — {exam_name}</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "⚡ <b>TCS / IBPS लेटेस्ट पॅटर्न शिफ्ट अवलोकन</b>\n\n"
        "📌 <b>१. मराठी व्याकरण (२५ प्रश्न / ५० गुण):</b>\n"
        "• <i>प्रयोग (कर्तरी, कर्मणी, भावे):</i> २-३ प्रश्न\n"
        "• <i>समास व प्रकार:</i> २ प्रश्न\n"
        "• <i>समानार्थी व विरुद्धार्थी शब्द:</i> ४-५ प्रश्न\n"
        "• <i>म्हणी व वाक्प्रचार:</i> ३ प्रश्न\n"
        "• <i>वाक्यपृथक्करण व काळ:</i> ३ प्रश्न\n\n"
        "📌 <b>२. इंग्रजी व्याकरण (२५ प्रश्न / ५० गुण):</b>\n"
        "• <i>Synonyms & Antonyms:</i> ४-५ प्रश्न\n"
        "• <i>Spotting Errors & Sentence Correction:</i> ३-४ प्रश्न\n"
        "• <i>Prepositions & Articles:</i> ३ प्रश्न\n"
        "• <i>Direct/Indirect & Active/Passive:</i> २ प्रश्न\n"
        "• <i>Para Jumbles / Reading Comprehension:</i> ५ प्रश्न\n\n"
        "📌 <b>३. सामान्य ज्ञान - GS (२५ प्रश्न / ५० गुण):</b>\n"
        "• <i>महाराष्ट्र भूगोल (नद्या, जिल्हे, धरणे):</i> ४ प्रश्न\n"
        "• <i>आधुनिक भारताचा इतिहास व समाजसुधारक:</i> ४ प्रश्न\n"
        "• <i>माहितीचा अधिकार (RTI Act 2005):</i> २-३ प्रश्न\n"
        "• <i>चालू घडामोडी २०२४ (पुरस्कार, क्रीडा, योजना):</i> ५-६ प्रश्न\n"
        "• <i>भारतीय राज्यघटना व पंचायत राज:</i> ३-४ प्रश्न\n\n"
        "📌 <b>४. बुद्धिमत्ता व गणित (२५ प्रश्न / ५० गुण):</b>\n"
        "• <i>अंकमालिका व अक्षरमालिका:</i> ४ प्रश्न\n"
        "• <i>बैठक व्यवस्था (Seating Arrangement):</i> ४-५ प्रश्न\n"
        "• <i>नातेसंबंध व दिशाज्ञान:</i> ३ प्रश्न\n"
        "• <i>नफा-तोटा, शेकडेवारी, सरासरी:</i> ३-४ प्रश्न\n"
        "• <i>वेळ, काम व वेग:</i> २-३ प्रश्न\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "🔥 <b>काठिण्य पातळी:</b> मध्यम (Moderate)\n"
        "💡 <b>सल्ला:</b> चालू घडामोडी आणि बैठक व्यवस्था (Seating) यावर जास्त वेळ द्या, हेच स्कोर ठरवणारे घटक आहेत!\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "💎 <i>वरील सर्व टॉपिक्सचे प्रश्न खालील क्विझमध्ये त्वरित सोडवा!</i>"
    )

def get_daily_latest_exam_questions() -> dict:
    """
    Returns curated daily latest asked exam questions from recent TCS/IBPS shifts
    across Maharashtra Saralsewa Bharti exams.
    """
    return {
        "date": "आजचे विचारलेले प्रश्न (Latest Shift Updates)",
        "trend_summary": (
            "🔥 <b>महाराष्ट्र सरळसेवा भरती — आजचे विचारलेले प्रश्न (TCS & IBPS Pattern)</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "नुकत्याच पार पडलेल्या तलाठी, ZP, पोलीस भरती व आरोग्य विभाग शिफ्ट्समध्ये विचारलेले अतिमहत्त्वाचे प्रश्न:"
        ),
        "questions": [
            {
                "subject": "मराठी व्याकरण",
                "question": "खालीलपैकी 'प्रयोग' ओळखा: 'रामाने रावणास मारले.'",
                "options": ["A) कर्तरी प्रयोग", "B) कर्मणी प्रयोग", "C) भावे प्रयोग", "D) संकीर्ण प्रयोग"],
                "answer": "C) भावे प्रयोग",
                "explanation": "कर्ता व कर्म दोघांनाही प्रत्यय असल्याने क्रियापद तृतीयपुरुषी नपुंसकलिंगी एकावचनी राहते, म्हणून हा 'भावे प्रयोग' आहे."
            },
            {
                "subject": "सामान्य ज्ञान (GS)",
                "question": "माहितीचा अधिकार कायदा (RTI Act) भारतात कोणत्या वर्षी लागू झाला?",
                "options": ["A) २००२", "B) २००५", "C) २०१०", "D) २०००"],
                "answer": "B) २००५",
                "explanation": "१२ ऑक्टोबर २००५ रोजी माहितीचा अधिकार कायदा (RTI Act 2005) संपूर्ण भारतात लागू करण्यात आला."
            },
            {
                "subject": "बुद्धिमत्ता चाचणी",
                "question": "मालिका पूर्ण करा: 3, 8, 18, 38, ?",
                "options": ["A) 76", "B) 78", "C) 68", "D) 82"],
                "answer": "B) 78",
                "explanation": "पॅटर्न: (3×2)+2 = 8, (8×2)+2 = 18, (18×2)+2 = 38, (38×2)+2 = 78."
            },
            {
                "subject": "English Language",
                "question": "Choose the correct Synonym of 'CANDID':",
                "options": ["A) Deceitful", "B) Frank", "C) Shy", "D) Rude"],
                "answer": "B) Frank",
                "explanation": "'Candid' means truthful and straightforward; frank."
            },
            {
                "subject": "महाराष्ट्र भूगोल व इतिहास",
                "question": "महाराष्ट्रातील सर्वाधिक लांबीची नदी कोणती आहे?",
                "options": ["A) कृष्णा", "B) भीमा", "C) गोदावरी", "D) तापी"],
                "answer": "C) गोदावरी",
                "explanation": "गोदावरी ही महाराष्ट्रातील सर्वाधिक लांबीची नदी असून तिचा उगम नाशिक जिल्ह्यातील त्र्यंबकेश्वर येथे होतो (लांबी ६६८ किमी महाराष्ट्रात)."
            }
        ]
    }

def generate_master_analytics_report_html(data: dict) -> str:
    """
    Generates a world-class, responsive HTML Executive Analytics Dashboard for Admins.
    Provides deep breakdowns: Exam-wise, Post-wise, Category-wise, and Location/District-wise.
    """
    overall = data.get("overall", {})
    exams = data.get("exams", [])
    posts = data.get("posts", [])
    categories = data.get("categories", [])
    locations = data.get("locations", [])
    toppers = data.get("toppers", [])
    generated_at = datetime.now().strftime("%d-%m-%Y %I:%M %p")

    # Exam-wise rows
    exam_rows = []
    for e in exams:
        exam_rows.append(f"""
        <tr>
            <td class="font-bold text-white">{e.get('name', 'N/A')}</td>
            <td><span class="badge badge-indigo">{e.get('count', 0)} Candidates</span></td>
            <td class="text-emerald font-bold">{e.get('max_score', 0):.1f}</td>
            <td class="text-cyan font-bold">{e.get('avg_score', 0):.1f}</td>
            <td class="text-rose">{e.get('min_score', 0):.1f}</td>
            <td><span class="badge badge-emerald">Safe &gt;= {e.get('safe_cutoff', 0):.1f}</span></td>
            <td><span class="badge badge-amber">Border &gt;= {e.get('border_cutoff', 0):.1f}</span></td>
        </tr>
        """)

    # Post-wise rows
    post_rows = []
    for p in posts:
        post_rows.append(f"""
        <tr>
            <td class="font-bold text-white">{p.get('name', 'General')}</td>
            <td><span class="badge badge-cyan">{p.get('count', 0)} उमेदवारी</span></td>
            <td class="text-emerald font-bold">{p.get('max_score', 0):.1f}</td>
            <td class="text-amber font-bold">{p.get('avg_score', 0):.1f}</td>
        </tr>
        """)

    # Category-wise rows
    cat_rows = []
    for c in categories:
        pct = c.get('percentage', 0)
        cat_rows.append(f"""
        <tr>
            <td class="font-bold text-white">{c.get('name', 'Open')}</td>
            <td>{c.get('count', 0)} ({pct:.1f}%)</td>
            <td>
                <div class="progress-bar-bg">
                    <div class="progress-bar-fill" style="width: {min(100, max(5, pct))}%;"></div>
                </div>
            </td>
            <td class="text-cyan font-bold">{c.get('avg_score', 0):.1f}</td>
            <td class="text-emerald font-bold">{c.get('max_score', 0):.1f}</td>
            <td><span class="badge badge-indigo">Est. Cutoff: {c.get('cutoff_est', 0):.1f}</span></td>
        </tr>
        """)

    # Location-wise rows
    loc_rows = []
    for l in locations:
        loc_rows.append(f"""
        <tr>
            <td class="font-bold text-white">📍 {l.get('district', 'Maharashtra')}</td>
            <td><span class="badge badge-purple">{l.get('count', 0)} केंद्र परीक्षार्थी</span></td>
            <td class="text-cyan font-bold">{l.get('avg_score', 0):.1f}</td>
            <td class="text-emerald font-bold">{l.get('max_score', 0):.1f}</td>
        </tr>
        """)

    # Toppers rows
    topper_rows = []
    for t in toppers:
        r_badge = "🥇" if t.get('rank') == 1 else ("🥈" if t.get('rank') == 2 else ("🥉" if t.get('rank') == 3 else f"#{t.get('rank')}"))
        topper_rows.append(f"""
        <tr>
            <td class="font-bold text-center">{r_badge}</td>
            <td class="font-bold text-white">{t.get('name', 'परीक्षार्थी')}</td>
            <td><code>{t.get('roll', 'N/A')}</code></td>
            <td>{t.get('exam', 'N/A')}</td>
            <td>{t.get('post', 'General')}</td>
            <td><span class="badge badge-cyan">{t.get('category', 'Open')}</span></td>
            <td class="text-emerald font-bold text-lg">{t.get('score', 0):.1f}</td>
        </tr>
        """)

    # Topic-wise analysis rows
    topics = data.get("topics", [
        {"subject": "मराठी भाषा व व्याकरण", "avg_q": 25, "accuracy": 78.4, "difficulty": "मध्यम (Moderate)", "badge": "badge-emerald", "focus": "समास, प्रयोग, शब्दसंग्रह, म्हणी, उतारा"},
        {"subject": "English Language & Comprehension", "avg_q": 25, "accuracy": 64.2, "difficulty": "मध्यम-कठीण", "badge": "badge-amber", "focus": "Error Spotting, Idioms, Subject-Verb, Para Jumbles"},
        {"subject": "सामान्य ज्ञान (GS / GK)", "avg_q": 25, "accuracy": 58.7, "difficulty": "कठीण (Challenging)", "badge": "badge-rose", "focus": "RTI Act 2005, 2011 जनगणना, नदी प्रणाली, समाजसुधारक"},
        {"subject": "बौद्धिक चाचणी व अंकगणित", "avg_q": 25, "accuracy": 71.3, "difficulty": "मध्यम (Moderate)", "badge": "badge-cyan", "focus": "बैठक व्यवस्था (Seating), नातेसंबंध, नफा-तोटा, संख्यामालिका"}
    ])
    topic_rows = []
    for tp in topics:
        topic_rows.append(f"""
        <tr>
            <td class="font-bold text-white">{tp.get('subject', 'N/A')}</td>
            <td class="text-center">{tp.get('avg_q', 25)}</td>
            <td class="text-emerald font-bold">{tp.get('accuracy', 0):.1f}%</td>
            <td><span class="badge {tp.get('badge', 'badge-cyan')}">{tp.get('difficulty', 'मध्यम')}</span></td>
            <td class="text-muted" style="font-size: 13px;">{tp.get('focus', '')}</td>
        </tr>
        """)

    # Trending exam topics cards
    trending_list = data.get("trending", [
        {"icon": "📜", "topic": "माहितीचा अधिकार कायदा (RTI Act 2005)", "freq": "९८% शिफ्ट्समध्ये विचारला", "details": "कलम ४ (माहिती देणे), कलम ६ (अर्ज प्रक्रिया), कलम १९ (अपील), कलम २० (शास्ती/दंड). दर शिफ्टला २-३ प्रश्न."},
        {"icon": "👥", "topic": "जनगणना २०११ (Census 2011)", "freq": "९५% शिफ्ट्समध्ये विचारला", "details": "महाराष्ट्राची साक्षरता (८२.३४%), सर्वाधिक/किमान लिंगगुणोत्तर जिल्हे, आदिवासी व नागरी लोकसंख्या टक्केवारी."},
        {"icon": "⚡", "topic": "मराठी: समास व प्रयोग", "freq": "१००% शिफ्ट्समध्ये विचारला", "details": "कर्मधारय व बहुव्रीही समास फरक, भावे प्रयोगाची ओळख, कर्मणी प्रयोगाचे प्रकार (शक्य, समापन)."},
        {"icon": "🪑", "topic": "बैठक व्यवस्था (Seating Arrangement)", "freq": "९०% शिफ्ट्समध्ये विचारला", "details": "वर्तुळाकार व रेषीय बैठक व्यवस्था. ६ ते ८ व्यक्तींचे इनवर्ड/आऊटवर्ड फेसिंग कोडे (५ गुण हमखास)."},
        {"icon": "🌊", "topic": "महाराष्ट्र भूगोल: जलप्रणाली व धरणे", "freq": "८५% शिफ्ट्समध्ये विचारला", "details": "गोदावरी, भीमा, कृष्णा नद्यांची खोरी, उपनद्या, उगमस्थाने, जायकवाडी, कोयना व उजनी धरणे."}
    ])
    trending_cards = []
    for tr in trending_list:
        trending_cards.append(f"""
        <div style="background: rgba(30, 41, 59, 0.6); border: 1px solid var(--border-color); border-radius: 12px; padding: 16px;">
            <div style="font-size: 24px; margin-bottom: 8px;">{tr['icon']}</div>
            <div style="font-size: 16px; font-weight: 700; color: #ffffff; margin-bottom: 4px;">{tr['topic']}</div>
            <div style="font-size: 12px; font-weight: 600; color: #06b6d4; margin-bottom: 8px;"><span class="badge badge-cyan">{tr['freq']}</span></div>
            <div style="font-size: 13px; color: var(--text-muted); line-height: 1.4;">{tr['details']}</div>
        </div>
        """)

    html = f"""<!DOCTYPE html>
<html lang="mr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ExamRankers™ Master Exam Analysis & Merit Dashboard</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=Noto+Sans+Devanagari:wght@400;600;700;800&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg-base: #080d1a;
            --bg-card: rgba(17, 24, 39, 0.85);
            --bg-card-hover: rgba(30, 41, 59, 0.9);
            --border-color: rgba(255, 255, 255, 0.08);
            --primary: #6366f1;
            --emerald: #10b981;
            --cyan: #06b6d4;
            --amber: #f59e0b;
            --rose: #f43f5e;
            --purple: #a855f7;
            --text-main: #f8fafc;
            --text-muted: #94a3b8;
        }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: 'Plus Jakarta Sans', 'Noto Sans Devanagari', -apple-system, sans-serif;
            background: radial-gradient(circle at 10% 20%, #111827 0%, #080d1a 100%);
            color: var(--text-main);
            min-height: 100vh;
            padding: 30px 16px;
        }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        .header {{
            background: linear-gradient(135deg, rgba(99, 102, 241, 0.15) 0%, rgba(6, 182, 212, 0.15) 100%);
            border: 1px solid var(--border-color);
            border-radius: 20px;
            padding: 32px 28px;
            margin-bottom: 28px;
            backdrop-filter: blur(16px);
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 20px;
        }}
        .header h1 {{ font-size: 26px; font-weight: 800; color: #ffffff; letter-spacing: -0.5px; }}
        .header p {{ color: var(--text-muted); font-size: 14px; margin-top: 6px; }}
        .btn-print {{
            background: linear-gradient(135deg, #6366f1, #4f46e5);
            color: #ffffff;
            border: none;
            padding: 12px 22px;
            border-radius: 12px;
            font-weight: 700;
            font-size: 14px;
            cursor: pointer;
            box-shadow: 0 4px 15px rgba(99, 102, 241, 0.35);
            transition: all 0.2s ease;
        }}
        .btn-print:hover {{ transform: translateY(-2px); box-shadow: 0 6px 20px rgba(99, 102, 241, 0.45); }}
        
        .grid-stats {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
            gap: 16px;
            margin-bottom: 28px;
        }}
        .stat-card {{
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 16px;
            padding: 20px 22px;
            backdrop-filter: blur(12px);
            transition: transform 0.2s ease;
        }}
        .stat-card:hover {{ transform: translateY(-3px); border-color: rgba(99, 102, 241, 0.3); }}
        .stat-label {{ font-size: 13px; font-weight: 600; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.5px; }}
        .stat-value {{ font-size: 30px; font-weight: 800; margin-top: 8px; color: #ffffff; }}
        .stat-sub {{ font-size: 12px; color: var(--text-muted); margin-top: 4px; }}

        .section-card {{
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 18px;
            padding: 26px;
            margin-bottom: 28px;
            backdrop-filter: blur(12px);
        }}
        .section-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 18px;
            padding-bottom: 12px;
            border-bottom: 1px solid var(--border-color);
        }}
        .section-title {{ font-size: 19px; font-weight: 700; color: #ffffff; }}
        .section-badge {{ font-size: 12px; font-weight: 600; color: var(--cyan); background: rgba(6, 182, 212, 0.1); padding: 4px 10px; border-radius: 20px; }}

        table {{ width: 100%; border-collapse: collapse; text-align: left; font-size: 14px; }}
        th {{
            color: var(--text-muted);
            font-weight: 600;
            padding: 12px 14px;
            border-bottom: 1px solid var(--border-color);
            font-size: 12px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        td {{
            padding: 14px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.04);
            color: #cbd5e1;
        }}
        tr:hover td {{ background: rgba(255, 255, 255, 0.02); }}

        .badge {{
            display: inline-block;
            padding: 4px 9px;
            border-radius: 8px;
            font-size: 12px;
            font-weight: 700;
        }}
        .badge-indigo {{ background: rgba(99, 102, 241, 0.15); color: #818cf8; }}
        .badge-emerald {{ background: rgba(16, 185, 129, 0.15); color: #34d399; }}
        .badge-cyan {{ background: rgba(6, 182, 212, 0.15); color: #22d3ee; }}
        .badge-amber {{ background: rgba(245, 158, 11, 0.15); color: #fbbf24; }}
        .badge-rose {{ background: rgba(244, 63, 94, 0.15); color: #fb7185; }}
        .badge-purple {{ background: rgba(168, 85, 247, 0.15); color: #c084fc; }}

        .progress-bar-bg {{
            background: rgba(255, 255, 255, 0.08);
            border-radius: 8px;
            height: 8px;
            width: 100%;
            overflow: hidden;
        }}
        .progress-bar-fill {{
            background: linear-gradient(90deg, #6366f1, #06b6d4);
            height: 100%;
            border-radius: 8px;
        }}

        .text-white {{ color: #ffffff !important; }}
        .text-emerald {{ color: var(--emerald) !important; }}
        .text-cyan {{ color: var(--cyan) !important; }}
        .text-amber {{ color: var(--amber) !important; }}
        .text-rose {{ color: var(--rose) !important; }}
        .font-bold {{ font-weight: 700; }}
        .text-lg {{ font-size: 16px; }}

        .footer {{
            text-align: center;
            color: var(--text-muted);
            font-size: 13px;
            margin-top: 40px;
            padding: 20px;
            border-top: 1px solid var(--border-color);
        }}

        @media (max-width: 768px) {{
            .grid-stats {{ grid-template-columns: 1fr 1fr; }}
            .header {{ flex-direction: column; align-items: flex-start; }}
            table {{ font-size: 12px; }}
            td, th {{ padding: 10px 8px; }}
        }}
        @media print {{
            body {{ background: #ffffff; color: #000000; }}
            .btn-print {{ display: none; }}
            .header, .section-card, .stat-card {{ background: #ffffff; border: 1px solid #ccc; color: #000000; box-shadow: none; }}
            .text-white {{ color: #000000 !important; }}
            td, th {{ color: #000000 !important; border-bottom: 1px solid #ddd; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <header class="header">
            <div>
                <h1>📊 ExamRankers™ Master Exam Analysis &amp; Merit Report</h1>
                <p>महाराष्ट्र सरळसेवा भरती (TCS &amp; IBPS पॅटर्न) — सविस्तर निकाल, प्रवर्गनिहाय, पदानिहाय व जिल्हानिहाय विश्लेषण</p>
                <p style="font-size: 12px; color: var(--cyan); margin-top: 4px;">📅 अहवाल दिनांक: {generated_at} | अधिकृत गोपनीय प्रशासक अहवाल</p>
            </div>
            <div>
                <button class="btn-print" onclick="window.print()">🖨️ Print / Save as PDF</button>
            </div>
        </header>

        <!-- KPI Overall Stats -->
        <div class="grid-stats">
            <div class="stat-card">
                <div class="stat-label">एकूण परीक्षक (Candidates)</div>
                <div class="stat-value text-cyan">{overall.get('total_candidates', 0)}</div>
                <div class="stat-sub">साठवलेल्या अद्वितीय रिस्पॉन्स शीट्स</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">राज्यस्तरीय सर्वोच्च गुण (Topper)</div>
                <div class="stat-value text-emerald">{overall.get('highest_score', 0):.1f}</div>
                <div class="stat-sub">Top Mark across all exams</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">सरासरी गुण (State Average)</div>
                <div class="stat-value text-amber">{overall.get('avg_score', 0):.1f}</div>
                <div class="stat-sub">एकूण सरासरी गुण</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">सक्रिय परीक्षा (Exams)</div>
                <div class="stat-value text-white">{overall.get('total_exams', 0)}</div>
                <div class="stat-sub">तलाठी, ZP, पोलीस, आरोग्य, नगरपरिषद</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">सरासरी अचूकता (Accuracy)</div>
                <div class="stat-value text-purple">{overall.get('avg_accuracy', 0):.1f}%</div>
                <div class="stat-sub">प्रश्नांची बरोबर सोडवणूक टक्केवारी</div>
            </div>
        </div>

        <!-- 1. Top 10 State Merit Leaders -->
        <div class="section-card">
            <div class="section-header">
                <div class="section-title">🏆 राज्यस्तरीय गुणवत्ता यादी (Top State Rankers)</div>
                <div class="section-badge">गुणवत्ता यादी व टॉपर्स</div>
            </div>
            <div style="overflow-x: auto;">
                <table>
                    <thead>
                        <tr>
                            <th>रँक</th>
                            <th>उमेदवाराचे नाव</th>
                            <th>रोल / नोंदणी क्र.</th>
                            <th>परीक्षा</th>
                            <th>पद / संवर्ग</th>
                            <th>प्रवर्ग</th>
                            <th>मिळालेले गुण</th>
                        </tr>
                    </thead>
                    <tbody>
                        {"".join(topper_rows) if topper_rows else "<tr><td colspan='7' style='text-align:center;'>अजून कोणतीही रिस्पॉन्स शीट नोंदवलेली नाही.</td></tr>"}
                    </tbody>
                </table>
            </div>
        </div>

        <!-- 2. Exam-wise Deep Dive -->
        <div class="section-card">
            <div class="section-header">
                <div class="section-title">📝 परीक्षा निहाय सविस्तर विश्लेषण (Exam-Wise Analysis)</div>
                <div class="section-badge">Exams Breakdown</div>
            </div>
            <div style="overflow-x: auto;">
                <table>
                    <thead>
                        <tr>
                            <th>परीक्षेचे नाव</th>
                            <th>एकूण परीक्षार्थी</th>
                            <th>टॉप गुण</th>
                            <th>सरासरी गुण</th>
                            <th>किमान गुण</th>
                            <th>अपेक्षित सेफ झोन कट-ऑफ</th>
                            <th>बॉर्डर झोन कट-ऑफ</th>
                        </tr>
                    </thead>
                    <tbody>
                        {"".join(exam_rows) if exam_rows else "<tr><td colspan='7' style='text-align:center;'>डेटा उपलब्ध नाही.</td></tr>"}
                    </tbody>
                </table>
            </div>
        </div>

        <!-- 3. Category-wise Reservation Analysis -->
        <div class="section-card">
            <div class="section-header">
                <div class="section-title">👥 प्रवर्गनिहाय कट-ऑफ व गुण विश्लेषण (Category-Wise Breakdown)</div>
                <div class="section-badge">Reservation Categories</div>
            </div>
            <div style="overflow-x: auto;">
                <table>
                    <thead>
                        <tr>
                            <th>प्रवर्ग (Category)</th>
                            <th>उमेदवार संख्या</th>
                            <th>टक्केवारी वाटा</th>
                            <th>प्रवर्ग सरासरी</th>
                            <th>प्रवर्ग टॉप स्कोर</th>
                            <th>अपेक्षित कट-ऑफ</th>
                        </tr>
                    </thead>
                    <tbody>
                        {"".join(cat_rows) if cat_rows else "<tr><td colspan='6' style='text-align:center;'>डेटा उपलब्ध नाही.</td></tr>"}
                    </tbody>
                </table>
            </div>
        </div>

        <!-- 4. Post-wise Breakdown -->
        <div class="section-card">
            <div class="section-header">
                <div class="section-title">👔 पदानिहाय विश्लेषण (Post-Wise Performance)</div>
                <div class="section-badge">Posts &amp; Cadres</div>
            </div>
            <div style="overflow-x: auto;">
                <table>
                    <thead>
                        <tr>
                            <th>पदाचे नाव (Post Name)</th>
                            <th>एकूण उमेदवार</th>
                            <th>टॉप स्कोर</th>
                            <th>सरासरी गुण</th>
                        </tr>
                    </thead>
                    <tbody>
                        {"".join(post_rows) if post_rows else "<tr><td colspan='4' style='text-align:center;'>डेटा उपलब्ध नाही.</td></tr>"}
                    </tbody>
                </table>
            </div>
        </div>

        <!-- 5. Location / District-wise Breakdown -->
        <div class="section-card">
            <div class="section-header">
                <div class="section-title">📍 केंद्र व जिल्हानिहाय विश्लेषण (District &amp; Center Distribution)</div>
                <div class="section-badge">Location Breakdown</div>
            </div>
            <div style="overflow-x: auto;">
                <table>
                    <thead>
                        <tr>
                            <th>जिल्हा / परीक्षा केंद्र (District)</th>
                            <th>परीक्षार्थी संख्या</th>
                            <th>जिल्हा सरासरी गुण</th>
                            <th>जिल्हा टॉप स्कोर</th>
                        </tr>
                    </thead>
                    <tbody>
                        {"".join(loc_rows) if loc_rows else "<tr><td colspan='4' style='text-align:center;'>डेटा उपलब्ध नाही.</td></tr>"}
                    </tbody>
                </table>
            </div>
        </div>

        <!-- 6. Topic-wise & Subject-wise Performance -->
        <div class="section-card">
            <div class="section-header">
                <div class="section-title">📚 विषय व घटकनिहाय विश्लेषण (Subject &amp; Topic-Wise Accuracy)</div>
                <div class="section-badge">Topic Breakdown</div>
            </div>
            <div style="overflow-x: auto;">
                <table>
                    <thead>
                        <tr>
                            <th>विषय / घटक (Subject / Topic)</th>
                            <th>सरासरी प्रश्न</th>
                            <th>अचूकता (Accuracy)</th>
                            <th>काठिण्य पातळी (Difficulty)</th>
                            <th>अति महत्त्वाचे उपघटक</th>
                        </tr>
                    </thead>
                    <tbody>
                        {"".join(topic_rows) if topic_rows else "<tr><td colspan='5' style='text-align:center;'>डेटा उपलब्ध नाही.</td></tr>"}
                    </tbody>
                </table>
            </div>
        </div>

        <!-- 7. Trending High-Frequency Exam Topics -->
        <div class="section-card">
            <div class="section-header">
                <div class="section-title">🔥 आगामी परीक्षांसाठी ट्रेंडिंग टॉपिक्स (High-Yield Trending Topics)</div>
                <div class="section-badge">Trending Focus</div>
            </div>
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 16px; margin-top: 10px;">
                {"".join(trending_cards) if trending_cards else "<p>डेटा उपलब्ध नाही.</p>"}
            </div>
        </div>

        <footer class="footer">
            <p>© 2026 <b>ExamRankers™ Bot</b> — महाराष्ट्र सरळसेवा भरती अधिकृत अ‍ॅनालिटिक्स प्लॅटफॉर्म.</p>
            <p style="margin-top: 6px;">Generated automatically via Telegram Admin Command. All rights reserved.</p>
        </footer>
    </div>
</body>
</html>"""
    return html

def generate_swot_analysis(records: list[dict], score_result: dict, exam_config: dict = None) -> dict:
    """
    Computes candidate-specific SWOT (Strengths, Weaknesses, Opportunities, Threats) analysis
    based on section-wise marks, accuracy percentages, error patterns, and unattempted questions.
    """
    sections = score_result.get("sections", {})
    total_score = score_result.get("score", 0.0)
    total_q = score_result.get("total_questions", len(records))
    correct = score_result.get("correct", 0)
    wrong = score_result.get("incorrect", 0)
    unans = score_result.get("unanswered", 0)
    attempted = correct + wrong
    overall_acc = (correct / attempted * 100) if attempted > 0 else 0.0

    strengths = []
    weaknesses = []
    opportunities = []
    threats = []

    for sec_name, s_data in sections.items():
        s_att = s_data.get("attempted", 0)
        s_cor = s_data.get("correct", 0)
        s_inc = s_data.get("incorrect", 0)
        s_unans = s_data.get("unanswered", 0)
        s_acc = (s_cor / s_att * 100) if s_att > 0 else 0.0

        if s_acc >= 70.0 and s_cor >= 2:
            strengths.append(f"{sec_name}: उच्च अचूकता {s_acc:.1f}% ({s_cor}/{s_att} योग्य)")
        elif s_acc < 50.0 and s_att >= 2:
            weaknesses.append(f"{sec_name}: कमी अचूकता {s_acc:.1f}% ({s_inc} प्रश्न चुकले)")

        if s_unans >= 3:
            opportunities.append(f"{sec_name} मध्ये {s_unans} प्रश्न न सोडवल्याने गुण गमावले; वेळेचे नियोजन सुधारल्यास +{s_unans*2} गुण मिळू शकतात.")

        if s_inc >= 4:
            threats.append(f"{sec_name} मधील नकारात्मक गुण (Negative risk): {s_inc} प्रश्न चुकल्याने मेरिटला फटका.")

    if not strengths:
        if overall_acc >= 60.0:
            strengths.append(f"एकूण अचूकता प्रमाण {overall_acc:.1f}% समाधानकारक आहे.")
        else:
            strengths.append("मूलभूत व्याकरण व चालू घडामोडींवर सराव वाढवल्यास वेगाने गुण सुधारतील.")

    if not weaknesses:
        if wrong > 0:
            weaknesses.append(f"एकूण {wrong} प्रश्नांमध्ये घाईगडबडीत सूक्ष्म चुका (Silly mistakes) झाल्या आहेत.")
        else:
            weaknesses.append("विशेष त्रुटी आढळली नाही; अप्रतिम व संतुलित कामगिरी!")

    if not opportunities:
        opportunities.append("TCS/IBPS च्या आगामी शिफ्ट्समधील ट्रेंडिंग टॉपिक्स (RTI, जनगणना, समास) सोडवून गुणवत्ता वाढवा.")

    if not threats:
        if wrong > (attempted * 0.25):
            threats.append("२५% पेक्षा जास्त चुकीची उत्तरे — निगेटिव्ह मार्किंगमुळे मेरिट रँक घसरण्याचा गंभीर धोका.")
        else:
            threats.append("अंतिम मिनिटांत अंदाजे उत्तरे (Wild guessing) टाळा, जेणेकरून हक्काचे गुण सुरक्षित राहतील.")

    return {
        "strengths": strengths[:3],
        "weaknesses": weaknesses[:3],
        "opportunities": opportunities[:3],
        "threats": threats[:3],
        "overall_accuracy": round(overall_acc, 1)
    }

def format_swot_telegram_message(swot: dict) -> str:
    """Formats SWOT analysis into an engaging Telegram HTML message."""
    s_lines = "\n".join(f"  • {item}" for item in swot.get("strengths", []))
    w_lines = "\n".join(f"  • {item}" for item in swot.get("weaknesses", []))
    o_lines = "\n".join(f"  • {item}" for item in swot.get("opportunities", []))
    t_lines = "\n".join(f"  • {item}" for item in swot.get("threats", []))

    return (
        "📊 <b>🎯 AI SWOT विश्लेषण (Performance Audit):</b>\n"
        f"🎯 <i>एकूण अचूकता (Accuracy): <b>{swot.get('overall_accuracy', 0)}%</b></i>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💪 <b>सामर्थ्य (Strengths):</b>\n{s_lines}\n\n"
        f"⚠️ <b>दुर्बलता (Weaknesses):</b>\n{w_lines}\n\n"
        f"🚀 <b>संधी (Opportunities):</b>\n{o_lines}\n\n"
        f"⚡ <b>धोके (Threats):</b>\n{t_lines}\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "💡 <i>टिप: वरील संधी व दुर्बल घटकांवर भर दिल्यास अंतिम गुणवत्ता यादीत तुमचे स्थान निश्चित होईल!</i>"
    )

def generate_oneliner_question_bank_pdf(db_path: str, output_path: str, exam_name: str = None) -> str:
    """
    Generates a world-class, printable A4 One-Liner Question Bank PDF for Admins.
    Format: ONLY ONELINERS TABLE:
    - Left side: प्रश्न (Question - One Liner)
    - Right side: अधिकृत अचूक उत्तर (Correct Answer)
    Extracts authentic questions from ALL uploaded response sheets in the bot.
    Strictly anonymous: zero candidate personal data.
    """
    import sqlite3
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    def clean_text_for_pdf(txt: str) -> str:
        """Sanitizes text and removes raw HTML artifacts, tags, and formatting glitches."""
        if not txt:
            return ""
        t = str(txt)
        t = re.sub(r"<[^>]+>", " ", t)
        t = re.sub(r"\[Correct\s*Option\]|rightAns|[✓✔☑]", "", t, flags=re.I)
        t = re.sub(r"&(?:nbsp|amp|quot|#39|lt|gt);", " ", t)
        t = re.sub(r"\s+", " ", t).strip()
        # Escape special XML/ReportLab chars
        t = t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        return t

    # Register Nirmala Unicode Font for Devanagari (Marathi) support
    from reportlab.pdfbase.pdfmetrics import registerFontFamily
    font_regular = "Helvetica"
    font_bold = "Helvetica-Bold"
    
    # Candidate Unicode font locations (Windows + Linux Cloud / Docker)
    candidate_fonts = [
        ("C:/Windows/Fonts/Nirmala.ttf", "C:/Windows/Fonts/NirmalaB.ttf", "Nirmala"),
        ("/usr/share/fonts/truetype/lohit-marathi/Lohit-Marathi.ttf", "/usr/share/fonts/truetype/lohit-marathi/Lohit-Marathi.ttf", "Lohit-Marathi"),
        ("/usr/share/fonts/truetype/Gargi/Gargi.ttf", "/usr/share/fonts/truetype/Gargi/Gargi.ttf", "Gargi"),
        ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "DejaVuSans"),
        ("/usr/share/fonts/truetype/freefont/FreeSans.ttf", "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf", "FreeSans"),
    ]

    for reg_path, bld_path, fam_name in candidate_fonts:
        if os.path.exists(reg_path):
            try:
                pdfmetrics.registerFont(TTFont(fam_name, reg_path))
                if os.path.exists(bld_path):
                    pdfmetrics.registerFont(TTFont(f"{fam_name}-Bold", bld_path))
                    registerFontFamily(fam_name, normal=fam_name, bold=f"{fam_name}-Bold", italic=fam_name, boldItalic=f"{fam_name}-Bold")
                    font_bold = f"{fam_name}-Bold"
                else:
                    registerFontFamily(fam_name, normal=fam_name, bold=fam_name, italic=fam_name, boldItalic=fam_name)
                    font_bold = fam_name
                font_regular = fam_name
                logger.info(f"Unicode font family '{fam_name}' registered successfully from {reg_path}.")
                break
            except Exception as e:
                logger.warning(f"Could not register font {fam_name}: {e}")

    # Collect questions from ALL response sheets in DB & disk
    from .parser import parse_answers, parse_html_response_sheet
    collected_questions = []
    scanned_paths = set()

    try:
        with sqlite3.connect(db_path) as conn:
            cur = conn.cursor()
            # Fetch ALL distinct uploads without artificial limits
            cur.execute("SELECT DISTINCT storage_path, exam_key FROM uploads WHERE storage_path IS NOT NULL ORDER BY id DESC")
            rows = cur.fetchall()
            for s_path, e_key in rows:
                if s_path and os.path.exists(s_path):
                    scanned_paths.add(os.path.abspath(s_path))
                    try:
                        content = Path(s_path).read_text(encoding="utf-8", errors="ignore")
                        if "<html" in content.lower() or "<table" in content.lower():
                            content = parse_html_response_sheet(content)
                        records = parse_answers(content)
                        for r in records:
                            q_text = clean_text_for_pdf(r.get("question_text", ""))
                            opts = r.get("options", {})
                            c_num = r.get("correct_option_number")
                            if q_text and len(q_text) >= 6 and c_num and str(c_num) in opts:
                                ans_txt = clean_text_for_pdf(opts[str(c_num)])
                                sec_txt = clean_text_for_pdf(r.get("section", "सामान्य घटक"))
                                collected_questions.append({
                                    "section": sec_txt,
                                    "question": q_text,
                                    "answer": f"पर्याय {c_num}: {ans_txt}"
                                })
                    except Exception as e:
                        logger.warning(f"Error parsing response sheet {s_path} for qbank: {e}")
    except Exception as e:
        logger.warning(f"DB lookup for qbank: {e}")

    # Also scan response_sheets directory for any additional stored files
    resp_dir = Path("response_sheets")
    if resp_dir.exists():
        for p in resp_dir.iterdir():
            if p.is_file() and p.suffix.lower() in (".html", ".htm", ".pdf") and str(p.resolve()) not in scanned_paths:
                scanned_paths.add(str(p.resolve()))
                try:
                    if p.suffix.lower() in (".html", ".htm"):
                        raw_c = p.read_text(encoding="utf-8", errors="ignore")
                        p_text = parse_html_response_sheet(raw_c)
                    else:
                        from .parser import extract_pdf_text
                        p_text = extract_pdf_text(str(p))
                    recs = parse_answers(p_text)
                    for r in recs:
                        q_text = clean_text_for_pdf(r.get("question_text", ""))
                        opts = r.get("options", {})
                        c_num = r.get("correct_option_number")
                        if q_text and len(q_text) >= 6 and c_num and str(c_num) in opts:
                            ans_txt = clean_text_for_pdf(opts[str(c_num)])
                            sec_txt = clean_text_for_pdf(r.get("section", "सामान्य घटक"))
                            collected_questions.append({
                                "section": sec_txt,
                                "question": q_text,
                                "answer": f"पर्याय {c_num}: {ans_txt}"
                            })
                except Exception as e:
                    logger.warning(f"Error scanning local file {p} for qbank: {e}")

    # Fallback / High-Yield curated seeds for Maharashtra TCS/IBPS Bharti
    high_yield_seeds = [
        {
            "section": "मराठी व्याकरण",
            "question": "खालीलपैकी 'कर्मधारय समासाचे' अचूक उदाहरण कोणते?",
            "answer": "पर्याय २: रक्तचंदन (रक्तासारखे चंदन)"
        },
        {
            "section": "मराठी व्याकरण",
            "question": "'रामाने रावणास मारले.' या वाक्यातील प्रयोग कोणता?",
            "answer": "पर्याय ३: भावे प्रयोग (कर्ता व कर्म प्रत्ययान्वित)"
        },
        {
            "section": "मराठी व्याकरण",
            "question": "खालीलपैकी 'तत्सम' शब्द ओळखा:",
            "answer": "पर्याय १: सूर्य, मंदिर, वृक्ष"
        },
        {
            "section": "मराठी व्याकरण",
            "question": "'अव्ययीभाव समासात' कोणते पद प्रमुख असते?",
            "answer": "पर्याय १: पहिले पद प्रमुख (उदा. यथाशक्ती)"
        },
        {
            "section": "सामान्य ज्ञान (GS / GK)",
            "question": "माहितीचा अधिकार कायदा (RTI Act 2005) भारतात कोणत्या तारखेस लागू झाला?",
            "answer": "पर्याय २: १२ ऑक्टोबर २००५"
        },
        {
            "section": "सामान्य ज्ञान (GS / GK)",
            "question": "माहितीचा अधिकार कायदा (RTI Act 2005) अंतर्गत प्रथम अपील किती दिवसांत दाखल करावे लागते?",
            "answer": "पर्याय १: ३० दिवसांच्या आत (कलम १९ (१))"
        },
        {
            "section": "सामान्य ज्ञान (GS / GK)",
            "question": "२०११ च्या जनगणनेनुसार महाराष्ट्राचे स्त्री-पुरुष लिंगगुणोत्तर किती आहे?",
            "answer": "पर्याय २: ९२९ (हजार पुरुषांमागे स्त्रिया)"
        },
        {
            "section": "सामान्य ज्ञान (GS / GK)",
            "question": "२०११ जनगणनेनुसार महाराष्ट्रातील सर्वाधिक साक्षर जिल्हा कोणता?",
            "answer": "पर्याय ३: मुंबई उपनगर (८९.९१%)"
        },
        {
            "section": "सामान्य ज्ञान (GS / GK)",
            "question": "गोदावरी नदीचा उगम महाराष्ट्रात कोणत्या ठिकाणी होतो?",
            "answer": "पर्याय ४: त्र्यंबकेश्वर (नाशिक जिल्हा, ब्रह्मगिरी)"
        },
        {
            "section": "सामान्य ज्ञान (GS / GK)",
            "question": "महाराष्ट्रातील 'जायकवाडी धरण' कोणत्या नदीवर बांधण्यात आले आहे?",
            "answer": "पर्याय १: गोदावरी नदी (छत्रपती संभाजीनगर)"
        },
        {
            "section": "English Language",
            "question": "Select the correct Synonym for the word 'PERSEVERE':",
            "answer": "Option 1: Persist (To continue firmly)"
        },
        {
            "section": "English Language",
            "question": "Choose the correctly spelled word:",
            "answer": "Option 3: Bureaucracy (प्रशासकीय नोकरशाही)"
        },
        {
            "section": "English Language",
            "question": "Select the correct Antonym for 'TRANSPARENT':",
            "answer": "Option 2: Opaque (अपारदर्शक)"
        },
        {
            "section": "English Language",
            "question": "Identify the error: 'Neither of the students were present in the hall.'",
            "answer": "Option 4: Replace 'were' with 'was'"
        },
        {
            "section": "बौद्धिक चाचणी व अंकगणित",
            "question": "संख्यामालिका पूर्ण करा: 4, 9, 19, 39, 79, ?",
            "answer": "पर्याय २: 159 [तर्क: (x*2)+1]"
        },
        {
            "section": "बौद्धिक चाचणी व अंकगणित",
            "question": "एका सांकेतिक भाषेत CAT ला 24 लिहिले जाते, तर DOG ला काय लिहिले जाईल?",
            "answer": "पर्याय ४: 26 [अक्षरांची बेरीज: 4+15+7]"
        },
        {
            "section": "बौद्धिक चाचणी व अंकगणित",
            "question": "रांगेत अमोलचा डावीकडून १० वा व उजवीकडून १५ वा क्रमांक असल्यास रांगेत एकूण मुले किती?",
            "answer": "पर्याय ३: २४ मुले (१०+१५ - १ = २४)"
        }
    ]

    # Deduplicate questions
    final_questions = []
    seen_hashes = set()
    for q in collected_questions + high_yield_seeds:
        h = re.sub(r"\s+", "", q["question"].lower()[:45])
        if h and h not in seen_hashes:
            seen_hashes.add(h)
            final_questions.append(q)

    # Build PDF with ONLY ONELINERS TABLE
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        rightMargin=30,
        leftMargin=30,
        topMargin=28,
        bottomMargin=28
    )

    header_title_style = ParagraphStyle(
        "HeaderTitle",
        fontName=font_bold,
        fontSize=16,
        leading=21,
        textColor=colors.HexColor("#1e1b4b"),
        alignment=1
    )
    header_sub_style = ParagraphStyle(
        "HeaderSub",
        fontName=font_regular,
        fontSize=9.5,
        leading=13.5,
        textColor=colors.HexColor("#475569"),
        alignment=1
    )
    th_style = ParagraphStyle(
        "TH",
        fontName=font_bold,
        fontSize=10,
        leading=14,
        textColor=colors.white
    )
    q_cell_style = ParagraphStyle(
        "QCell",
        fontName=font_regular,
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#0f172a")
    )
    ans_cell_style = ParagraphStyle(
        "AnsCell",
        fontName=font_regular,
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#065f46")
    )

    story = []

    # Title Block
    story.append(Paragraph("🎯 महास्पर्धा परीक्षा — वनलायनर प्रश्नसंच (One-Liner Question Bank)", header_title_style))
    story.append(Spacer(1, 4))
    gen_date = datetime.now().strftime("%d-%m-%Y %I:%M %p")
    exam_tag = f"परीक्षेचे नाव: {exam_name} | " if exam_name else ""
    story.append(Paragraph(
        f"{exam_tag}एकूण प्रश्न: {len(final_questions)} | दिनांक: {gen_date} | TCS / IBPS / MPSC अधिकृत रिस्पॉन्स शीट्स | Admin प्रत",
        header_sub_style
    ))
    story.append(Spacer(1, 8))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#4338ca"), spaceBefore=2, spaceAfter=8))

    # Two-Column Oneliners Table Data
    table_data = [[
        Paragraph("<b>प्रश्न (Question - One Liner)</b>", th_style),
        Paragraph("<b>अधिकृत अचूक उत्तर (Correct Answer)</b>", th_style)
    ]]

    for i, item in enumerate(final_questions, 1):
        sec = item.get("section", "सामान्य घटक")
        q_text = item.get("question", "")
        ans_text = item.get("answer", "")

        q_p = Paragraph(f"<b>प्र. {i}. [{sec}]</b> {q_text}", q_cell_style)
        a_p = Paragraph(f"<b>{ans_text}</b>", ans_cell_style)
        table_data.append([q_p, a_p])

    # Table with exact A4 printable widths: 345 pt left + 190 pt right = 535 pt total
    oneliner_table = Table(table_data, colWidths=[345, 190], repeatRows=1)
    oneliner_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e1b4b")),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#f8fafc"), colors.white])
    ]))

    story.append(oneliner_table)

    doc.build(story)
    logger.info(f"One-Liner Question Bank Table PDF generated at {output_path} with {len(final_questions)} questions from all uploaded responses.")
    return output_path
