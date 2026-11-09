"""
Content Faculty Force Agents:
Specialized Senior Academic Chairs for Maharashtra Government Exam Content.
- MarathiSeniorFaculty (Senior Professor in Marathi Vyakaran)
- EnglishSeniorFaculty (Chair of English Grammar & Comprehension)
- MathsReasoningSeniorFaculty (Head of Quantitative Aptitude & Logic)
- CurrentAffairsSeniorEditor (Chief Editor for Monthly 200 MCQs, Half-Yearly & Yearly Compendiums)
"""

import logging
from typing import Any, Dict, List

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
        if isinstance(res, list) and len(res) > 0:
            return res
        return self._get_offline_grammar_capsule(topic, count)

    def _get_offline_grammar_capsule(self, topic: str, count: int = 10) -> List[Dict[str, Any]]:
        offline_bank = [
            {
                "question": "खालील वाक्यातील 'प्रयोग' ओळखा: 'रामाने रावणास मारले.'",
                "options": ["कर्तरी प्रयोग", "कर्मणी प्रयोग", "भावे प्रयोग", "मिश्र प्रयोग"],
                "correct_option": 2,
                "explanation": "कर्त्याला (रामाने - तृतीया) व कर्माला (रावणास - द्वितीया) दोन्हीला विभक्ती प्रत्यय असून क्रियापद तृतीयपुरुषी, नपुंसकलिंगी, एकवचनी (मारले) आहे. म्हणून हा भावे प्रयोग आहे.",
                "shortcut_rule": "कर्ता + कर्म दोन्ही सप्रत्ययी = १००% भावे प्रयोग."
            },
            {
                "question": "'सूर्योदय' या शब्दाचा योग्य संधी विग्रह कोणता?",
                "options": ["सूर्य + उदय", "सूर्यो + दय", "सूर्य + दय", "सूर्या + उदय"],
                "correct_option": 0,
                "explanation": "अ/आ + उ = ओ (गुणादेश स्वरसंधी). सूर्य (अ) + उदय (उ) = सूर्योदय.",
                "shortcut_rule": "अ/आ पुढे इ/उ/ऋ आल्यास अनुक्रमे ए/ओ/अर् होतात (गुणादेश)."
            },
            {
                "question": "खालीलपैकी 'तत्पुरुष' समासाचे अचूक उदाहरण कोणते?",
                "options": ["पापपुण्य", "राजवाडा", "नीलकंठ", "प्रतिदिन"],
                "correct_option": 1,
                "explanation": "'राजवाडा' = राजाचा वाडा (षष्ठी तत्पुरुष). ज्या समासात दुसरे पद प्रधान असते व विभक्ती प्रत्ययाचा लोप होतो त्यास तत्पुरुष समास म्हणतात.",
                "shortcut_rule": "दुसरे पद महत्त्वाचे + विभक्ती अर्थ = तत्पुरुष समास."
            },
            {
                "question": "खालील वाक्याचा 'काळ' ओळखा: 'मी दररोज सकाळी वर्तमानपत्र वाचत असे.'",
                "options": ["अपूर्ण भूतकाळ", "रीती भूतकाळ", "पूर्ण भूतकाळ", "साधा भूतकाळ"],
                "correct_option": 1,
                "explanation": "भूतकाळात सतत घडणारी रीत किंवा सवय दर्शवण्यासाठी 'त + असे' रचना येते, म्हणून हा रीती भूतकाळ (चालू-पूर्ण भूतकाळ) आहे.",
                "shortcut_rule": "धातू + 'त' + असे/असायचा = रीती भूतकाळ."
            },
            {
                "question": "'अनुज' या शब्दाचा अचूक विरुद्धार्थी शब्द कोणता?",
                "options": ["अग्रज", "कनिष्ठ", "ज्येष्ठ", "अनुपम"],
                "correct_option": 0,
                "explanation": "अनुज म्हणजे मागे जन्मलेला (लहान भाऊ). अग्रज म्हणजे आधी जन्मलेला (मोठा भाऊ).",
                "shortcut_rule": "अग्र (पुढे/आधी) विरुद्ध अनु (मागे/नंतर)."
            },
            {
                "question": "'त्याने निबंध लिहिला आहे.' या वाक्यातील काळ ओळखा.",
                "options": ["साधा वर्तमानकाळ", "पूर्ण वर्तमानकाळ", "चालू वर्तमानकाळ", "रीती वर्तमानकाळ"],
                "correct_option": 1,
                "explanation": "क्रिया वर्तमानात नुकतीच पूर्ण झाली आहे (लिहिला + आहे = पूर्ण वर्तमानकाळ).",
                "shortcut_rule": "भूतकाळी धातुसाधित रूप + 'आहे' = पूर्ण वर्तमानकाळ."
            },
            {
                "question": "खालीलपैकी 'शुद्ध शब्द' ओळखा:",
                "options": ["कविइत्री", "कवयित्री", "कवियत्री", "कवयित्री"],
                "correct_option": 1,
                "explanation": "'कवयित्री' हे शुद्ध लेखन नियमांनुसार अचूक रूप आहे. 'य' ला पहिली वेलांटी (इ) व 'त्र' ला दुसरी वेलांटी (ई) असते.",
                "shortcut_rule": "कव + यित्री (कवयित्री) - TCS/IBPS वारंवार विचारला जाणारा शब्द."
            },
            {
                "question": "'पांढरा कावळा' या अलंकारिक शब्दाचा योग्य अर्थ सांगा:",
                "options": ["खूप हुशार व्यक्ती", "निसर्गातील चमत्कार", "अस्तित्वात नसलेली गोष्ट", "पांढरा शुभ्र पक्षी"],
                "correct_option": 2,
                "explanation": "ज्या गोष्टीचे अस्तित्व निसर्गात शक्य नाही किंवा कधीही आढळत नाही अशा असंभवनीय गोष्टीला 'पांढरा कावळा' म्हणतात.",
                "shortcut_rule": "असंभवनीय गोष्ट = पांढरा कावळा."
            }
        ]
        return offline_bank[:count]

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
        if isinstance(res, list) and len(res) > 0:
            return res
        return self._get_offline_error_spotting_drill(count)

    def _get_offline_error_spotting_drill(self, count: int = 10) -> List[Dict[str, Any]]:
        offline_bank = [
            {
                "question": "Identify the segment containing a grammatical error: Neither the teacher (A) / nor the students (B) / was present in the hall (C) / No error (D)",
                "options": ["Neither the teacher", "nor the students", "was present in the hall", "No error"],
                "correct_option": 2,
                "explanation": "When two subjects are joined by 'Neither... nor', the verb agrees with the closer subject. 'The students' is plural, so the verb must be 'were present', not 'was present'.",
                "grammar_rule": "Subject-Verb Inversion: With 'neither... nor', verb agrees with the nearest subject."
            },
            {
                "question": "Find the error: She is senior (A) / than me (B) / in government service (C) / No error (D)",
                "options": ["She is senior", "than me", "in government service", "No error"],
                "correct_option": 1,
                "explanation": "Adjectives ending in '-ior' (senior, junior, superior, inferior, prior) take the preposition 'to', never 'than'. The correct phrase is 'senior to me'.",
                "grammar_rule": "Latin comparatives (-ior) always take 'to', not 'than'."
            },
            {
                "question": "Spot the error: Scarcely had he (A) / entered the room (B) / than the phone rang (C) / No error (D)",
                "options": ["Scarcely had he", "entered the room", "than the phone rang", "No error"],
                "correct_option": 2,
                "explanation": "'Scarcely... when' and 'Hardly... when' are correlative conjunctions. 'Than' is used only with 'No sooner... than'. Correct phrase: 'when the phone rang'.",
                "grammar_rule": "Correlative conjunction pair: Scarcely/Hardly is followed by 'when', never 'than'."
            },
            {
                "question": "Find the error: One of the candidate (A) / who cleared the preliminary exam (B) / was awarded a medal (C) / No error (D)",
                "options": ["One of the candidate", "who cleared the preliminary exam", "was awarded a medal", "No error"],
                "correct_option": 0,
                "explanation": "'One of the' is always followed by a plural noun and a singular verb. It should be 'One of the candidates'.",
                "grammar_rule": "Syntax rule: 'One of the' + Plural Noun + Singular Verb."
            },
            {
                "question": "Spot the error: Each of the girls (A) / have performed (B) / exceptionally well in the debate (C) / No error (D)",
                "options": ["Each of the girls", "have performed", "exceptionally well in the debate", "No error"],
                "correct_option": 1,
                "explanation": "'Each of' takes a singular verb. The correct auxiliary is 'has performed', not 'have performed'.",
                "grammar_rule": "Distributive pronoun: 'Each of' requires a singular verb."
            }
        ]
        return offline_bank[:count]

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

    async def generate_shortcut_drill(self, topic: str = "Quantitative Aptitude", count: int = 10) -> List[Dict[str, Any]]:
        task = (
            f"Generate {count} TCS/IBPS Quantitative Aptitude & Reasoning questions on '{topic}'.\n"
            "Each item must contain:\n"
            "- 'question': Clear question text in Marathi/English\n"
            "- 'options': 4 choices\n"
            "- 'correct_option': Index 0 to 3\n"
            "- 'traditional_solution': Step-by-step method\n"
            "- 'shortcut_trick': 15-second mental math or elimination trick\n"
            "Return JSON array."
        )
        res = await self.execute_task(task, temperature=0.3, expect_json=True)
        if isinstance(res, list) and len(res) > 0:
            return res
        return self._get_offline_maths_drill(topic, count)

    def _get_offline_maths_drill(self, topic: str = "General", count: int = 10) -> List[Dict[str, Any]]:
        offline_bank = [
            {
                "question": "एका वस्तूची किंमत २०% वाढवली आणि नंतर २०% कमी केली, तर एकूण व्यवहारात शेकडा नफा किंवा तोटा किती होईल?",
                "options": ["शेकडा ४% तोटा", "शेकडा ४% नफा", "ना नफा ना तोटा", "शेकडा २% तोटा"],
                "correct_option": 0,
                "traditional_solution": "समजा मूळ किंमत १०० रु. २०% वाढ = १२० रु. १२० चे २०% कमी = २४ रु. अंतिम किंमत = १२० - २४ = ९६ रु. तोटा = १०० - ९६ = ४%.",
                "shortcut_trick": "समान टक्के वाढ व घट असल्यास नेहमी तोटाच होतो = (x/10)^2 = (20/10)^2 = 2^2 = 4% तोटा."
            },
            {
                "question": "A एक काम १२ दिवसांत पूर्ण करतो व B तेच काम २४ दिवसांत पूर्ण करतो. दोघे मिळून ते काम किती दिवसांत पूर्ण करतील?",
                "options": ["६ दिवस", "८ दिवस", "१० दिवस", "१६ दिवस"],
                "traditional_solution": "A चे १ दिवसाचे काम = १/१२. B चे १ दिवसाचे काम = १/२४. एकूण १ दिवसाचे काम = १/१२ + १/२४ = ३/२४ = १/८. एकूण दिवस = ८.",
                "shortcut_trick": "AB / (A + B) = (12 × 24) / (12 + 24) = 288 / 36 = 8 दिवस (१० सेकंद ट्रिक!)."
            },
            {
                "question": "जर २ : ३ :: ८ : x असेल, तर x ची किंमत किती?",
                "options": ["१०", "१२", "१४", "१६"],
                "traditional_solution": "२/३ = ८/x => २x = २४ => x = १२.",
                "shortcut_trick": "मध्य पदांचा गुणाकार = अंत्य पदांचा गुणाकार (3 × 8) / 2 = 12."
            },
            {
                "question": "एका वर्तुळाची त्रिज्या तिप्पट केल्यास त्याचे क्षेत्रफळ किती पट होईल?",
                "options": ["३ पट", "६ पट", "९ पट", "२७ पट"],
                "traditional_solution": "मूळ क्षेत्रफळ = πr^2. नवीन त्रिज्या = 3r. नवीन क्षेत्रफळ = π(3r)^2 = 9πr^2 (९ पट).",
                "shortcut_trick": "क्षेत्रफळ प्रमाण = (पट)^2 = 3^2 = 9 पट."
            }
        ]
        return offline_bank[:count]

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

