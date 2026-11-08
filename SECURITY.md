# Security Policy — ExamRankers™

ExamRankers is committed to providing a secure, reliable, and compliant educational platform for competitive examination aspirants and administrators. This document outlines our security architecture, defense-in-depth controls, vulnerability reporting process, and secret revocation guidelines.

---

## 1. Reporting a Vulnerability

If you discover a security vulnerability in this repository:
1. **Do not open a public GitHub issue.**
2. Send a detailed report to the security team at **security@examrankers.in** with steps to reproduce.
3. We acknowledge reports within 24 hours and aim to release a patched version within 72 hours under coordinated vulnerability disclosure.

---

## 2. Core Security Architecture & Defense Controls

### 2.1 Admin Authentication (`X-Admin-Key`)
- All administrative endpoints (`/admin`, `/api/admin/*`, `/api/admin/visitors`, `/api/admin/sync_products`) strictly require the HTTP header `X-Admin-Key == ADMIN_API_KEY`.
- Authentication uses constant-time comparison via `hmac.compare_digest` to prevent timing attacks.
- If `ADMIN_API_KEY` is not explicitly set in the server environment, all admin endpoints are completely disabled and return `403 Forbidden`.
- CORS wildcard (`*`) headers have been removed from all administrative routes.

### 2.2 Cashfree Payment Gateway & Order Monetization
- **Orders API v2023-08-01**: Replaced legacy Razorpay and untrusted client-side amount submissions.
- **Strict Server-Side Pricing**: Prices are strictly fetched from the `digital_products` SQLite table (enforced between ₹10 and ₹50 INR). Tampered client amounts (e.g. ₹0.01 or negative values) are ignored.
- **Webhook HMAC-SHA256 Verification**: Cashfree webhooks must include valid `x-webhook-signature` and `x-webhook-timestamp`. Signatures are computed using `HMAC-SHA256(timestamp + raw_body, CASHFREE_SECRET_KEY)` and compared in constant time.
- **Replay Attack Defense**: Webhook timestamps with more than 300 seconds drift are automatically rejected.
- **Zero Auto-Approval**: Telegram UTR submissions and photo receipts are never auto-approved. They enter a `pending_verification` queue requiring official Cashfree webhook confirmation or authorized admin action.

### 2.3 SSRF (Server-Side Request Forgery) Prevention
- Ingestion of exam response sheet URLs is protected by multi-tier validation (`validate_safe_url`):
  1. **HTTPS Enforcement**: Non-HTTPS protocols (`http://`, `ftp://`, `file://`) are immediately rejected.
  2. **Domain Whitelist**: Only authorized domains are permitted (`*.digialm.com`, `*.tcsion.com`, `*.ibpsonline.ibps.in`).
  3. **DNS & IP Resolution Guard**: Resolves hostname via `socket.getaddrinfo` and checks that the IP is not private (`ip.is_private`), loopback (`ip.is_loopback`), link-local (`ip.is_link_local`), reserved (`ip.is_reserved`), or cloud metadata (`169.254.169.254`).
  4. **Redirect Guard**: HTTP redirects (`301`/`302`/`307`) are intercepted and re-validated against `validate_safe_url` before following.

### 2.4 Token-Only Order Status & Signed Digital Downloads
- `/api/order_status` requires an explicit `token` parameter. Order lookup by email or UTR alone is blocked to prevent customer order enumeration.
- Responses never expose raw customer emails or bank transaction UTRs.
- Download links are signed using HMAC-SHA256 (`DOWNLOAD_SIGNING_KEY`), incorporating a UNIX expiration timestamp. Expired or tampered links return `403 Forbidden`.

### 2.5 Request Limits & Denial-of-Service Mitigations
- **Payload Limit**: HTTP POST requests exceeding 1 MB (1,048,576 bytes) are immediately terminated with `413 Payload Too Large`.
- **Per-IP Rate Limiting**: The `/api/checkout` endpoint enforces a strict rate limit (max 10 requests per minute per IP), returning `429 Too Many Requests`.
- **Broadcast Throttling**: Telegram `/broadcast` batches honor `RetryAfter` exceptions and include non-blocking rate-limiting sleeps.

### 2.6 Unauthorized Channel Auto-Leaving
- `on_chat_member_updated` monitors when the bot is added to channels or supergroups. If added by a non-admin Telegram user ID, the bot immediately calls `leave_chat(chat_id)` and refuses registration.

---

## 3. BotFather Token Revocation Protocol

If a bot token was ever exposed in public history or an untrusted environment:
1. Open Telegram and search for [@BotFather](https://t.me/BotFather).
2. Send `/mybots` and select your bot.
3. Select **API Token** -> **Revoke current token**.
4. BotFather will immediately invalidate the old token and generate a new token.
5. Update your deployment environment variable `TELEGRAM_BOT_TOKEN` in your private hosting secrets (e.g. Railway, Render, Docker secret).
6. Restart the application.

---

## 4. Required Production Secrets

Ensure the following environment variables are securely provisioned:

| Variable | Description | Security Requirement |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | BotFather API Token | Private, never commit to git |
| `ADMIN_API_KEY` | Key for admin web dashboard | 32+ char high-entropy secret |
| `DOWNLOAD_SIGNING_KEY` | Key for signing download links | 32+ char high-entropy secret |
| `CASHFREE_APP_ID` | Cashfree Merchant App ID | From Cashfree Merchant Portal |
| `CASHFREE_SECRET_KEY` | Cashfree Secret Key | Private merchant secret |
| `CASHFREE_ENV` | Gateway Environment | `sandbox` (test) or `production` |
| `ADMIN_TELEGRAM_ID` | Telegram numeric ID for admin | Integer ID (comma-separated for multiple) |
| `STORAGE_DIR` | Persistent storage directory | Mounted Docker/Kubernetes volume |
| `DB_PATH` | SQLite Database file path | Must reside in mounted persistent volume |
