# ExamRankers India — Production Deployment Checklist

**Target Process:** `python -m app.bot`  
**Deployment Target:** Render (Web Service) / Docker (`Dockerfile`) / Linux VM / Termux  
**Release Version:** Production Acceptance 2.0 (Commit verified)

---

## 1. Required Environment Variables

Configure the following variables in the host dashboard (e.g. Render Environment Variables). Never commit secrets to Git.

| Variable Name | Required | Min Length / Format | Purpose |
| :--- | :---: | :--- | :--- |
| `TELEGRAM_BOT_TOKEN` | **YES** | Standard BotFather format | Bot communication with Telegram API |
| `ADMIN_API_KEY` | **YES** | 32+ random characters | Protection for `/admin` web portal & `/api/admin/*` APIs |
| `DOWNLOAD_SECRET_KEY` | **YES** | 32+ random characters | HMAC-SHA256 signature token for expiring digital store downloads |
| `CASHFREE_APP_ID` | **YES** | App ID from Cashfree | Cashfree payment gateway authentication |
| `CASHFREE_SECRET_KEY`| **YES** | Secret from Cashfree | Cashfree webhook signature verification & order creation |
| `CASHFREE_ENV` | **YES** | `sandbox` or `production` | Cashfree gateway target environment |
| `DATA_DIR` | **YES** | e.g. `/var/data` or `data` | Mounted persistent disk directory for SQLite & PDFs |
| `PORT` | **YES** | Default `10000` or `8080` | Port for HTTP health check, store & admin web server |
| `PAID_CHANNEL_LINK` | Recommended | Valid Telegram link (`https://t.me/...`) | Official community link for student conversion |
| `PAID_CHANNEL_ID` | Optional | Telegram chat ID (`-100...`) | Channel for manual post broadcasting |
| `TELEGRAM_API_ID` | Optional | Integer (from my.telegram.org) | Direct MTProto client fallback for 20MB+ files |
| `TELEGRAM_API_HASH` | Optional | 32-char hex string | Direct MTProto client authentication |
| `OPENROUTER_API_KEY` | Optional | `sk-or-...` | OpenRouter multi-agent AI faculty fallback |

---

## 2. Pre-Deployment Verification Steps

1. **Persistent Storage Mounted:**
   - Confirm persistent disk is attached to `DATA_DIR` (or `/var/data`) so `bot.db` and uploaded response sheets survive service rebuilds.
2. **Secrets Complexity:**
   - Verify `ADMIN_API_KEY` and `DOWNLOAD_SECRET_KEY` are 32+ random alphanumeric/hex characters.
3. **Payment Mode Alignment:**
   - If testing: ensure `CASHFREE_ENV=sandbox` and test credentials are used.
   - If live: ensure `CASHFREE_ENV=production` and production API credentials are configured.
4. **Clean Git Branch:**
   - Check `git status` on `main` branch to ensure no untracked local secrets exist.

---

## 3. Post-Deployment Verification Steps

1. **Health Check Probe:**
   ```bash
   curl -i https://YOUR-APP.onrender.com/health
   # Expected: HTTP 200 OK, body: "OK"
   ```
2. **Storefront Verification:**
   - Open `https://YOUR-APP.onrender.com/` in desktop and mobile viewport.
   - Verify Marathi Devanagari renders cleanly with zero console JavaScript errors.
   - Verify no fake ratings, fake review counts, or false strikethrough prices appear.
3. **Admin Security Probe:**
   - Open `https://YOUR-APP.onrender.com/admin` without key -> Expect **HTTP 403 Forbidden**.
   - Open `https://YOUR-APP.onrender.com/admin?key=YOUR_KEY` -> Expect Admin Command Studio dashboard.
4. **Log Inspection:**
   - Verify the startup log includes:
     `Background Schedulers launched: Daily Current Affairs DB updater, Agency Orchestrator, Nightly Backup`
   - Confirm **NO** log line mentions auto-posting quizzes or promotions.

---

## 4. Rollback and Disaster Recovery

1. **Database Snapshot:**
   - Automatic nightly backups run to `data/backups/bot_backup_*.db`.
   - Before any major upgrade, run manual backup via Admin Panel or shell:
     ```bash
     sqlite3 bot.db ".backup data/backups/manual_pre_release.db"
     ```
2. **Instant Rollback:**
   - If deployment fails, click "Rollback to Previous Commit" in Render dashboard.
   - Previous stable Git commit hash: `5441263`.
