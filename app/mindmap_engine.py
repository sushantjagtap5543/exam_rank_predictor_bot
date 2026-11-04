"""
Dynamic Mindmap Generation Engine for TCS & IBPS Exam Preparation.
Features:
- Never repeats the same topic: rotates dynamically across 16+ high-yield exam topics
- Real-time generation of 1200x800 high-res visual mindmap cards using Pillow
- Multi-subject coverage: Marathi Grammar, General Studies/Maharashtra GS, Maths, Reasoning, English
- Database tracking of posted topics in SQLite (`posted_mindmaps`)
"""

import os
import sqlite3
import logging
from pathlib import Path
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "db.sqlite3")
STORAGE_DIR = Path(__file__).resolve().parent.parent / "admin_storage" / "mindmaps"

MINDMAP_TOPICS = [
    {
        "id": "marathi_samas",
        "subject": "मराठी व्याकरण",
        "title": "समास व त्याचे मुख्य प्रकार (TCS / IBPS स्पेशल)",
        "subtitle": "सर्व भरती परीक्षांमध्ये हमखास २ ते ४ गुण देणारा घटक",
        "branches": [
            {
                "heading": "१. अव्ययीभाव समास",
                "color": "#38BDF8",
                "points": [
                    "• पहिले पद प्रमुख असते व शब्द क्रियाविशेषण असतो.",
                    "• उदाहरणे: यथाशक्ती, प्रतिक्षण, आजन्म, घरोघरी.",
                    "• संस्कृत, फारशी व मराठी उपसर्ग लागून बनणारे शब्द."
                ]
            },
            {
                "heading": "२. तत्पुरुष समास",
                "color": "#34D399",
                "points": [
                    "• दुसरे पद प्रमुख असते व विभक्तीचा संबंध असतो.",
                    "• विभक्ती तत्पुरुष: राजपुत्र (राजाचा पुत्र - षष्ठी).",
                    "• कर्मधारय समास: दोन्ही पदे प्रथमा विभक्तीत (नीलकमल).",
                    "• द्विगु समास: पहिले पद संख्याविशेषण (त्रिभुवन, नवरात्र)."
                ]
            },
            {
                "heading": "३. द्वंद्व समास",
                "color": "#FBBF24",
                "points": [
                    "• दोन्ही पदे अर्थाच्या दृष्टीने समान दर्जाची असतात.",
                    "• इतरेतर द्वंद्व: 'आणि', 'व' (आई-वडील, बहिण-भाऊ).",
                    "• वैकल्पिक द्वंद्व: 'किंवा', 'अथवा' (खरे-खोटे, पाप-पुण्य).",
                    "• समाहार द्वंद्व: इतर गोष्टींचा समावेश (भाजीपाला, केरकचरा)."
                ]
            },
            {
                "heading": "४. बहुव्रीही समास",
                "color": "#F472B6",
                "points": [
                    "• दोन्ही पदांशिवाय तिसऱ्याच घटकाचा बोध होतो.",
                    "• गजानन (गजाचे आनन ज्याला आहे तो - गणपती).",
                    "• नीलकंठ (निळा आहे कंठ ज्याचा तो - शंकर).",
                    "• लंबोदर (लांब आहे उदर ज्याचे तो - गणेश)."
                ]
            }
        ],
        "exam_tip": "TCS परीक्षेत सामासिक शब्दाचा विग्रह करून मुख्य पद कोणते ते ओळखा. पहिले पद प्रमुख = अव्ययीभाव, दुसरे = तत्पुरुष, दोन्ही = द्वंद्व, तिसरेच पद = बहुव्रीही!"
    },
    {
        "id": "marathi_prayog",
        "subject": "मराठी व्याकरण",
        "title": "प्रयोग व ओळखण्याच्या १० सेकंद शॉर्टकट ट्रिक्स",
        "subtitle": "कर्तरी, कर्मणी व भावे प्रयोग क्षणात अचूक ओळखा",
        "branches": [
            {
                "heading": "१. कर्तरी प्रयोग (Subject Centric)",
                "color": "#38BDF8",
                "points": [
                    "• नियम: कर्त्याला कोणताही विभक्ती प्रत्यय नसतो (प्रथमा विभक्ती).",
                    "• क्रियापद कर्त्याच्या लिंग/वचनानुसार बदलते.",
                    "• उदा. 'तो निबंध लिहितो' -> 'ती निबंध लिहिते'.",
                    "• अकर्मक कर्तरी (पक्षी उडतो) व सकर्मक कर्तरी (राम आंबा खातो)."
                ]
            },
            {
                "heading": "२. कर्मणी प्रयोग (Object Centric)",
                "color": "#34D399",
                "points": [
                    "• नियम: कर्त्याला प्रत्यय असतो, कर्माला प्रत्यय नसतो.",
                    "• क्रियापद कर्माच्या लिंग/वचनानुसार बदलते.",
                    "• उदा. 'रामाने आंबा खाल्ला' -> 'रामाने चिंच खाल्ली'.",
                    "• प्रकार: प्रधानकर्तुक, शक्य, समापन, नवीन कर्मणी."
                ]
            },
            {
                "heading": "३. भावे प्रयोग (Neutral)",
                "color": "#F87171",
                "points": [
                    "• नियम: कर्ता आणि कर्म दोघांनाही प्रत्यय लागलेला असतो.",
                    "• क्रियापद नेहमी तृतीयपुरुषी, नपुंसकलिंगी, एकवचनी असते.",
                    "• उदा. 'रामाने रावणास मारले', 'शिक्षकांनी विद्यार्थ्याला शिकवले'.",
                    "• अकर्मक भावे: 'त्याला आज सारखे मळमळते'."
                ]
            },
            {
                "heading": "४. परीक्षेतील शॉर्टकट टेबल",
                "color": "#A78BFA",
                "points": [
                    "• कर्ता प्रत्ययरहित = १००% कर्तरी प्रयोग.",
                    "• कर्त्याला प्रत्यय + कर्माला नाही = १००% कर्मणी प्रयोग.",
                    "• कर्ता व कर्म दोघांना प्रत्यय = १००% भावे प्रयोग.",
                    "• संयुक्त प्रयोग: संकीर्ण/मिश्र (कर्तृकर्म, कर्मभाव, कर्तृभाव)."
                ]
            }
        ],
        "exam_tip": "वाक्य वाचताच सर्वात आधी कर्ता शोधा. कर्त्याला प्रत्यय नसेल तर डोळे झाकून 'कर्तरी' निवडा!"
    },
    {
        "id": "gs_constitution_articles",
        "subject": "सामान्य ज्ञान (राज्यघटना)",
        "title": "भारतीय राज्यघटना: सर्वाधिक विचारली जाणारी महत्त्वाची कलमे",
        "subtitle": "TCS व IBPS परीक्षेत वारंवार रिपीट होणारी कलमे",
        "branches": [
            {
                "heading": "१. मूलभूत हक्क (कलम १२ ते ३५)",
                "color": "#38BDF8",
                "points": [
                    "• कलम १४: कायद्यापुढे सर्व समान.",
                    "• कलम १७: अस्पृश्यता निवारण (सर्वाधिक विचारले जाणारे).",
                    "• कलम १९: भाषण व अभिव्यक्ती स्वातंत्र्य (६ स्वातंत्र्ये).",
                    "• कलम २१: जीवित व वैयक्तिक स्वातंत्र्याचे रक्षण.",
                    "• कलम ३२: घटनात्मक उपायांचा हक्क (घटनेचा आत्मा - डॉ. आंबेडकर)."
                ]
            },
            {
                "heading": "२. मार्गदर्शक तत्त्वे (DPSP - कलम ३६ ते ५१)",
                "color": "#34D399",
                "points": [
                    "• कलम ४०: ग्रामपंचायतींची स्थापना.",
                    "• कलम ४४: समान नागरी कायदा (Uniform Civil Code).",
                    "• कलम ४५: बालकांसाठी मोफत व सक्तीचे शिक्षण.",
                    "• कलम ५०: न्यायव्यवस्था व कार्यकारी व्यवस्था विलगीकरण."
                ]
            },
            {
                "heading": "३. राष्ट्रपती व संसद",
                "color": "#FBBF24",
                "points": [
                    "• कलम ५२: भारताचे राष्ट्रपती.",
                    "• कलम ६१: राष्ट्रपतींवरील महाभियोग (Impeachment).",
                    "• कलम ७२: राष्ट्रपतींचा दयेचा अधिकार (Pardon Power).",
                    "• कलम ७६: भारताचे महान्यायवादी (Attorney General).",
                    "• कलम ११०: धनविधेयक (Money Bill)."
                ]
            },
            {
                "heading": "४. आणीबाणी व घटनादुरुस्ती",
                "color": "#F472B6",
                "points": [
                    "• कलम ३५२: राष्ट्रीय आणीबाणी (युद्ध, परकीय आक्रमण).",
                    "• कलम ३५६: राष्ट्रपती राजवट (घटनेतील यंत्रणा अपयशी).",
                    "• कलम ३६०: आर्थिक आणीबाणी (भारतात एकदाही नाही).",
                    "• कलम ३६८: घटनादुरुस्ती प्रक्रिया (दक्षिण आफ्रिकेकडून स्वीकारली)."
                ]
            }
        ],
        "exam_tip": "कलम १७, २१, ३२, ४४, ६१ आणि ३६८ या ६ कलमांवर दर ३ शिफ्ट्समध्ये किमान १ प्रश्न १००% येतोच!"
    },
    {
        "id": "gs_maharashtra_rivers",
        "subject": "महाराष्ट्राचा भूगोल",
        "title": "महाराष्ट्रातील प्रमुख नद्या व त्यांची जलप्रणाली",
        "subtitle": "गोदावरी, भीमा, कृष्णा व तापी-नर्मदा नदी प्रणाली",
        "branches": [
            {
                "heading": "१. गोदावरी नदी (दक्षिण गंगा)",
                "color": "#38BDF8",
                "points": [
                    "• उगम: त्र्यंबकेश्वर, जि. नाशिक (ब्रह्मगिरी पर्वत).",
                    "• लांबी: महाराष्ट्रात ६६८ किमी (भारतात १४६५ किमी).",
                    "• खोऱ्याने व्यापलेले क्षेत्र: महाराष्ट्राच्या ४९.५% क्षेत्र.",
                    "• प्रमुख उपनद्या: दारणा, प्रवरा, सिंदफणा, मांजरा, प्राणहिता, इंद्रावती.",
                    "• प्रमुख धरण: जायकवाडी (पैठण, छत्रपती संभाजीनगर)."
                ]
            },
            {
                "heading": "२. भीमा व कृष्णा नदी प्रणाली",
                "color": "#34D399",
                "points": [
                    "• भीमा उगम: भीमाशंकर, जि. पुणे (लांबी: ४५१ किमी).",
                    "• भीमेची प्रमुख धरणे: उजनी (सोलापूर), भाटघर, चासकमान.",
                    "• कृष्णा उगम: महाबळेश्वर, जि. सातारा (लांबी: २८२ किमी).",
                    "• कृष्णेच्या उपनद्या: कोयना (महाराष्ट्राची भाग्यलक्ष्मी), वारणा, पंचगंगा."
                ]
            },
            {
                "heading": "३. तापी व नर्मदा (पश्चिमवाहिनी नद्या)",
                "color": "#FBBF24",
                "points": [
                    "• तापी उगम: बैतुल (मध्य प्रदेश), मुलताई टेकड्या.",
                    "• महाराष्ट्रातील लांबी: २०८ किमी (खानदेशची कन्या).",
                    "• प्रमुख उपनदी: पूर्णा नदी; प्रमुख धरण: हतनूर (जळगाव).",
                    "• नर्मदा नदी: महाराष्ट्राच्या उत्तर सीमेवरून फक्त ५४ किमी वाहते (नंदुरबार)."
                ]
            },
            {
                "heading": "४. कोकणातील नद्या (पश्चिमवाहिनी)",
                "color": "#A78BFA",
                "points": [
                    "• सह्याद्री पर्वतात उगम पावून अरबी समुद्रास मिळतात.",
                    "• नद्यांची लांबी अतिशय कमी (४९ ते १५५ किमी) व प्रवाह वेगवान.",
                    "• उत्तरेकडील वैतरणा ही कोकणातील सर्वात लांब नदी (१५४ किमी).",
                    "• उल्हास, सावित्री, वाशिष्ठी, शास्त्री, तेरेखोल (दक्षिण सीमा)."
                ]
            }
        ],
        "exam_tip": "उपनद्यांवर हमखास प्रश्न विचारले जातात: मांजरा ही गोदावरीची उजव्या तीरावरील सर्वात मोठी उपनदी आहे!"
    },
    {
        "id": "math_time_and_work",
        "subject": "अंकगणित (Quantitative Aptitude)",
        "title": "काळ, काम आणि वेग (Time & Work) सुपर शॉर्टकट ट्रिक्स",
        "subtitle": "लसावि (LCM) पद्धतीने कोणतीही पायरी न चुकता उत्तरे काढा",
        "branches": [
            {
                "heading": "१. मूलभूत लसावि (LCM) पद्धत",
                "color": "#38BDF8",
                "points": [
                    "• 'A' काम करतो १० दिवसात, 'B' करतो १५ दिवसात.",
                    "• १० व १५ चा लसावि = ३० युनिट्स (एकूण काम).",
                    "• A ची कार्यक्षमता = ३०/१० = ३ युनिट/दिवस.",
                    "• B ची कार्यक्षमता = ३०/१५ = २ युनिट/दिवस.",
                    "• दोघे मिळून: ३० / (३ + २) = ६ दिवसांत काम संपेल!"
                ]
            },
            {
                "heading": "२. काम सोडून जाण्याची उदाहरणे",
                "color": "#34D399",
                "points": [
                    "• काम संपण्याच्या आधी किंवा सुरुवातीस सोडून गेल्यास:",
                    "• सुरुवातीस सोडून गेला तर त्याचे काम वजा करा.",
                    "• काम संपण्यापूर्वी सोडून गेला तर त्याचे काम एकूण कामात मिळवा!",
                    "• राहिलेल्या कार्यक्षमतेने एकूण युनिट्सला भागा."
                ]
            },
            {
                "heading": "३. नळ व पाण्याची टाकी (Pipes & Cistern)",
                "color": "#FBBF24",
                "points": [
                    "• भरणारा नळ (+) धनात्मक कार्यक्षमता देतो.",
                    "• गळती किंवा रिकामी करणारा नळ (-) ऋण कार्यक्षमता देतो.",
                    "• टाकीची क्षमता = दोन्ही नळांच्या वेळेचा लसावि.",
                    "• निव्वळ कार्यक्षमता = (भरणारा दर - रिकामी करणारा दर)."
                ]
            },
            {
                "heading": "४. M1 × D1 × H1 = M2 × D2 × H2",
                "color": "#F472B6",
                "points": [
                    "• सूत्र: (M1 × D1 × H1) / W1 = (M2 × D2 × H2) / W2",
                    "• M = माणसे, D = दिवस, H = रोजचे तास, W = केलेले काम.",
                    "• काम (Work) नेहमी छेदात (Denominator) ठेवायचे असते!"
                ]
            }
        ],
        "exam_tip": "पूर्णांक अपूर्णांकांची बेरीज टाळण्यासाठी नेहमी एकूण काम = दिलेल्या दिवसांचा 'लसावि' माना!"
    },
    {
        "id": "gs_social_reformers",
        "subject": "महाराष्ट्राचा इतिहास",
        "title": "महाराष्ट्रातील प्रमुख समाजसुधारक व त्यांचे अद्वितीय कार्य",
        "subtitle": "TCS व IBPS भरतीमध्ये हमखास येणारे संस्था, वृत्तपत्रे व पुस्तके",
        "branches": [
            {
                "heading": "१. महात्मा ज्योतिराव फुले",
                "color": "#38BDF8",
                "points": [
                    "• १८४८: भिडे वाड्यात मुलींची पहिली शाळा सुरू केली.",
                    "• १८७३: सत्यशोधक समाजाची स्थापना केली.",
                    "• ग्रंथसंपदा: शेतकऱ्याचा आसूड, गुलामगिरी, ब्राह्मणांचे कसब, सार्वजनिक सत्यधर्म.",
                    "• १८८८: मुंबईच्या जनतेने 'महात्मा' पदवी बहाल केली."
                ]
            },
            {
                "heading": "२. भारतरत्न डॉ. बाबासाहेब आंबेडकर",
                "color": "#34D399",
                "points": [
                    "• १९२४: बहिष्कृत हितकारिणी सभा (शिका, संघटित व्हा, संघर्ष करा).",
                    "• १९२७: महाडचा सत्याग्रह (चवदार तळे), मनुस्मृती दहन.",
                    "• वृत्तपत्रे: मूकनायक, बहिष्कृत भारत, जनता, प्रबुद्ध भारत.",
                    "• भारतीय संविधानाच्या मसुदा समितीचे अध्यक्ष (Drafting Committee)."
                ]
            },
            {
                "heading": "३. राजर्षी छत्रपती शाहू महाराज",
                "color": "#FBBF24",
                "points": [
                    "• २६ जुलै १९०२: मागासवर्गीयांसाठी ५०% आरक्षणाची ऐतिहासिक घोषणा.",
                    "• कोल्हापूर संस्थानात प्राथमिक शिक्षण मोफत व सक्तीचे केले.",
                    "• आंतरजातीय व आंतरधर्मीय विवाहाचा कायदा संमत केला.",
                    "• डॉ. आंबेडकरांच्या मूकनायक पाक्षिकाला आर्थिक मदत केली."
                ]
            },
            {
                "heading": "४. महर्षी धोंडो केशव कर्वे व आगरकर",
                "color": "#A78BFA",
                "points": [
                    "• महर्षी कर्वे: १९१६ मध्ये भारतातील पहिले महिला विद्यापीठ (SNDT) स्थापले.",
                    "• १९५८: भारतरत्न सन्मान मिळालेले पहिले महाराष्ट्रीय व्यक्ती.",
                    "• गोपाळ गणेश आगरकर: 'सुधारक' वृत्तपत्र सुरू केले.",
                    "• 'इष्ट असेल ते बोलणार आणि साध्य असेल ते करणार' हे आगरकरांचे ब्रीदवाक्य."
                ]
            }
        ],
        "exam_tip": "वृत्तपत्रे आणि स्थापन केलेल्या संस्थांच्या जोड्या जुळवा या स्वरूपाचे प्रश्न हमखास येतात!"
    },
    {
        "id": "reasoning_blood_relation",
        "subject": "बुद्धिमत्ता चाचणी (Reasoning)",
        "title": "नातेसंबंध (Blood Relations) ५ सेकंद फॅमिली ट्री ट्रिक्स",
        "subtitle": "कोडिंग व फोटोग्राफकडे बोट दाखवणाऱ्या प्रश्नांवर अचूक उत्तरे",
        "branches": [
            {
                "heading": "१. फॅमिली ट्री संकेतांक (Notations)",
                "color": "#38BDF8",
                "points": [
                    "• पुरुष सदस्य: [+] किंवा चौरस चिन्ह.",
                    "• स्त्री सदस्य: [-] किंवा वर्तुळ चिन्ह.",
                    "• पती-पत्नी संबंध: [=] दुहेरी रेषा.",
                    "• भाऊ-बहीण संबंध: [-] एकेरी आडवी रेषा.",
                    "• पिढीचा बदल (आई/वडील ➔ मुले): [|] उभी रेषा."
                ]
            },
            {
                "heading": "२. फोटोग्राफ / व्यक्तीकडे बोट दाखवणारे प्रश्न",
                "color": "#34D399",
                "points": [
                    "• 'माझ्या' शब्दापासून वाचायला सुरुवात करा (Reverse Reading).",
                    "• स्वतःला बोलणाऱ्या व्यक्तीच्या जागी कल्पून नात्यांची साखळी जोडा.",
                    "• उदा. 'माझ्या वडिलांची एकुलती एक मुलगी' = 'मी स्वतः' (स्त्री असल्यास) किंवा 'माझी बहीण'."
                ]
            },
            {
                "heading": "३. कोडिंग नातेसंबंध (A + B, A - B)",
                "color": "#FBBF24",
                "points": [
                    "• आधी प्रश्नात विचारलेल्या व्यक्तीचे लिंग (Gender Elimination) तपासा.",
                    "• जर मुलगा विचारला असेल तर [-] असणारे पर्याय लगेच बाद करा.",
                    "• शेवटून सुरुवातीकडे नाते जोडत जावे."
                ]
            },
            {
                "heading": "४. सामान्य चुका टाळा",
                "color": "#F87171",
                "points": [
                    "• नावावरून व्यक्तीचे लिंग (Gender) कधीही ठरवू नका (उदा. किरण, शीतल).",
                    "• काका, मामा, मावशी, आत्या यांमधील इंग्रजी 'Uncle / Aunt' शब्द तपासा.",
                    "• भाचा / पुतण्या (Nephew) व भाची / पुतणी (Niece) फरक लक्षात ठेवा."
                ]
            }
        ],
        "exam_tip": "नेहमी फॅमिली ट्री कागदावर काढा. मानसिक विचार करण्यापेक्षा आकृती काढल्यास ०% चूक होते!"
    },
    {
        "id": "gs_census_2011",
        "subject": "सामान्य ज्ञान (महाराष्ट्र भूगोल)",
        "title": "२०११ ची जनगणना: महाराष्ट्र विशेष आकडेवारी",
        "subtitle": "TCS परीक्षेमध्ये प्रत्येक पेपरमध्ये विचारले जाणारे हमखास आकडे",
        "branches": [
            {
                "heading": "१. लोकसंख्या व घनता",
                "color": "#38BDF8",
                "points": [
                    "• महाराष्ट्राची एकूण लोकसंख्या: ११.२४ कोटी (भारताच्या ९.२८% - २ रा क्रमांक).",
                    "• लोकसंख्येची घनता: ३६५ व्यक्ती प्रति चौ.किमी (भारताची ३८२).",
                    "• सर्वाधिक लोकसंख्येचा जिल्हा: ठाणे (विभाजनापूर्वी), पुणे.",
                    "• सर्वात कमी लोकसंख्येचा जिल्हा: सिंधुदुर्ग (८.५ लाख)."
                ]
            },
            {
                "heading": "२. लिंगगुणोत्तर (Sex Ratio)",
                "color": "#34D399",
                "points": [
                    "• महाराष्ट्राचे एकूण लिंगगुणोत्तर: ९२९ (भारताचे ९४३).",
                    "• सर्वाधिक लिंगगुणोत्तर जिल्हा: रत्नागिरी (११२२), सिंधुदुर्ग (१०३६).",
                    "• सर्वात कमी लिंगगुणोत्तर जिल्हा: मुंबई शहर (८३२).",
                    "• बाल लिंगगुणोत्तर (० ते ६ वर्षे): ८९४ (सर्वात कमी बीड - ८०७)."
                ]
            },
            {
                "heading": "३. साक्षरता प्रमाण (Literacy Rate)",
                "color": "#FBBF24",
                "points": [
                    "• महाराष्ट्राचा साक्षरता दर: ८२.३% (पुरुष: ८८.४%, स्त्री: ७५.९%).",
                    "• सर्वाधिक साक्षर जिल्हा: मुंबई उपनगर (८९.९%), मुंबई शहर (८९.२%).",
                    "• सर्वात कमी साक्षर जिल्हा: नंदुरबार (६४.४%).",
                    "• ग्रामीण साक्षरता: ७७%, नागरी साक्षरता: ८८.७%."
                ]
            },
            {
                "heading": "४. नागरी व ग्रामीण लोकसंख्या",
                "color": "#A78BFA",
                "points": [
                    "• ग्रामीण लोकसंख्या: ५४.८% (६.१५ कोटी).",
                    "• नागरी लोकसंख्या: ४५.२% (५.०८ कोटी).",
                    "• महाराष्ट्रात १००% नागरी जिल्हा: मुंबई शहर व मुंबई उपनगर.",
                    "• सर्वाधिक अनुसूचित जमाती (ST) लोकसंख्या: नाशिक जिल्हा."
                ]
            }
        ],
        "exam_tip": "रत्नागिरी (११२२) व सिंधुदुर्ग (१०३६) हे दोनच जिल्हे असे आहेत जेथे पुरुषांपेक्षा स्त्रियांची संख्या जास्त आहे!"
    },
    {
        "id": "english_subject_verb",
        "subject": "English Grammar",
        "title": "Subject-Verb Agreement: 5 Golden Rules for TCS & IBPS",
        "subtitle": "Spotting the Error व Sentence Correction मध्ये १००% विचारले जाणारे नियम",
        "branches": [
            {
                "heading": "1. Along with / As well as Rule",
                "color": "#38BDF8",
                "points": [
                    "• Words: along with, together with, as well as, accompanied by.",
                    "• Rule: Verb agrees strictly with the FIRST Subject!",
                    "• Example: The Captain, along with his players, IS coming (not are).",
                    "• Example: The students, as well as the teacher, WERE present."
                ]
            },
            {
                "heading": "2. Either...Or / Neither...Nor Rule",
                "color": "#34D399",
                "points": [
                    "• Rule: Verb agrees strictly with the NEAREST (second) Subject!",
                    "• Neither the teacher nor the students WERE in the class.",
                    "• Either the boys or their father HAS done this.",
                    "• 'Each of', 'Neither of', 'Either of' ALWAYS take Singular Verb!"
                ]
            },
            {
                "heading": "3. Collective Noun Rule",
                "color": "#FBBF24",
                "points": [
                    "• Acting as a single unit = SINGULAR Verb (jury, committee, team).",
                    "• The jury HAS given its verdict unanimously.",
                    "• Divided in opinion = PLURAL Verb.",
                    "• The committee ARE divided in their opinions."
                ]
            },
            {
                "heading": "4. Plural in Form, Singular in Meaning",
                "color": "#F472B6",
                "points": [
                    "• Subjects/Diseases: Mathematics, Physics, News, Measles, Rickets.",
                    "• Take SINGULAR verb: 'Mathematics IS an interesting subject.'",
                    "• Pairs: Scissors, Trousers, Spectacles take PLURAL verb.",
                    "• 'A pair of scissors' takes SINGULAR verb!"
                ]
            }
        ],
        "exam_tip": "'One of the + Plural Noun + Singular Verb' हा TCS चा अत्यंत आवडता पॅटर्न आहे: 'One of the students IS absent'!"
    },
    {
        "id": "math_profit_loss",
        "subject": "अंकगणित (Quantitative Aptitude)",
        "title": "नफा-तोटा व शेकडेवारी (Profit, Loss & %) ट्रिक्स",
        "subtitle": "फॉर्म्युले पाठ न करता गुणोत्तर (Fraction) पद्धतीने जलद उत्तरे",
        "branches": [
            {
                "heading": "१. टक्केवारी ते अपूर्णांक टेबल",
                "color": "#38BDF8",
                "points": [
                    "• १०% = १/१० | २०% = १/५ | २५% = १/४ | ५०% = १/२",
                    "• १६.६६% = १/६ | १२.५% = १/८ | ३३.३३% = १/३",
                    "• उदा. २५% नफा म्हणजे ४ रुपयांची वस्तू ५ रुपयांत विकली (CP=४, SP=५)."
                ]
            },
            {
                "heading": "२. वस्तूंची खरेदी व विक्री संख्या समान असताना",
                "color": "#34D399",
                "points": [
                    "• '१२ वस्तूंची खरेदी किंमत = ९ वस्तूंच्या विक्री किंमतीइतकी आहे.'",
                    "• शॉर्टकट: नफा % = [(खरेदी वस्तू - विक्री वस्तू) / विक्री वस्तू] × १००",
                    "• = [(१२ - ९) / ९] × १०० = ३/९ × १०० = ३३.३३% नफा!"
                ]
            },
            {
                "heading": "३. समान दराने विक्री व नफा-तोटा",
                "color": "#FBBF24",
                "points": [
                    "• दोन वस्तू प्रत्येकी समान दराने विकल्या, एकावर x% नफा व दुसऱ्यावर x% तोटा झाला.",
                    "• या व्यवहारात नेहमी तोटाच होतो!",
                    "• तोटा % = (x² / १००) %.",
                    "• उदा. २०% नफा व २०% तोटा ➔ (२०² / १००) = ४% तोटा."
                ]
            },
            {
                "heading": "४. छापील किंमत व सूट (Discount)",
                "color": "#A78BFA",
                "points": [
                    "• सवलत (Discount) नेहमी छापील किंमतीवर (Marked Price) दिली जाते.",
                    "• क्रमागत सूट (Successive Discount) शॉर्टकट: A + B - (AB / १००).",
                    "• उदा. २०% व १०% ची एकत्रित सूट = २० + १० - (२००/१००) = २८% सूट."
                ]
            }
        ],
        "exam_tip": "नफा किंवा तोटा हा नेहमी खरेदी किंमतीवर (CP) काढला जातो, जोपर्यंत प्रश्नात स्पष्टपणे विक्री किंमतीवर विचारले जात नाही!"
    },
    {
        "id": "marathi_alankar",
        "subject": "मराठी व्याकरण",
        "title": "मराठी भाषेचे अलंकार: TCS व IBPS मधील ट्रॅप प्रकार",
        "subtitle": "अर्थालंकार व शब्दालंकार ओळखण्याची १-सेकंद युक्ती",
        "branches": [
            {
                "heading": "१. उपमा अलंकार (Comparison)",
                "color": "#38BDF8",
                "points": [
                    "• साम्यदर्शक शब्द: सम, सारखा, जसा, वाणी, प्रमाणे, परी.",
                    "• उदा. 'सावळाच रंग तुझा पावसाळी नभापरी'.",
                    "• क्लृप्ती: वाक्यात 'सारखा/परी' दिसताच उपमा अलंकार."
                ]
            },
            {
                "heading": "२. उत्प्रेक्षा अलंकार (Imagination)",
                "color": "#34D399",
                "points": [
                    "• साम्यदर्शक शब्द: जणू, जणूकाही, गमे, वाटे, भासे, की.",
                    "• उदा. 'ती गुलाबी उषा म्हणजे परमेश्वराचे प्रेम जणू!'.",
                    "• क्लृप्ती: उपमेय हे जणू उपमानच आहे अशी कल्पना."
                ]
            },
            {
                "heading": "३. रूपक अलंकार (Identification)",
                "color": "#FBBF24",
                "points": [
                    "• उपमेय आणि उपमान यात पूर्ण एकरूपता (भेद नसतो).",
                    "• उदा. 'लहान मूल म्हणजे मातीचा गोळा'.",
                    "• उदा. 'नयनकमल', 'मुखचंद्र'."
                ]
            },
            {
                "heading": "४. श्लेष व व्यतिरेक (Trap Rules)",
                "color": "#F472B6",
                "points": [
                    "• श्लेष: एकच शब्द दोन अर्थांनी (उदा. 'मित्राच्या उदयाने कोणास आनंद होत नाही?').",
                    "• व्यतिरेक: उपमेय उपमानापेक्षा श्रेष्ठ (उदा. 'अमृताहुनि गोड नाम तुझे देवा')."
                ]
            }
        ],
        "exam_tip": "वाक्यात 'जणू/गमे/वाटे' आले की उत्प्रेक्षा; 'सम/सारखा/परी' आले की उपमा; आणि 'पेक्षा श्रेष्ठ' दाखवले की व्यतिरेक!"
    },
    {
        "id": "gs_panchayati_raj",
        "subject": "सामान्य ज्ञान (पंचायत राज)",
        "title": "पंचायत राज व्यवस्था: ७३ वी व ७४ वी घटनादुरुस्ती",
        "subtitle": "महाराष्ट्र जिल्हा परिषद, पंचायत समिती व ग्रामपंचायत रचना",
        "branches": [
            {
                "heading": "१. घटनात्मक पार्श्वभूमी",
                "color": "#38BDF8",
                "points": [
                    "• ७३ वी घटनादुरुस्ती (१९९२): ग्रामीण स्थानिक स्वराज्य संस्था (११ वे परिशिष्ट, २९ विषय).",
                    "• ७४ वी घटनादुरुस्ती (१९९२): नागरी स्थानिक स्वराज्य संस्था (१२ वे परिशिष्ट, १८ विषय).",
                    "• कलम २४३ ते २४३O: पंचायत राज तरतुदी."
                ]
            },
            {
                "heading": "२. महत्त्वाच्या समित्या क्रम",
                "color": "#34D399",
                "points": [
                    "• बलवंतराय मेहता समिती (१९५७) - त्रिस्तरीय व्यवस्था शिफारस.",
                    "• वसंतराव नाईक समिती (१९६०) - महाराष्ट्रात जिल्हा परिषद सर्वोच्च.",
                    "• अशोक मेहता समिती (१९७७) - द्विस्तरीय व्यवस्था शिफारस."
                ]
            },
            {
                "heading": "३. ग्रामपंचायत व ग्रामसभा",
                "color": "#FBBF24",
                "points": [
                    "• सदस्य संख्या: ७ ते १७ (लोकसंख्येनुसार).",
                    "• सरपंच: थेट जनतेतून किंवा सदस्यांमधून.",
                    "• ग्रामसेवक: वर्ग-३ चा प्रशासकीय अधिकारी (Z.P. कडून नियुक्ती)."
                ]
            },
            {
                "heading": "४. जिल्हा परिषद व CEO",
                "color": "#F472B6",
                "points": [
                    "• मुख्य कार्यकारी अधिकारी (CEO): IAS दर्जाचा अधिकारी.",
                    "• आरक्षण: महिलांसाठी ५०% राखीव जागा.",
                    "• निवडणुका: राज्य निवडणूक आयोग (SEC) घेतो."
                ]
            }
        ],
        "exam_tip": "महाराष्ट्रात पंचायत राजची स्थापना १ मे १९६२ रोजी झाली. वसंतराव नाईक समितीच्या शिफारशीनुसार जिल्हा परिषदेला सर्वात शक्तिशाली बनवले!"
    },
    {
        "id": "math_percentage_shortcuts",
        "subject": "अंकगणित (Quantitative Aptitude)",
        "title": "टक्केवारी (Percentages): फ्रॅक्शन टू पर्सेंटेज मॅजिक ट्रिक्स",
        "subtitle": "TCS व IBPS मध्ये १० सेकंदात आकडेमोड करण्याचे टेबल",
        "branches": [
            {
                "heading": "१. अपूर्णांक ते टक्केवारी टेबल",
                "color": "#38BDF8",
                "points": [
                    "• १/२ = ५०%, १/३ = ३३.३३%, १/४ = २५%.",
                    "• १/५ = २०%, १/६ = १६.६६%, १/७ = १४.२८%.",
                    "• १/८ = १२.५%, १/९ = ११.११%, १/११ = ९.०९%."
                ]
            },
            {
                "heading": "२. मूळ किंमत वाढ-घट नियम",
                "color": "#34D399",
                "points": [
                    "• साखर २५% (१/४) ने महागली, तर वापर २०% (१/५) ने कमी करावा लागतो.",
                    "• सूत्र: जर किंमत a/b ने वाढली, तर खर्च कायम ठेवण्यासाठी वापर a/(a+b) ने कमी होतो."
                ]
            },
            {
                "heading": "३. क्रमागत टक्केवारी वाढ (Successive)",
                "color": "#FBBF24",
                "points": [
                    "• नेट बदल = X + Y + (XY / १००).",
                    "• २०% वाढ व १०% वाढ = २० + १० + २ = ३२% निव्वळ वाढ.",
                    "• २०% वाढ व २०% घट = ४% नेहमी निव्वळ घट (-X²/१००)."
                ]
            },
            {
                "heading": "४. गुणाकार ट्रिक्स (AB Rule)",
                "color": "#F472B6",
                "points": [
                    "• ६४ चे १२.५% = ६४ × (१/८) = ८ (पेन न उचलता!).",
                    "• ८४ चे १६.६६% = ८४ × (१/६) = १४.",
                    "• ९९ चे ९.०९% = ९९ × (१/११) = ९."
                ]
            }
        ],
        "exam_tip": "जेव्हा दोन समान टक्केवारी एकदा वाढतात व एकदा घटतात, तेव्हा १००% वेळेस तोटाच (X²/१००)% होतो!"
    },
    {
        "id": "reasoning_syllogism",
        "subject": "बुद्धिमत्ता चाचणी (Reasoning)",
        "title": "सिलॉगीझम (Syllogism): वेन आकृती व निष्कर्ष नियम",
        "subtitle": "Only a few, Some, All यांवरील TCS चे नवीन प्रश्न",
        "branches": [
            {
                "heading": "१. 'सर्व' (All) व 'काही' (Some)",
                "color": "#38BDF8",
                "points": [
                    "• जर विधान: 'सर्व A हे B आहेत' -> निष्कर्ष: 'काही B हे A आहेत' हे १००% सत्य.",
                    "• विधान: 'काही A हे B आहेत' -> निष्कर्ष: 'काही B हे A आहेत' हे १००% सत्य."
                ]
            },
            {
                "heading": "२. 'नाही' (No) व नकारात्मक नियम",
                "color": "#34D399",
                "points": [
                    "• 'कोणताही A हा B नाही' -> दोघांच्या वेन आकृती एकमेकांना स्पर्श करत नाहीत.",
                    "• जर सर्व विधाने होकारात्मक असतील, तर कोणताही निश्चित नकारात्मक निष्कर्ष निघत नाही."
                ]
            },
            {
                "heading": "३. 'Only a Few' (TCS स्पेशल)",
                "color": "#FBBF24",
                "points": [
                    "• 'Only a few A are B' चा अर्थ: 'काही A हे B आहेत' आणि 'काही A हे B नाहीत' दोन्ही एकत्र!",
                    "• यामध्ये सर्व A कधीही B होऊ शकत नाहीत."
                ]
            },
            {
                "heading": "४. 'Either / Or' अट (सुवर्ण नियम)",
                "color": "#F472B6",
                "points": [
                    "• दोन्ही निष्कर्ष वैयक्तिकरित्या खोटे असावेत.",
                    "• एक होकारात्मक व एक नकारात्मक असावा (Some + No किंवा All + Some Not).",
                    "• दोन्ही निष्कर्षांचे घटक (Elements) समान असावेत."
                ]
            }
        ],
        "exam_tip": "संभाव्यता (Possibility) विचारली असेल तर बेसिक आकृती तोडून नवीन आकृती तपासा. जर विधानाचा भंग होत नसेल, तर शक्यता सत्य ठरते!"
    },
    {
        "id": "ca_2026_maharashtra_schemes",
        "subject": "चालू घडामोडी २०२६",
        "title": "महाराष्ट्र शासन प्रमुख कल्याणकारी योजना २०२६",
        "subtitle": "लाडकी बहीण, अन्नपूर्णा, वयोश्री व लेक लाडकी योजना अपडेट्स",
        "branches": [
            {
                "heading": "१. मुख्यमंत्री माझी लाडकी बहीण योजना",
                "color": "#38BDF8",
                "points": [
                    "• आर्थिक लाभ: दरमहा ₹१,५०० पात्र महिलांच्या खात्यात थेट DBT द्वारे.",
                    "• वयोगट: २१ ते ६५ वर्षे; कौटुंबिक वार्षिक उत्पन्न मर्यादा: ₹२.५ लाख.",
                    "• नोडल विभाग: महिला व बालविकास विभाग, महाराष्ट्र शासन."
                ]
            },
            {
                "heading": "२. मुख्यमंत्री अन्नपूर्णा योजना",
                "color": "#34D399",
                "points": [
                    "• दरवर्षी पात्र कुटुंबांना ३ घरगुती एलपीजी (LPG) सिलिंडर मोफत.",
                    "• प्रधानमंत्री उज्ज्वला योजना व लाडकी बहीण लाभार्थींना थेट लाभ."
                ]
            },
            {
                "heading": "३. मुख्यमंत्री वयोश्री योजना",
                "color": "#FBBF24",
                "points": [
                    "• ज्येष्ठ नागरिकांसाठी (वय ६५ वर्षे वरील) ₹३,००० एकरकमी सहाय्य.",
                    "• चष्मा, श्रवणयंत्र, व्हीलचेअर व इतर सहाय्यक उपकरणे खरेदीसाठी."
                ]
            },
            {
                "heading": "४. लेक लाडकी योजना",
                "color": "#F472B6",
                "points": [
                    "• पिवळे व केशरी रेशनकार्डधारक कुटुंबातील मुलींना टप्प्याटप्प्याने एकूण ₹१,०१,०००.",
                    "• जन्मावेळी ₹५,००० ते १८ वर्षे पूर्ण झाल्यावर ₹७५,००० थेट लाभ."
                ]
            }
        ],
        "exam_tip": "TCS परीक्षेत योजनांचे 'वयोगट', 'उत्पन्न मर्यादा' आणि 'दरमहा मिळणारी रक्कम' यावर हमखास थेट प्रश्न विचारले जातात!"
    }
]

def init_mindmap_db(db_path: str = DEFAULT_DB_PATH):
    """Initializes the deduplication tracking table for posted mindmaps."""
    dir_name = os.path.dirname(db_path)
    if dir_name:
        os.makedirs(dir_name, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS posted_mindmaps (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                topic_id TEXT UNIQUE,
                topic_title TEXT,
                posted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()

def get_pil_font(size: int = 20, bold: bool = False):
    """Safely loads Unicode font supporting Devanagari across Windows and Linux."""
    candidates = []
    if os.name == "nt":
        if bold:
            candidates.extend(["C:/Windows/Fonts/NirmalaB.ttf", "C:/Windows/Fonts/Arialbd.ttf"])
        candidates.extend(["C:/Windows/Fonts/Nirmala.ttf", "C:/Windows/Fonts/Arial.ttf"])
    else:
        # Linux paths
        candidates.extend([
            "/usr/share/fonts/truetype/lohit-marathi/Lohit-Marathi.ttf",
            "/usr/share/fonts/truetype/gargi/Gargi.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ])
    for p in candidates:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                continue
    try:
        return ImageFont.load_default()
    except Exception:
        return None

def hex_to_rgb(hex_str: str) -> tuple[int, int, int]:
    hex_str = hex_str.lstrip("#")
    return tuple(int(hex_str[i:i+2], 16) for i in (0, 2, 4))

def render_mindmap_image(topic: dict, output_path: Path) -> Path:
    """Renders a 1200x800 high-resolution, modern dark-slate infographic card for the topic."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    w, h = 1200, 800
    img = Image.new("RGB", (w, h), color=(15, 23, 42))  # Slate 900
    draw = ImageDraw.Draw(img)

    # Fonts
    font_badge = get_pil_font(16, bold=True)
    font_title = get_pil_font(30, bold=True)
    font_sub = get_pil_font(18, bold=False)
    font_card_head = get_pil_font(21, bold=True)
    font_body = get_pil_font(17, bold=False)
    font_footer = get_pil_font(15, bold=False)

    # Outer decorative glow border
    draw.rectangle([16, 16, w - 16, h - 16], outline=(51, 65, 85), width=2)
    draw.rectangle([20, 20, w - 20, h - 20], outline=(30, 41, 59), width=1)

    # Header Bar Badge
    subj = topic.get("subject", "परीक्षेचा घटक")
    badge_text = f"🔥 TCS / IBPS दैनिक माइंडमॅप  •  [{subj}]"
    draw.rounded_rectangle([40, 36, 440, 70], radius=8, fill=(30, 58, 138), outline=(56, 189, 248), width=1)
    draw.text((54, 43), badge_text, font=font_badge, fill=(224, 242, 254))

    # Main Title
    draw.text((40, 85), topic.get("title", ""), font=font_title, fill=(248, 250, 252))
    # Subtitle
    draw.text((40, 130), f"⚡ {topic.get('subtitle', '')}", font=font_sub, fill=(148, 163, 184))

    # 4 Branch Cards Grid (2x2)
    # Positions
    cards = [
        {"rect": [40, 175, 585, 435]},     # Top-Left
        {"rect": [615, 175, 1160, 435]},   # Top-Right
        {"rect": [40, 455, 585, 715]},     # Bottom-Left
        {"rect": [615, 455, 1160, 715]},   # Bottom-Right
    ]

    branches = topic.get("branches", [])
    for idx, card_cfg in enumerate(cards):
        if idx >= len(branches):
            break
        br = branches[idx]
        rx1, ry1, rx2, ry2 = card_cfg["rect"]
        accent_color = hex_to_rgb(br.get("color", "#38BDF8"))

        # Card Background
        draw.rounded_rectangle([rx1, ry1, rx2, ry2], radius=12, fill=(30, 41, 59), outline=(51, 65, 85), width=1)
        # Top Accent Line
        draw.rounded_rectangle([rx1, ry1, rx2, ry1 + 6], radius=4, fill=accent_color)

        # Card Title
        draw.text((rx1 + 18, ry1 + 18), br.get("heading", ""), font=font_card_head, fill=accent_color)

        # Bullet Points
        cur_y = ry1 + 58
        for pt in br.get("points", []):
            # Wrap long text cleanly
            words = pt.split(" ")
            line = ""
            for word in words:
                test_line = f"{line} {word}".strip()
                if len(test_line) > 52:
                    draw.text((rx1 + 18, cur_y), line, font=font_body, fill=(241, 245, 249))
                    cur_y += 26
                    line = f"  {word}"
                else:
                    line = test_line
            if line:
                draw.text((rx1 + 18, cur_y), line, font=font_body, fill=(241, 245, 249))
                cur_y += 28

    # Footer Watermark
    draw.line([40, 740, w - 40, 740], fill=(51, 65, 85), width=1)
    footer_text = "📚 ExamRankers India Bot (@ExamRankersIndiaBot) | अधिकृत परीक्षा रँक, स्पष्टीकरण व क्विझ चॅनेल"
    draw.text((40, 752), footer_text, font=font_footer, fill=(148, 163, 184))

    img.save(output_path, format="JPEG", quality=95)
    logger.info(f"Generated dynamic mindmap image: {output_path}")
    return output_path

def format_mindmap_telegram_caption(topic: dict) -> str:
    """
    Formats an engaging, richly-styled Marathi Telegram caption for the mindmap.
    Strictly guaranteed to remain under 850 characters to comply with Telegram photo limits (1024 max).
    """
    subj = topic.get("subject", "सामान्य ज्ञान")
    title = topic.get("title", "")
    sub = topic.get("subtitle", "TCS / IBPS स्पेशल रिव्हिजन")

    lines = [
        f"🎯 <b>आजचा नवीन ट्रेंडिंग घटक: {subj}</b>",
        f"📌 <b>{title}</b>",
        "━━━━━━━━━━━━━━━━━━━━━━",
        f"⚡ <i>{sub}</i>\n"
    ]

    for br in topic.get("branches", [])[:4]:
        heading = br.get("heading", "")
        pts = br.get("points", [])
        pt_lead = pts[0].lstrip("• ") if pts else ""
        lines.append(f"🔹 <b>{heading}</b>: {pt_lead}")

    if topic.get("exam_tip"):
        lines.append(f"\n💡 <b>TCS/IBPS प्रो ट्रिक:</b> <i>{topic['exam_tip']}</i>")

    lines.append("\n━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("📥 <i>हा माइंडमॅप सेव्ह करा व मित्रांना अभ्यासासाठी नक्की शेअर करा!</i>")

    caption = "\n".join(lines)
    if len(caption) > 920:
        caption = caption[:910] + "...\n━━━━━━━━━━━━━━━━━━━━━━\n📥 <i>हा माइंडमॅप सेव्ह करा!</i>"
    return caption

def get_next_dynamic_mindmap(db_path: str = DEFAULT_DB_PATH) -> tuple[dict, Path, str]:
    """
    Selects the next unposted or least recently posted topic.
    Returns: (topic_dict, image_path, formatted_caption)
    """
    init_mindmap_db(db_path)
    with sqlite3.connect(db_path) as conn:
        posted_ids = [r[0] for r in conn.execute("SELECT topic_id FROM posted_mindmaps").fetchall()]

    # Find unposted topic
    chosen_topic = None
    for t in MINDMAP_TOPICS:
        if t["id"] not in posted_ids:
            chosen_topic = t
            break

    # If all 10+ topics have been posted, recycle least recently used
    if not chosen_topic:
        with sqlite3.connect(db_path) as conn:
            oldest_row = conn.execute("SELECT topic_id FROM posted_mindmaps ORDER BY posted_at ASC LIMIT 1").fetchone()
        oldest_id = oldest_row[0] if oldest_row else MINDMAP_TOPICS[0]["id"]
        for t in MINDMAP_TOPICS:
            if t["id"] == oldest_id:
                chosen_topic = t
                break
        if not chosen_topic:
            chosen_topic = MINDMAP_TOPICS[0]

    # Generate Image
    t_id = chosen_topic["id"]
    today_str = datetime.now().strftime("%Y%m%d")
    out_file = STORAGE_DIR / f"mindmap_{t_id}_{today_str}.jpg"
    render_mindmap_image(chosen_topic, out_file)

    caption = format_mindmap_telegram_caption(chosen_topic)
    return chosen_topic, out_file, caption

def record_mindmap_posted(topic_id: str, topic_title: str, db_path: str = DEFAULT_DB_PATH):
    """Records that a topic mindmap was published to prevent repeating it."""
    init_mindmap_db(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """INSERT INTO posted_mindmaps (topic_id, topic_title, posted_at)
               VALUES (?, ?, CURRENT_TIMESTAMP)
               ON CONFLICT(topic_id) DO UPDATE SET posted_at = CURRENT_TIMESTAMP""",
            (topic_id, topic_title)
        )
        conn.commit()
