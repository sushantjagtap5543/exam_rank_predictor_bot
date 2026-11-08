# 🚀 बॉट २४/७ अखंड लाईव्ह (Live) ठेवण्यासाठी मोफत व सोपे पर्याय
## 24/7 Free & Easy Hosting Guide (No Laptop Needed!)

जेव्हा तुमचा लॅपटॉप बंद असतो, तेव्हा बॉट बंद पडू नये यासाठी **४ सर्वोत्तम १००% मोफत आणि सोपे पर्याय** खाली दिले आहेत. एकाही पर्यायासाठी **क्रेडिट कार्डची आवश्यकता नाही**.

---

### 🏆 पर्याय १: Koyeb (सर्वात सोपा व १००% मोफत क्लाउड पर्याय — No Credit Card)
> **फायदा:** सेटअप अवघ्या २ मिनिटांत होतो. क्रेडिट कार्ड लागत नाही. बॉट अखंड २४ तास चालू राहतो.

1. [Koyeb.com](https://www.koyeb.com/) वर जाऊन मोफत **GitHub ने Sign Up** करा.
2. **"Create App"** वर क्लिक करा.
3. **GitHub** निवडा आणि तुमचे `exam_rank_predictor_bot` रिपॉझिटरी सिलेक्ट करा.
4. **Builder:** Docker निवडा (किंवा Buildpack).
5. **Environment Variables** सेक्शनमध्ये तुमचे सुरक्षित सिक्रेट्स टाका:
   - `TELEGRAM_BOT_TOKEN`: `your_new_bot_token_from_botfather`
   - `ADMIN_API_KEY`: `your_strong_random_secret_hex_key`
   - `ADMIN_TELEGRAM_IDS`: `your_numeric_telegram_id`
   - `PAID_CHANNEL_ID`: `your_telegram_channel_id` (उदा. `-1001234567890`)
   - `PAID_CHANNEL_LINK`: `https://t.me/+YourPrivateChannelLink`
   - `OPENROUTER_API_KEY`: `your_openrouter_free_key`

> [!CAUTION]
> **सुरक्षा सूचना (Revoke Leaked Tokens):**
> जर पूर्वी वापरलेला टेलिग्राम बॉट टोकन लीक झाला असेल, तर लगेच Telegram मध्ये **@BotFather** कडे जाऊन `/revoke` कमांड देऊन नवीन टोकन जनरेट करा. सिस्टीम जुन्या किंवा लीक झालेल्या टोकन्सचा वापर करण्यास नकार देईल.
6. **"Deploy"** वर क्लिक करा!
   - बॉट लगेच २४/७ लाईव्ह सुरू होईल.

---

### 🌟 पर्याय २: Hugging Face Spaces (कधीही झोपत नाही — 100% Free Forever)
> **फायदा:** १६ GB RAM, २ CPU मोफत. कधीही स्लीप (Sleep) होत नाही. क्रेडिट कार्डची गरज नाही.

1. [HuggingFace.co](https://huggingface.co/) वर मोफत अकाऊंट उघडा.
2. उजव्या कोपऱ्यात प्रोफाइलवर क्लिक करून **"New Space"** दाबा.
3. **Space Name:** `exam-rankers-bot`
4. **Space SDK:** **Docker** (Blank) निवडा.
5. **Visibility:** Public किंवा Private (दोन्ही मोफत आहेत).
6. **"Settings" ➔ "Variables and secrets"** वर जा आणि **New Secret** जोडा:
   - `TELEGRAM_BOT_TOKEN`
   - `PAID_CHANNEL_ID`
   - `ADMIN_USER_IDS`
   - `OPENROUTER_API_KEY`
7. तुमचे कोड फाईल्स (Files) Hugging Face वर अपलोड करा किंवा Git Push करा.
8. बॉट आपोआप बिल्ड होऊन २४/७ अखंड चालू राहील!

---

### ⚡ पर्याय ३: Render (Free Web Service) + UptimeRobot (Free Ping)
> **फायदा:** आधीपासूनच रिपॉझिटरीमध्ये `render.yaml` कॉन्फिगर केलेले आहे.

1. [Render.com](https://render.com/) वर मोफत अकाउंट तयार करा.
2. **"New +" ➔ "Web Service"** निवडा आणि तुमचे GitHub रिपॉझिटरी कनेक्ट करा.
3. **Plan:** Free ($0/month) निवडा.
4. **Environment Variables** जोडा (`TELEGRAM_BOT_TOKEN`, `PAID_CHANNEL_ID`, इत्यादी).
5. डिप्लॉय झाल्यानंतर Render तुम्हाला एक मोफत URL देईल (उदा. `https://exam-rankers-bot.onrender.com`).
6. आता [UptimeRobot.com](https://uptimerobot.com/) वर मोफत अकाउंट उघडा:
   - **Add New Monitor** दाबा.
   - **Monitor Type:** HTTP(s)
   - **URL:** तुमची Render ची URL टाका.
   - **Monitoring Interval:** 5 minutes.
7. यामुळे Render चा सर्व्हर कधीही स्लीप होणार नाही आणि बॉट अखंड २४/७ चालू राहील!

---

### 📱 पर्याय ४: जुना अँड्रॉइड मोबाईल (Android Phone + Termux — घरातूनच 100% मोफत)
> **फायदा:** कोणत्याही क्लाउड खात्याची किंवा इंटरनेट होस्टिंगची गरज नाही. घरातील जुना मोबाईल वायफायवर लावून ठेवल्यास बॉट २४/७ चालू राहतो.

1. मोबाईलमध्ये गुगलवरून किंवा F-Droid वरून **Termux** ॲप इन्स्टॉल करा.
2. Termux ॲप उघडा आणि खालील १ कमांड पेस्ट करा:
```bash
pkg update -y && pkg install -y git python && git clone https://github.com/YOUR_USERNAME/exam_rank_predictor_bot.git && cd exam_rank_predictor_bot && bash termux_setup.sh
```
3. `termux-wake-lock` मुळे मोबाईलची स्क्रीन बंद असली तरीही बॉट अखंड चालू राहतो!

---

### ✅ बॉट लाईव्ह आहे हे कसे तपासावे?
कोणत्याही ब्राऊझरमध्ये तुमच्या क्लाउडची URL उघडल्यास तुम्हाला थेट डॅशबोर्ड दिसेल:
`🟢 24/7 LIVE & RUNNING — ExamRankers India Bot`
आणि टेलिग्रामवर `/start` करताच बॉट लगेच उत्तर देईल!
