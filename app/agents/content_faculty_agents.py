"""
Content Faculty Force Agents:
Specialized Senior Academic Chairs for Maharashtra Government Exam Content.
- MarathiSeniorFaculty (Senior Professor in Marathi Vyakaran)
- EnglishSeniorFaculty (Chair of English Grammar & Comprehension)
- MathsReasoningSeniorFaculty (Head of Quantitative Aptitude & Logic)
- CurrentAffairsSeniorEditor (Chief Editor for Monthly 200 MCQs, Half-Yearly & Yearly Compendiums)
"""

import os
import json
import logging
from typing import List, Dict, Any
from .base_agent import BaseSeniorAgent

logger = logging.getLogger(__name__)

class MarathiSeniorFaculty(BaseSeniorAgent):
    """Senior Professor & Author of TCS/IBPS Marathi Vyakaran Guidebooks."""

    def __init__(self):
        super().__init__(
            name="Prof. Ramchandra More (Marathi Vyakaran Ratna)",
            role="Senior Chair of Marathi Language & Grammar Research",
            seniority="Emeritus Professor (22+ Years in MPSC & Saralsewa Exam Pedagogy)",
            core_competencies=[
                "TCS/IBPS Pattern question design (वाक्यपृथक्करण, काळ, प्रयोग, समास, संधी)",
                "Subtle grammatical objections & official reference citing (मो. रा. वाळंबे / दादोबा पांडुरंग)",
                "High-scoring memory mnemonics for Marathi vocabulary (समानार्थी, विरुद्धार्थी, म्हणी)"
            ],
            system_instruction="Explain all concepts in authentic, lucid, flawless Marathi with rigorous grammatical rules."
        )

    async def generate_grammar_capsule(self, topic: str, count: int = 10) -> List[Dict[str, Any]]:
        task = (
            f"Generate {count} TCS/IBPS high-yield Marathi Grammar questions on topic '{topic}'.\n"
            "Each item must have:\n"
            "- 'question': Clear question text in Marathi\n"
            "- 'options': List of 4 distinct choices\n"
            "- 'correct_option': Index 0 to 3\n"
            "- 'explanation': In-depth grammatical rule explaining why the right option is correct and others are wrong\n"
            "- 'shortcut_rule': 1-line golden tip\n"
            "Return JSON array of question objects."
        )
        res = await self.execute_task(task, temperature=0.3, expect_json=True)
        return res if isinstance(res, list) else []

class EnglishSeniorFaculty(BaseSeniorAgent):
    """Senior Faculty for Competitive English Language & Verbal Ability."""

    def __init__(self):
        super().__init__(
            name="Dr. Elizabeth Rao (English Verbal Chair)",
            role="Senior Professor of Competitive English Pedagogy",
            seniority="Principal English Specialist (18+ Years Training Top Rankers)",
            core_competencies=[
                "TCS/IBPS Error Spotting, Sentence Improvement & Cloze Tests",
                "Idioms, Phrasal Verbs & Vocabulary Mnemonics",
                "Reading Comprehension logic & Para Jumbles"
            ],
            system_instruction="Provide comprehensive explanations highlighting root causes of grammatical errors."
        )

    async def generate_error_spotting_drill(self, count: int = 10) -> List[Dict[str, Any]]:
        task = (
            f"Generate {count} TCS/IBPS Error Spotting questions with high trap rates.\n"
            "Include 'question', 'options', 'correct_option', 'explanation', and 'grammar_rule'.\n"
            "Return JSON array."
        )
        res = await self.execute_task(task, temperature=0.3, expect_json=True)
        return res if isinstance(res, list) else []

class MathsReasoningSeniorFaculty(BaseSeniorAgent):
    """Senior Specialist in TCS/IBPS Quantitative Aptitude & Logical Reasoning."""

    def __init__(self):
        super().__init__(
            name="Er. Anand Deshmukh (Maths & Logic Wizard)",
            role="Chief Mentor of Quantitative Shortcuts & Analytical Reasoning",
            seniority="Senior Reasoning Director (16+ Years in Banking & State Government Testing)",
            core_competencies=[
                "15-second shortcut tricks for Percentage, Ratio, Time & Work",
                "TCS puzzle grids, Circular/Linear Seating, Syllogisms",
                "Data Interpretation & Speed Math calculations"
            ],
            system_instruction="Include step-by-step traditional method AND instant 15-second shortcut trick for every question."
        )

class CurrentAffairsSeniorEditor(BaseSeniorAgent):
    """
    Chief Editor & Senior Research Lead for Monthly Top 200 MCQs,
    Half-Yearly, and Yearly Maharashtra & National Current Affairs.
    """

    def __init__(self):
        super().__init__(
            name="Siddharth Shinde (Editor-in-Chief, Current Affairs Division)",
            role="Chief Editor of Government Examination Current Affairs Compendiums",
            seniority="Senior Research Lead (15+ Years Tracking Maharashtra Government & National Schemes)",
            core_competencies=[
                "Curating Top 200 MCQs per month strictly matching TCS & IBPS exam weightage",
                "Maharashtra specific schemes (Ladki Bahin, Jalyukt Shivar, Budget allocations)",
                "Sports, Appointments, Science & Technology, Awards, and International Summits",
                "Generating publication-ready high-retention monthly, half-yearly and yearly compendiums"
            ],
            system_instruction=(
                "Curate strictly authoritative, fact-checked, high-yield current affairs MCQs. "
                "Provide detailed bilingual explanations (Marathi + English key terms) with memory hooks."
            )
        )

    async def generate_monthly_top_mcqs(self, month: str, year: str, count: int = 15) -> List[Dict[str, Any]]:
        """
        Generates a curated batch of Top MCQs with TCS/IBPS weightage for the specified month/year.
        """
        task = (
            f"Generate a batch of {count} high-yield, authentic Current Affairs MCQs for {month} {year} "
            "for Maharashtra competitive exams (TCS/IBPS: Talathi, ZP, Police Bharti, Arogya Vibhag).\n\n"
            "Mix of categories:\n"
            "1. Maharashtra State News & Schemes\n"
            "2. National Summits & Appointments\n"
            "3. Sports, Medals & Honours\n"
            "4. Science & Tech, Defence Exercises\n"
            "5. Awards & Cultural Recognitions\n\n"
            "For each question, return an object:\n"
            "- 'id': integer\n"
            "- 'category': category name\n"
            "- 'question': Marathi question with clear English terminology\n"
            "- 'options': [A, B, C, D]\n"
            "- 'correct_option': index 0-3\n"
            "- 'answer_text': correct option text\n"
            "- 'explanation': 2-3 line insightful explanation in Marathi\n"
            "- 'exam_takeaway': 1-line key fact to remember\n\n"
            "Return JSON array."
        )
        res = await self.execute_task(task, temperature=0.3, expect_json=True)
        if isinstance(res, list) and len(res) > 0:
            return res

        # Offline fallback batch
        return [
            {
                "id": 1,
                "category": "महाराष्ट्र विशेष (Maharashtra Specific)",
                "question": "महाराष्ट्र शासनाने महिलांच्या आर्थिक सक्षमीकरणासाठी सुरू केलेल्या 'मुख्यमंत्री माझी लाडकी बहीण योजने'अंतर्गत दरमहा किती रुपयांची आर्थिक मदत दिली जाते?",
                "options": ["₹१,०००", "₹१,५००", "₹२,०००", "₹२,५००"],
                "correct_option": 1,
                "answer_text": "₹१,५००",
                "explanation": "महाराष्ट्र शासनाने अंतरिम अर्थसंकल्प २०२४-२५ मध्ये २१ ते ६५ वयोगटातील पात्र महिलांसाठी 'मुख्यमंत्री माझी लाडकी बहीण योजना' जाहीर केली असून दरमहा ₹१,५०० थेट बँक खात्यात जमा केले जातात.",
                "exam_takeaway": "वयोगट: २१ ते ६५ वर्षे | वार्षिक उत्पन्न मर्यादा: ₹२.५ लाख"
            },
            {
                "id": 2,
                "category": "क्रीडा व पुरस्कार (Sports & Honours)",
                "question": "पॅरिस पॅरालिम्पिक २०२४ मध्ये भालाफेक (Javelin Throw) F64 प्रकारात सलग दुसरे सुवर्णपदक जिंकणारा भारतीय खेळाडू कोण?",
                "options": ["नीरज चोप्रा", "सुमित अंतिल", "देवेंद्र झाझरिया", "निषाद कुमार"],
                "correct_option": 1,
                "answer_text": "सुमित अंतिल",
                "explanation": "सुमित अंतिल यांनी पॅरिस पॅरालिम्पिक २०२४ मध्ये ७०.५९ मीटर भाला फेकून विश्वविक्रमासह सलग दुसरे पॅरालिम्पिक सुवर्णपदक पटकावले.",
                "exam_takeaway": "सुमित अंतिल यांनी टोकियो २०२० आणि पॅरिस २०२४ अशा दोन्ही ऑलिम्पिकमध्ये सुवर्ण पटकावले आहे."
            },
            {
                "id": 3,
                "category": "विज्ञान व तंत्रज्ञान (Science & Technology)",
                "question": "भारतीय अंतराळ संशोधन संस्था (ISRO) च्या आगामी 'गगनयान' मोहिमेसाठी निवडलेल्या अंतराळवीरांपैकी कोणाची नियुक्ती आंतरराष्ट्रीय अंतराळ स्थानकावर (ISS) जाण्यासाठी करण्यात आली आहे?",
                "options": ["ग्रुप कॅप्टन शुभांशू शुक्ला", "ग्रुप कॅप्टन प्रशांत नायर", "ग्रुप कॅप्टन अंगद प्रताप", "विंग कमांडर अजित कृष्णन"],
                "correct_option": 0,
                "answer_text": "ग्रुप कॅप्टन शुभांशू शुक्ला",
                "explanation": "इस्रो आणि नासाच्या संयुक्त मोहिमेअंतर्गत ॲक्सिओम-४ (Axiom-4) मोहिमेसाठी ग्रुप कॅप्टन शुभांशू शुक्ला यांची मुख्य अंतराळवीर म्हणून निवड झाली आहे.",
                "exam_takeaway": "राकेश शर्मा (१९८४) नंतर अंतराळात जाणारे शुभांशू शुक्ला हे दुसरे भारतीय ठरतील."
            }
        ]

