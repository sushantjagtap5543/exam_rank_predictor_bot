# Changelog — ExamRankers™

All notable changes to this project are documented in this file in chronological order.

---

## [v2.0.0-PROD] — 2026-11-08

### Summary
Complete architecture upgrade from prototype to hardened, launch-ready, production-grade platform. Enforces 100% free AI models, Cashfree Payment Gateway, WCAG 2.2 AA mobile-first storefront, and complete security defense-in-depth across 15 autonomous agents.

---

### Part 0: Launch Blockers & Security Hardening
- **Secret Hygiene & Leak Prevention**:
  - Completely purged leaked tokens, channel IDs, invite links, and personal phone/UPI identifiers from `DEPLOY_24_7_FREE_GUIDE.md`, `.env.example`, and codebase.
  - Implemented startup refusal (`validate_environment_security`) when placeholder or known leaked bot tokens are detected.
  - Documented BotFather token revocation protocol.
- **Admin Authentication**:
  - Replaced unauthenticated `/admin` and `/api/admin/*` endpoints with `X-Admin-Key` header authentication using `hmac.compare_digest`.
  - Admin endpoints are disabled by default if `ADMIN_API_KEY` is not explicitly set.
  - Removed wildcard `Access-Control-Allow-Origin: *` from administrative routes.
- **Razorpay Removal**:
  - Eliminated vulnerable, unverified Razorpay checkout flow and replaced with Cashfree.
- **Payment Verification Gate**:
  - Eliminated automatic approval on 8–22 character text or photo receipts.
  - Orders now enter a `pending_verification` state until an authorized Cashfree webhook or admin confirmation is received.
- **Channel Protection**:
  - Restricted channel registration to authorized bot administrators in `ADMIN_IDS`.
  - Added `on_chat_member_updated` guard that forces the bot to immediately leave any unauthorized channel or group.
- **Server-Side Pricing**:
  - Client-submitted `amount` parameters are strictly ignored; prices are fetched server-side from `digital_products` SQLite table (₹10–₹50 INR).
- **SSRF Defense**:
  - Created `validate_safe_url` to restrict response sheet downloads strictly to HTTPS domains (`*.digialm.com`, `*.tcsion.com`, `*.ibpsonline.ibps.in`).
  - Blocked private RFC 1918 IPs, loopbacks, link-local, and cloud metadata endpoints (`169.254.169.254`).
  - Enforced validation on HTTP redirect targets.
- **Signed Download Links**:
  - Implemented HMAC-SHA256 download link signing (`DOWNLOAD_SIGNING_KEY`) with expiration timestamps.
  - `/api/order_status` requires an explicit token and never exposes customer emails or UTRs.
- **DoS & Reliability**:
  - Added 1 MB payload size limit (`413 Payload Too Large`).
  - Implemented per-IP rate limiting on `/api/checkout` (`429 Too Many Requests`).
  - Added Telegram broadcast throttling with `RetryAfter` error handling.
  - Automated nightly SQLite backup API loop (`backup_sqlite_database`).
  - Pinned all exact dependencies in `requirements.txt` for Python 3.12.
  - Hardened `Dockerfile` with non-root user `appuser` and `HEALTHCHECK`.

---

### Part 1: Cashfree Payment Gateway Integration
- Implemented `CashfreeClient` in `app/cashfree_client.py` for Cashfree Orders API `v2023-08-01`.
- Added `POST /api/checkout` returning `order_id` and `payment_session_id`.
- Added `POST /api/cashfree/webhook` verifying `x-webhook-signature` using `HMAC-SHA256(timestamp + raw_body, secret_key)` and enforcing max 300-second drift replay prevention.
- Added `/order/<order_id>` return tracking page with live status polling and 1-click download button.
- Integrated Cashfree JS SDK (`https://sdk.cashfree.com/js/v3/cashfree.js`) into web storefront.

---

### Part 2: Universal Free AI Engine & 15 Agents Upgrade
- Built `UniversalFreeAIClient` (`app/ai_client.py`) enforcing zero paid AI model usage:
  - Strict `:free` model tag enforcement for OpenRouter.
  - 4-tier cascade: Google Gemini 2.0 Flash Free -> Meta LLaMA 3.3 70B Free -> Mistral 7B Free -> Qwen 2.5 72B Free.
  - Circuit breaker (10-minute cooldown on provider outages).
  - Daily soft cap (`AI_DAILY_CAP`) with instant offline fallback.
- Added comprehensive offline Devanagari question banks to senior faculty agents:
  - `MarathiSeniorFacultyAgent` (Sandhi, Samas, Prayog, Kaal, Shuddhalekhan).
  - `EnglishSeniorFacultyAgent` (Subject-Verb Agreement, Prepositions, Error Spotting).
  - `MathsReasoningSeniorFacultyAgent` (15-second shortcut tricks, clock angles, percentages).
- Enforced 6 canonical subject taxonomies across all 15 agents.

---

### Part 3: Storefront Modernization & Accessibility
- Complete UI redesign in `store_static/index.html` and `app/digital_store.py`:
  - Marathi-first bilingual interface with live language toggle (🌐 English / 🌐 मराठी).
  - Mobile-first, responsive layouts verified with zero horizontal scroll at 320px, 360px, 390px, 768px, and 1280px.
  - WCAG 2.2 AA compliance: minimum 44px touch targets and high-contrast color scheme.
  - Replaced unproven social proof with verified credentials ("TCS & IBPS अधिकृत प्रश्नसंच").
  - Linked Web App Manifest (`store_static/manifest.json`) and Schema.org `EducationalOrganization` JSON-LD metadata.
  - Added Legal Compliance Modals for Privacy Policy, Terms of Service, Refund Policy, and Grievance/Contact.

---

### Part 4: Quality Gates & Attack Validation
- Created `test_security_attack_script.py` validating 9 live attack vectors:
  - Vector 1: Admin endpoint auth with `X-Admin-Key` (403 Forbidden on missing/invalid key).
  - Vector 2: Cashfree webhook signature verification (400 Bad Request on forged HMAC).
  - Vector 3: UTR verification queue safety (never auto-approved).
  - Vector 4: Price tampering immunity (catalog price enforced).
  - Vector 5: SSRF protection against private and metadata IPs.
  - Vector 6: Unauthorized channel addition auto-leave.
  - Vector 7: Order status lookup enumeration prevention (token-only).
  - Vector 8: Request size ceiling (413 Payload Too Large on > 1 MB).
  - Vector 9: Expired/tampered download signature rejection (403 Forbidden).
- Configured GitHub Actions CI workflow in `.github/workflows/ci.yml`.
- Created comprehensive `SECURITY.md` documentation.

