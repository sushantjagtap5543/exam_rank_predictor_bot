# ExamRankers™ — Production Exam Rank Predictor & Digital E-Book Store

[![Quality Gate](https://github.com/sushant/exam-rank-predictor-bot/actions/workflows/ci.yml/badge.svg)](.github/workflows/ci.yml)
[![Python Version](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/)
[![Security Verified](https://img.shields.io/badge/security-9%20attack%20vectors%20passed-success.svg)](SECURITY.md)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

An enterprise-grade, high-concurrency educational platform for competitive exam aspirants (TCS, IBPS, MPSC, Police Bharti, Talathi, ZP) featuring:
1. **Free Exam Rank Predictor & Response Sheet Analyzer**: Ingests DigiALM / TCS iON / IBPS response sheet URLs and PDFs to compute marks, section breakdown, negative marking, and cohort rank distributions.
2. **100% Free AI Question Bank & Explanation Engine**: Extracts exam questions and synthesizes explanations using free AI models (`:free` cascade: Gemini 2.0 Flash -> LLaMA 3.3 70B -> Mistral 7B -> Qwen 2.5 72B) with zero API costs.
3. **WCAG 2.2 AA Mobile-First Digital Store**: Sells micro-books, subject mastery guides, and response sheet compendiums priced strictly between ₹10 and ₹50 INR.
4. **Cashfree Payment Gateway Integration**: Production-ready Orders API (v2023-08-01) with HMAC-SHA256 webhook verification, token-only tracking, and signed 1-click expiring downloads.
5. **15 Autonomous Specialist Agents**: Coordinated faculty and fulfillment agents running on additive SQLite schemas with automated nightly backup APIs.

---

## 🏛️ System Architecture

```mermaid
flowchart TD
    subgraph Aspirant Interface
        A[Telegram Bot User] -->|Response Sheet PDF / DigiALM URL| B[app/bot.py / Parser]
        C[Web Store Aspirant] -->|Browse & Purchase E-Books ₹10-₹50| D[store_static/index.html]
    end

    subgraph Security & Ingestion Gates
        B -->|SSRF Guard & Allowlist| E[validate_safe_url]
        D -->|Rate Limiter 10/min & 1MB Cap| F[/api/checkout]
    end

    subgraph Autonomous Faculty & AI Engine
        E --> G[app/ai_client.py: UniversalFreeAIClient]
        G --> H[OpenRouter Free Tier Cascade: Gemini / LLaMA / Mistral]
        H --> I[app/agents/content_faculty_agents.py: 15 Agents]
        I --> J[Offline High-Recall Devanagari Question Banks]
    end

    subgraph Cashfree Payment & Delivery
        F --> K[app/cashfree_client.py: Orders API v2023-08-01]
        K --> L[Cashfree Hosted Checkout JS SDK]
        L --> M[POST /api/cashfree/webhook: HMAC-SHA256 Signature Verify]
        M --> N[Signed Expiring Download Token: /download/<token>?sig=...]
    end

    subgraph Administrative Governance
        O[Admin User] -->|Header: X-Admin-Key == ADMIN_API_KEY| P[/admin & /api/admin/*]
        P --> Q[Dashboard: Revenue, Visitors, Product Catalog, SQLite Backups]
    end
```

---

## 🔒 Security Architecture Highlights

See [SECURITY.md](SECURITY.md) for the full security specification and attack test reports:
- **Admin Authentication**: Timing-safe `hmac.compare_digest` on header `X-Admin-Key == ADMIN_API_KEY`.
- **Cashfree Webhook Defense**: Mandatory HMAC-SHA256 signature verification with 300s replay drift rejection.
- **SSRF Immunity**: Restricts URLs strictly to HTTPS DigiALM/TCS/IBPS domains, resolving DNS and blocking private, loopback, and cloud metadata (`169.254.169.254`) IPs.
- **Server-Side Pricing**: Prices are strictly bound to `digital_products` SQLite table (₹10–₹50 INR); client amounts are ignored.
- **Signed Expiring Downloads**: 24-hour expiring HMAC-SHA256 tokens; order lookup is strictly token-only.
- **Zero Auto-Approval**: Manual payments enter a `pending_verification` queue requiring authorized verification.

---

## ⚙️ Environment Variables Reference

| Variable | Description | Example / Default |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | BotFather API Token | `1234567890:ABCdef...` |
| `ADMIN_TELEGRAM_IDS` | Telegram Admin User IDs | `12345678,87654321` |
| `ADMIN_API_KEY` | Admin Web Dashboard Secret Key | `32+ character random string` |
| `DOWNLOAD_SIGNING_KEY` | Secret for HMAC download tokens | `32+ character random string` |
| `CASHFREE_APP_ID` | Cashfree Merchant App ID | `TEST1000...` |
| `CASHFREE_SECRET_KEY` | Cashfree Merchant Secret Key | `cfsk_ma_test_...` |
| `CASHFREE_ENV` | Cashfree Environment | `sandbox` or `production` |
| `OPENROUTER_API_KEY` | OpenRouter API Key (Free Tier) | `sk-or-v1-...` |
| `OPENROUTER_MODEL` | Primary Free AI Model | `google/gemini-2.0-flash-exp:free` |
| `PORT` | Web Store & Webhook HTTP Port | `8080` |
| `STORE_WEB_URL` | Public Base URL of Storefront | `https://yourdomain.com` |
| `STORAGE_DIR` | Directory for PDF storage | `/app/storage` |
| `DB_PATH` | SQLite Database file path | `/app/storage/bot.db` |

---

## 🧪 Quality Gates & Automated Testing

The codebase includes comprehensive test suites running 1000+ verification checks:

```bash
# 1. 1000 End-to-End Scenarios Suite
python test_1000_scenarios.py

# 2. 100% Free AI Models & Offline Question Bank Suite
python test_free_models_and_qbank.py

# 3. 15 Autonomous Agents Suite
python test_all_agents.py

# 4. Cashfree Payment Gateway & Order Monetization Suite
python test_payment_gateway.py

# 5. Live Security Attack Validation Suite (9 Critical Vectors)
python test_security_attack_script.py
```

---

## 🐳 Docker Production Deployment

Build and run using the hardened non-root container:

```bash
# Build production image
docker build -t examrankers:latest .

# Run with mounted persistent volume
docker run -d \
  --name examrankers \
  -p 8080:8080 \
  -v examrankers_data:/app/storage \
  --env-file .env \
  --restart unless-stopped \
  examrankers:latest
```

---

## 📜 License & Compliance

Distributed under the MIT License. See `LICENSE` for details.
All educational content, sample questions, and syllabi adhere to official TCS, IBPS, and Maharashtra State examination guidelines.
