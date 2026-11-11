"""
MarketingSalesAgent: Senior Growth Hacker & Conversion Copywriter.
Crafts viral, high-converting Telegram promotional campaigns, teaser questions,
flash sales, and scarcity triggers to sell digital products in the Telegram Channel.
"""

import html
import logging
from typing import Any, Dict, Optional

from .base_agent import BaseSeniorAgent

logger = logging.getLogger(__name__)

class MarketingSalesAgent(BaseSeniorAgent):
    """
    Senior Executive in Direct-Response Copywriting & EdTech Conversion:
    Specializes in Marathi candidate psychology, urgency framing, and social proof.
    """

    def __init__(self):
        super().__init__(
            name="Radhika Deshpande (Chief Growth & Conversion Officer)",
            role="Senior Marketing Strategist & Direct-Response Copywriting Lead",
            seniority="Principal Growth Director (14+ Years in Digital Publishing & Channel Monetization)",
            core_competencies=[
                "High-converting Marathi promotional copy & FOMO hooks",
                "Teaser question marketing (giving 1 free value drop leading to instant purchase)",
                "Micro-pricing psychology (framing ₹19 as 'less than a cup of tea')",
                "Scarcity & limited-time discount drops"
            ],
            system_instruction=(
                "Write persuasive, authoritative, highly engaging Telegram broadcast copy in Marathi. "
                "Always emphasize candidate career protection, marks boosting, and the negligible price (₹19 - ₹49)."
            )
        )

    async def generate_product_promo_post(
        self,
        product: Dict[str, Any],
        store_url: str,
        sample_q: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Generates a high-converting promotional post for a specific digital product.
        """
        title = html.escape(str(product.get("title", "")))
        price = product.get("price_inr", 29)
        orig_price = product.get("original_price_inr", 149)

        sample_text = ""
        if sample_q:
            safe_q = html.escape(str(sample_q.get("question", "")))
            sample_text = (
                f"\n📌 <b>पुस्तकातील नमुना प्रश्न (Sample Question):</b>\n"
                f"❓ <i>{safe_q}</i>\n"
                f"👉 योग्य उत्तर व सविस्तर नियम ई-बुकमध्ये उपलब्ध आहे.\n"
            )

        post = (
            f"🔥 <b>{title}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🎯 <b>TCS व IBPS परीक्षार्थींसाठी खास डिजिटल ई-बुक!</b>\n\n"
            f"💡 <b>फक्त ०.५ किंवा १ मार्कामुळे मेरीट हुकण्याची भीती वाटतेय का?</b>\n"
            f"बाजारात ₹३००-₹४०० ची जाड पुस्तके वाचून गोंधळ उडण्यापेक्षा, चालू परीक्षांमधील <b>अतिसंभाव्य व ट्रॅप प्रश्न</b> एकाच ठिकाणी अभ्यासा!\n\n"
            f"✨ <b>या ई-बुकची वैशिष्ट्ये:</b>\n"
            f"• ✅ १००% चालू TCS/IBPS पॅटर्नवर आधारित\n"
            f"• ⚡ सोप्या भाषेत सविस्तर स्पष्टीकरण व शॉर्ट ट्रिक्स\n"
            f"• 📱 मोबाईल व लॅपटॉपवर कधीही वाचता येणारी PDF फाईल\n"
            f"{sample_text}\n"
            f"🏷️ <b>किंमत:</b> <s>₹{orig_price}</s> <b>फक्त ₹{price}/-</b> (एक चहापेक्षाही कमी किंमत!)\n\n"
            f"👇 <b>खालील लिंकवर क्लिक करून तात्काळ ई-बुक डाऊनलोड करा:</b>\n"
            f"🛒 <a href=\"{store_url}\"><b>येथे क्लिक करा आणि ई-बुक मिळवा (₹{price})</b></a>\n"
            f"<i>(पेमेंट केल्यानंतर तुमच्या Email ID वर तात्काळ PDF पाठवली जाईल!)</i>"
        )
        return post

    async def generate_monthly_current_affairs_drop(self, store_url: str) -> str:
        """
        Generates a promo specifically for the Top 200 Monthly Current Affairs PDF.
        """
        return (
            "🚨 <b>चालू महिन्याचे Top 200 चालू घडामोडी MCQs आता उपलब्ध!</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "महाराष्ट्र शासन निर्णय, लाडकी बहीण योजना, क्रीडा, आंतरराष्ट्रीय परिषदा व नियुक्त्या यांवर TCS नेहमी ३ ते ५ प्रश्न विचारते.\n\n"
            "📖 <b>काय आहे या Top 200 MCQs ई-बुकमध्ये?</b>\n"
            "१. चालू महिन्यातील २०० सर्वात महत्त्वाचे बहुपर्यायी प्रश्न\n"
            "२. प्रत्येक प्रश्नाचे मराठीत २-३ ओळींचे सविस्तर स्पष्टीकरण\n"
            "३. लक्षात ठेवण्यासाठी 'Exam Takeaway' ट्रिक्स\n"
            "४. संपूर्ण रंगीत व सुटसुटीत PDF फॉरमॅट\n\n"
            "💰 <b>किंमत:</b> फक्त <b>₹१९/-</b> (Special Launch Offer)\n\n"
            f"👇 <b>आताच खरेदी करा व Email वर मिळवा:</b>\n"
            f"🔗 <a href=\"{store_url}\"><b>ई-बुक विकत घेण्यासाठी येथे क्लिक करा (₹१९)</b></a>"
        )

