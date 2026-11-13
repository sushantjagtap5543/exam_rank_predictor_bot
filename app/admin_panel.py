"""
ExamRankers™ Web Admin Command Center
=====================================
A sleek, high-performing web administration studio for full manual control of ExamRankers Store.
Features:
- Complete Manual Product CRUD (Create, Read, Update, Delete, Toggle Active/Inactive)
- 1-Click Price Editor (₹10 - ₹100)
- Direct PDF File Upload & Instant Product Registration
- Purge Auto-Generated/Seeded Products with 1-Click
- Real-time KPI Metrics (Visitors, Sales, Checkouts, Digital Products)
- Live Visitor Tracking (IP, Device, Action)
- Order Management with 1-Click UTR Approval & Rejection
"""

import html as html_lib
import json
import os
import sqlite3


def render_admin_dashboard_html(db_path: str = "bot.db") -> str:
    """Renders the complete responsive Web Admin Dashboard HTML with full manual store control."""
    total_visits = 0
    unique_ips = 0
    mobile_cnt = 0
    desktop_cnt = 0
    checkouts = 0
    purchases = 0
    total_revenue = 0.0
    products = []
    recent_visitors = []
    recent_orders = []
    recent_uploads = []
    total_uploads_cnt = 0
    recent_qbank = []
    total_qbank_cnt = 0
    total_users_cnt = 0
    db_size_mb = 0.0

    try:
        if os.path.exists(db_path):
            db_size_mb = round(os.path.getsize(db_path) / (1024 * 1024), 2)
    except Exception:
        pass

    try:
        with sqlite3.connect(db_path, timeout=30.0) as db:
            db.row_factory = sqlite3.Row
            # Visitor Stats
            try:
                total_visits = db.execute("SELECT count(*) FROM store_visitors").fetchone()[0]
                unique_ips = db.execute("SELECT count(DISTINCT ip_address) FROM store_visitors").fetchone()[0]
                mobile_cnt = db.execute("SELECT count(*) FROM store_visitors WHERE device_type = 'Mobile'").fetchone()[0]
                desktop_cnt = db.execute("SELECT count(*) FROM store_visitors WHERE device_type = 'Desktop'").fetchone()[0]
                checkouts = db.execute("SELECT count(*) FROM store_visitors WHERE action = 'checkout_initiated'").fetchone()[0]
                purchases = db.execute("SELECT count(*) FROM store_visitors WHERE action = 'payment_verified'").fetchone()[0]
                recent_visitors = [dict(r) for r in db.execute("SELECT * FROM store_visitors ORDER BY id DESC LIMIT 40").fetchall()]
            except Exception:
                pass

            # Digital Products (Both Active and Inactive for Admin - newest uploaded first)
            try:
                prods_rows = db.execute("SELECT * FROM digital_products ORDER BY rowid DESC").fetchall()
                products = [dict(r) for r in prods_rows]
            except Exception:
                pass

            # Product Orders & Revenue
            try:
                orders_rows = db.execute("""
                    SELECT o.*, p.title as prod_title 
                    FROM product_orders o 
                    LEFT JOIN digital_products p ON o.product_id = p.id 
                    ORDER BY o.id DESC LIMIT 100
                """).fetchall()
                recent_orders = [dict(r) for r in orders_rows]
                rev_row = db.execute("SELECT sum(amount_paid) FROM product_orders WHERE status IN ('delivered', 'approved', 'paid')").fetchone()
                if rev_row and rev_row[0]:
                    total_revenue = float(rev_row[0])
            except Exception:
                pass

            # Candidate Uploads & Scorecards
            try:
                total_uploads_cnt = db.execute("SELECT count(*) FROM uploads").fetchone()[0]
                recent_uploads = [dict(r) for r in db.execute("SELECT * FROM uploads ORDER BY id DESC LIMIT 50").fetchall()]
            except Exception:
                pass

            # Central Harvested Question Bank
            try:
                total_qbank_cnt = db.execute("SELECT count(*) FROM qbank_questions").fetchone()[0]
                recent_qbank = [dict(r) for r in db.execute("SELECT * FROM qbank_questions ORDER BY id DESC LIMIT 30").fetchall()]
            except Exception:
                pass

            # Registered Users
            try:
                total_users_cnt = db.execute("SELECT count(*) FROM users").fetchone()[0]
            except Exception:
                pass
    except Exception:
        pass

    active_products_cnt = sum(1 for p in products if p.get("is_active", 1) == 1)
    inactive_products_cnt = len(products) - active_products_cnt

    # Build Product Rows HTML
    product_rows_html = []
    for p in products:
        p_id = p.get("id", "")
        title = p.get("title", "")
        subtitle = p.get("subtitle", "")
        subject = p.get("subject", "General")
        price = int(p.get("price_inr", 19))
        orig_price = int(p.get("original_price_inr", 99))
        pages = p.get("pages", 48)
        dl_file = p.get("download_file", "")
        icon = p.get("icon", "📚")
        badge = p.get("badge", "HOT")
        desc = p.get("description", "")
        is_active = p.get("is_active", 1)

        # JSON escape for modal edit button
        p_json = json.dumps({
            "id": p_id,
            "title": title,
            "subtitle": subtitle,
            "subject": subject,
            "price_inr": price,
            "original_price_inr": orig_price,
            "pages": pages,
            "download_file": dl_file,
            "icon": icon,
            "badge": badge,
            "description": desc,
            "is_active": is_active
        }).replace('"', '&quot;').replace("'", "&#39;")

        safe_title = html_lib.escape(title)
        safe_subtitle = html_lib.escape(subtitle)
        safe_subject = html_lib.escape(subject)
        safe_badge = html_lib.escape(badge)
        safe_pid = html_lib.escape(p_id)
        safe_dl_file = html_lib.escape(dl_file)

        product_rows_html.append(f"""
            <tr id="row_{safe_pid}">
                <td style="font-size:18px; text-align:center;">{icon}</td>
                <td>
                    <b style="color:#ffffff; font-size:14px;">{safe_title}</b><br>
                    <span style="font-size:11.5px; color:#94a3b8;">ID: <code>{safe_pid}</code> | 📄 {pages} पृष्ठे | <span class="badge badge-gray">{safe_badge}</span></span>
                </td>
                <td><span class="badge badge-sub">{safe_subject}</span></td>
                <td>
                    <div style="display:flex; align-items:center; gap:6px;">
                        <span>₹</span>
                        <input type="number" id="price_{safe_pid}" value="{price}" min="10" max="100" class="input-mini">
                        <button class="btn-sm btn-action" onclick="updateProductPrice('{safe_pid}')">💾</button>
                    </div>
                </td>
                <td style="text-align:center;">
                    {f'<a href="/admin/download_pdf?file={safe_dl_file}" class="btn-sm btn-link" target="_blank">📥 {safe_dl_file[:14]}...</a>' if safe_dl_file else '<span style="color:#64748b; font-size:11px;">PDF नाही</span>'}
                </td>
                <td style="text-align:center;">
                    <span class="status-pill {'status-active' if is_active else 'status-inactive'}">
                        {'सक्रिय (Active)' if is_active else 'लपवले (Hidden)'}
                    </span>
                </td>
                <td style="text-align:center;">
                    <div style="display:flex; gap:6px; justify-content:center;">
                        <button class="btn-sm btn-toggle" title="स्थिती बदला (Toggle Active/Hidden)" onclick="toggleProductStatus('{safe_pid}')">
                            {'👁️ लपवा' if is_active else '✅ सुरू करा'}
                        </button>
                        <button class="btn-sm btn-edit" title="संपादित करा (Edit Product)" onclick='openEditModal({p_json})'>
                            ✏️ Edit
                        </button>
                        <button class="btn-sm btn-del" title="कायमचे हटवा (Delete Product)" onclick="deleteProduct('{safe_pid}')">
                            🗑️
                        </button>
                    </div>
                </td>
            </tr>
        """)

    # Build Visitor Rows HTML
    visitor_rows_html = []
    for v in recent_visitors:
        ip = v.get("ip_address", "")
        dev = v.get("device_type", "Desktop")
        action = v.get("action", "")
        page = v.get("page_path", "/")
        prod_id = v.get("product_id") or "—"
        ts = v.get("created_at", "")

        action_badge = "badge-gray"
        if action == "payment_verified":
            action_badge = "badge-green"
        elif action == "checkout_initiated":
            action_badge = "badge-yellow"
        elif action == "download_pdf":
            action_badge = "badge-blue"

        safe_ip = html_lib.escape(str(ip))
        safe_dev = html_lib.escape(str(dev))
        safe_action = html_lib.escape(str(action))
        safe_page = html_lib.escape(str(page))
        safe_prod_id = html_lib.escape(str(prod_id))
        safe_ts = html_lib.escape(str(ts))

        visitor_rows_html.append(f"""
            <tr>
                <td><code>{safe_ip}</code></td>
                <td>{'📱' if dev == 'Mobile' else '💻'} {safe_dev}</td>
                <td><span class="badge {action_badge}">{safe_action}</span></td>
                <td><span style="color:#cbd5e1; font-size:12px;">{safe_page}</span></td>
                <td><span style="color:#94a3b8; font-size:11.5px;">{safe_prod_id}</span></td>
                <td style="color:#64748b; font-size:11px;">{safe_ts}</td>
            </tr>
        """)

    # Compute order stats
    pending_count = sum(1 for o in recent_orders if o.get("status") in ("pending", "pending_verification", "created"))
    approved_count = sum(1 for o in recent_orders if o.get("status") in ("approved", "delivered", "paid"))
    rejected_count = sum(1 for o in recent_orders if o.get("status") == "rejected")

    # Build Order Rows HTML
    order_rows_html = []
    for o in recent_orders:
        token = o.get("order_token", "")
        email = o.get("customer_email", "")
        prod_title = o.get("prod_title") or o.get("product_id") or "Digital E-Book"
        amount = o.get("amount_paid", 19)
        utr = o.get("utr", "—")
        status = o.get("status", "pending")
        delivery_status = o.get("delivery_status", "pending")
        ts = o.get("created_at", "")

        deliv_badge = "badge-gray"
        if delivery_status in ("sent", "delivered", "ready_for_download"):
            deliv_badge = "badge-green"
        elif delivery_status == "pending_verification":
            deliv_badge = "badge-yellow"
        elif delivery_status == "rejected":
            deliv_badge = "badge-rose"

        safe_token = html_lib.escape(str(token))
        safe_email = html_lib.escape(str(email))
        safe_prod_title = html_lib.escape(str(prod_title))
        safe_utr = html_lib.escape(str(utr))
        safe_status = html_lib.escape(str(status))
        safe_deliv = html_lib.escape(str(delivery_status))
        safe_ts = html_lib.escape(str(ts))

        action_btns = ""
        if status in ("pending", "pending_verification", "created"):
            action_btns = f"""
                <div style="display:flex; gap:6px; justify-content:center; flex-wrap:wrap;">
                    <button class="btn-sm btn-green" title="पेमेंट मंजूर करा व विद्यार्थ्याचे डाऊनलोड बटण सुरू करा" onclick="orderAction('{safe_token}', 'approve')">✅ मंजूर करा (Enable Download)</button>
                    <button class="btn-sm btn-del" title="ऑर्डर नाकारा" onclick="orderAction('{safe_token}', 'reject')">❌ नाकारा</button>
                    <a href="/download/{safe_token}" target="_blank" class="btn-sm btn-outline" style="text-decoration:none;" title="संबंधित PDF तपासा">📥 फाईल पहा</a>
                </div>
            """
        elif status in ("approved", "delivered", "paid"):
            action_btns = f"""
                <div style="display:flex; gap:6px; justify-content:center; flex-wrap:wrap; align-items:center;">
                    <span class="badge badge-green" style="font-size:11px;">✅ Download Enabled</span>
                    <a href="/order/{safe_token}" target="_blank" class="btn-sm btn-green" style="text-decoration:none; padding:4px 10px; font-weight:700;" title="विद्यार्थ्याची ऑर्डर पान पहा">📄 Order Page</a>
                </div>
            """
        else:
            action_btns = f"""
                <div style="display:flex; gap:6px; justify-content:center; flex-wrap:wrap;">
                    <button class="btn-sm btn-green" title="पुन्हा तपासून डाऊनलोड सुरू करा" onclick="orderAction('{safe_token}', 'approve')">🔄 पुन्हा मंजूर करा (Enable Download)</button>
                </div>
            """

        status_class = "status-pending"
        if status in ("approved", "delivered", "paid"):
            status_class = "status-active"
        elif status == "rejected":
            status_class = "status-rejected"

        order_rows_html.append(f"""
            <tr class="order-row" data-status="{status}">
                <td><code>{safe_token}</code></td>
                <td>
                    <b style="color:#ffffff;">{safe_email}</b><br>
                    <span style="font-size:11px; color:#94a3b8;">📖 {safe_prod_title[:28]}</span>
                </td>
                <td style="color:#10b981; font-weight:700;">₹{amount}</td>
                <td><code style="background:rgba(250,204,21,0.1); color:var(--accent-gold); padding:3px 7px; border-radius:4px; font-weight:700;">{safe_utr}</code></td>
                <td>
                    <span class="status-pill {status_class}">
                        {safe_status.upper()}
                    </span><br>
                    <span class="badge {deliv_badge}" style="font-size:10px; margin-top:3px;">{safe_deliv}</span>
                </td>
                <td style="color:#64748b; font-size:11px;">{safe_ts}</td>
                <td style="text-align:center;">{action_btns}</td>
            </tr>
        """)

    # Build Candidate Upload Rows HTML
    upload_rows_html = []
    for u in recent_uploads:
        u_id = u.get("id", 0)
        u_name = html_lib.escape(str(u.get("candidate_name") or "परीक्षार्थी"))
        u_roll = html_lib.escape(str(u.get("roll_number") or "-"))
        u_exam = html_lib.escape(str(u.get("exam_key") or "ZP_BHARTI"))
        u_cat = html_lib.escape(str(u.get("category") or "Open"))
        u_score = u.get("score", 0.0)
        u_rank = u.get("rank", 1)
        u_src = html_lib.escape(str(u.get("status") or "upload"))
        u_date = html_lib.escape(str(u.get("created_at") or "")[:19])

        upload_rows_html.append(f"""
            <tr id="upload_row_{u_id}">
                <td style="font-weight:700; color:#94a3b8;">#{u_id}</td>
                <td>
                    <b style="color:#ffffff;">{u_name}</b><br>
                    <span style="font-size:11.5px; color:#94a3b8;">रोल: <code>{u_roll}</code></span>
                </td>
                <td><span class="badge badge-sub">{u_exam}</span></td>
                <td><span style="font-size:12px; color:#cbd5e1;">{u_cat}</span></td>
                <td><b style="color:var(--accent-gold); font-size:14px;">{u_score}</b></td>
                <td><span class="badge badge-green">#{u_rank}</span></td>
                <td><span class="badge badge-gray">{u_src}</span></td>
                <td style="color:#64748b; font-size:11px;">{u_date}</td>
                <td style="text-align:center;">
                    <button class="btn-sm btn-del" title="हटवा" onclick="deleteUploadRecord({u_id})">🗑️ Delete</button>
                </td>
            </tr>
        """)

    # Build Harvested Question Bank Rows HTML
    qbank_rows_html = []
    for q in recent_qbank:
        q_id = q.get("id", 0)
        q_sec = html_lib.escape(str(q.get("section") or "General"))
        q_exam = html_lib.escape(str(q.get("exam_key") or "ZP_BHARTI"))
        q_txt = html_lib.escape(str(q.get("question_text") or "")[:120])
        q_cnum = q.get("correct_option_num", 1)
        q_src = html_lib.escape(str(q.get("source") or "web_upload"))

        qbank_rows_html.append(f"""
            <tr>
                <td style="font-weight:700; color:#94a3b8;">#{q_id}</td>
                <td><span class="badge badge-sub">{q_sec}</span></td>
                <td><span style="font-size:12px; color:#cbd5e1;">{q_exam}</span></td>
                <td><span style="color:#f1f5f9; font-size:12.5px;">{q_txt}...</span></td>
                <td style="text-align:center;"><span class="badge badge-green">पर्याय {q_cnum}</span></td>
                <td><span class="badge badge-gray">{q_src}</span></td>
            </tr>
        """)

    empty_products_html = '<tr><td colspan="7" style="text-align:center; padding:36px; color:#94a3b8; font-size:14px;">📭 सध्या स्टोअरमध्ये कोणतेही प्रॉडक्ट नाही.<br><br><button class="btn btn-gold" onclick="openAddModal()">➕ पहिले ई-बुक जोडा</button> किंवा <button class="btn btn-outline" onclick="document.getElementById(\'pdfFileInput\').click()">📁 PDF अपलोड करा</button></td></tr>'
    products_tbody_content = "".join(product_rows_html) if product_rows_html else empty_products_html

    html = f"""<!DOCTYPE html>
<html lang="mr">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ExamRankers™ Admin Studio & Command Center</title>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=Noto+Sans+Devanagari:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg-base: #090d16;
            --bg-surface: #0f172a;
            --bg-card: #151f32;
            --border: #23324a;
            --accent-gold: #facc15;
            --accent-emerald: #10b981;
            --accent-cyan: #38bdf8;
            --accent-rose: #f43f5e;
            --text-main: #f8fafc;
            --text-muted: #94a3b8;
        }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            background: var(--bg-base);
            color: var(--text-main);
            font-family: 'Plus Jakarta Sans', 'Noto Sans Devanagari', sans-serif;
            font-size: 13.5px;
            padding-bottom: 60px;
        }}
        .topbar {{
            background: var(--bg-surface);
            border-bottom: 1px solid var(--border);
            padding: 14px 28px;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }}
        .brand {{
            font-size: 18px;
            font-weight: 800;
            display: flex;
            align-items: center;
            gap: 10px;
            color: #ffffff;
        }}
        .brand span {{ color: var(--accent-gold); }}
        .header-actions {{
            display: flex;
            align-items: center;
            gap: 10px;
        }}
        .btn {{
            background: #2563eb;
            color: #ffffff;
            border: none;
            padding: 8px 16px;
            border-radius: 8px;
            font-weight: 700;
            font-size: 13px;
            cursor: pointer;
            text-decoration: none;
            display: inline-flex;
            align-items: center;
            gap: 6px;
            transition: all 0.2s;
        }}
        .btn:hover {{ opacity: 0.9; transform: translateY(-1px); }}
        .btn-gold {{ background: var(--accent-gold); color: #0f172a; }}
        .btn-green {{ background: var(--accent-emerald); color: #0f172a; }}
        .btn-purple {{ background: #7c3aed; color: #ffffff; }}
        .btn-danger {{ background: #dc2626; color: #ffffff; }}
        .btn-outline {{ background: transparent; border: 1px solid var(--border); color: #ffffff; }}

        .container {{
            max-width: 1350px;
            margin: 0 auto;
            padding: 24px;
        }}

        /* KPI Cards */
        .kpi-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 16px;
            margin-bottom: 24px;
        }}
        .kpi-card {{
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 18px 20px;
            position: relative;
            overflow: hidden;
        }}
        .kpi-title {{
            font-size: 12px;
            font-weight: 700;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 6px;
        }}
        .kpi-val {{
            font-size: 28px;
            font-weight: 800;
            color: #ffffff;
        }}
        .kpi-sub {{
            font-size: 11.5px;
            color: #64748b;
            margin-top: 4px;
        }}

        /* Action Toolbar */
        .toolbar {{
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 16px 20px;
            margin-bottom: 24px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 12px;
            flex-wrap: wrap;
        }}

        /* Section Box & Tables */
        .section-box {{
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 24px;
        }}
        .section-header {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 16px;
            flex-wrap: wrap;
            gap: 10px;
        }}
        .section-title {{
            font-size: 16px;
            font-weight: 800;
            color: #ffffff;
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        .table-wrap {{
            overflow-x: auto;
        }}
        .visitors-scroll-wrap {{
            max-height: 265px;
            overflow-y: auto;
            overflow-x: auto;
            scroll-behavior: smooth;
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 8px;
        }}
        .visitors-scroll-wrap thead th {{
            position: sticky;
            top: 0;
            z-index: 5;
            background: #0f172a;
            box-shadow: 0 1px 0 var(--border);
        }}
        .visitors-scroll-wrap::-webkit-scrollbar {{
            width: 8px;
            height: 8px;
        }}
        .visitors-scroll-wrap::-webkit-scrollbar-track {{
            background: #090d16;
            border-radius: 4px;
        }}
        .visitors-scroll-wrap::-webkit-scrollbar-thumb {{
            background: #334155;
            border-radius: 4px;
        }}
        .visitors-scroll-wrap::-webkit-scrollbar-thumb:hover {{
            background: var(--accent-gold);
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 13px;
        }}
        th {{
            background: #0f172a;
            color: var(--text-muted);
            text-align: left;
            padding: 12px 14px;
            font-weight: 700;
            border-bottom: 1px solid var(--border);
            font-size: 11.5px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        td {{
            padding: 12px 14px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.05);
            color: #e2e8f0;
            vertical-align: middle;
        }}
        tr:hover td {{
            background: rgba(255, 255, 255, 0.02);
        }}

        .badge {{
            display: inline-block;
            padding: 3px 8px;
            border-radius: 6px;
            font-size: 11px;
            font-weight: 700;
        }}
        .badge-sub {{ background: rgba(56, 189, 248, 0.15); color: var(--accent-cyan); border: 1px solid rgba(56, 189, 248, 0.3); }}
        .badge-green {{ background: rgba(16, 185, 129, 0.15); color: var(--accent-emerald); }}
        .badge-yellow {{ background: rgba(250, 204, 21, 0.15); color: var(--accent-gold); }}
        .badge-blue {{ background: rgba(37, 99, 235, 0.2); color: #60a5fa; }}
        .badge-gray {{ background: rgba(255, 255, 255, 0.08); color: #cbd5e1; }}

        .input-mini {{
            width: 60px;
            background: #090d16;
            border: 1px solid var(--border);
            color: #ffffff;
            padding: 4px 6px;
            border-radius: 6px;
            font-size: 13px;
            font-weight: 700;
            text-align: center;
        }}
        .btn-sm {{
            padding: 5px 10px;
            font-size: 11.5px;
            border-radius: 6px;
            font-weight: 700;
            cursor: pointer;
            border: none;
            display: inline-flex;
            align-items: center;
            gap: 4px;
            text-decoration: none;
        }}
        .btn-action {{ background: #2563eb; color: #fff; }}
        .btn-link {{ background: rgba(56, 189, 248, 0.15); color: var(--accent-cyan); border: 1px solid rgba(56, 189, 248, 0.3); }}
        .btn-edit {{ background: rgba(250, 204, 21, 0.15); color: var(--accent-gold); border: 1px solid rgba(250, 204, 21, 0.3); }}
        .btn-toggle {{ background: rgba(148, 163, 184, 0.15); color: #cbd5e1; border: 1px solid rgba(148, 163, 184, 0.3); }}
        .btn-del {{ background: rgba(239, 68, 68, 0.15); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.3); }}

        .status-pill {{
            padding: 3px 10px;
            border-radius: 999px;
            font-size: 11px;
            font-weight: 700;
        }}
        .status-active {{ background: rgba(16, 185, 129, 0.15); color: var(--accent-emerald); border: 1px solid rgba(16, 185, 129, 0.3); }}
        .status-inactive {{ background: rgba(148, 163, 184, 0.15); color: #94a3b8; border: 1px solid rgba(148, 163, 184, 0.3); }}
        .status-pending {{ background: rgba(250, 204, 21, 0.15); color: var(--accent-gold); border: 1px solid rgba(250, 204, 21, 0.3); }}
        .status-rejected {{ background: rgba(239, 68, 68, 0.15); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.3); }}

        .filter-tab {{
            background: #090d16;
            border: 1px solid var(--border);
            color: var(--text-muted);
            padding: 5px 12px;
            border-radius: 8px;
            font-size: 11.5px;
            cursor: pointer;
            font-weight: 600;
            transition: all 0.2s;
        }}
        .filter-tab:hover, .filter-tab.active {{
            background: var(--bg-card);
            color: var(--accent-gold);
            border-color: var(--accent-gold);
        }}

        /* Modal Styles */
        .modal-overlay {{
            position: fixed;
            top: 0; left: 0; right: 0; bottom: 0;
            background: rgba(0, 0, 0, 0.8);
            backdrop-filter: blur(5px);
            display: none;
            align-items: center;
            justify-content: center;
            z-index: 1000;
            padding: 20px;
        }}
        .modal {{
            background: var(--bg-surface);
            border: 1px solid var(--border);
            border-radius: 14px;
            width: 100%;
            max-width: 600px;
            max-height: 90vh;
            overflow-y: auto;
            padding: 24px;
            position: relative;
            box-shadow: 0 20px 50px rgba(0, 0, 0, 0.6);
        }}
        .modal-close {{
            position: absolute;
            top: 16px; right: 16px;
            background: none;
            border: none;
            color: #94a3b8;
            font-size: 22px;
            cursor: pointer;
        }}
        .form-group {{
            margin-bottom: 14px;
            text-align: left;
        }}
        .form-label {{
            display: block;
            font-size: 12px;
            font-weight: 700;
            color: #cbd5e1;
            margin-bottom: 5px;
        }}
        .form-input, .form-select, .form-textarea {{
            width: 100%;
            background: #090d16;
            border: 1px solid var(--border);
            color: #ffffff;
            padding: 10px 12px;
            border-radius: 8px;
            font-size: 13.5px;
            outline: none;
        }}
        .form-input:focus, .form-select:focus, .form-textarea:focus {{
            border-color: var(--accent-gold);
        }}
        .form-row {{
            display: flex;
            gap: 12px;
        }}
        .form-row .form-group {{
            flex: 1;
        }}

        /* Bulk Upload Dropzone & List Styles */
        .dropzone-box {{
            border: 2px dashed #334155;
            border-radius: 12px;
            padding: 24px;
            text-align: center;
            background: rgba(15, 23, 42, 0.6);
            cursor: pointer;
            transition: all 0.25s ease;
            margin-bottom: 14px;
        }}
        .dropzone-box:hover, .dropzone-box.drag-over {{
            border-color: var(--accent-gold);
            background: rgba(250, 204, 21, 0.05);
        }}
        .bulk-progress-bar {{
            width: 100%;
            height: 8px;
            background: #1e293b;
            border-radius: 4px;
            overflow: hidden;
            margin: 12px 0;
            display: none;
        }}
        .bulk-progress-fill {{
            height: 100%;
            width: 0%;
            background: linear-gradient(90deg, #2563eb, var(--accent-emerald));
            transition: width 0.2s ease;
        }}
        .bulk-file-list {{
            max-height: 200px;
            overflow-y: auto;
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 8px;
            background: #090d16;
            margin-bottom: 14px;
            display: none;
        }}
        .bulk-file-item {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 6px 10px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.05);
            font-size: 12px;
            color: #cbd5e1;
        }}
        .bulk-file-item:last-child {{
            border-bottom: none;
        }}
    </style>
</head>
<body>

    <!-- Header Navigation -->
    <header class="topbar">
        <div class="brand">
            <span style="font-size:22px;">⚙️</span>
            <div>ExamRankers™ <span>Admin Studio</span></div>
        </div>
        <div class="header-actions">
            <a href="/" target="_blank" class="btn btn-outline">🛒 स्टोअर उघडा (Public Store)</a>
            <a href="https://t.me/ExamRankersIndiaBot" target="_blank" class="btn btn-outline">🤖 Telegram Bot</a>
            <button class="btn btn-gold" onclick="openAddModal()">➕ नवीन ई-बुक जोडा</button>
            <button class="btn btn-outline" style="border-color:#ef4444; color:#f87171;" onclick="handleLogout()">🚪 लॉगआउट</button>
        </div>
    </header>

    <main class="container">

        <!-- KPI Grid -->
        <div class="kpi-grid">
            <div class="kpi-card">
                <div class="kpi-title">📦 सक्रिय उत्पादने (Active Products)</div>
                <div class="kpi-val" style="color:var(--accent-emerald);">{active_products_cnt}</div>
                <div class="kpi-sub">लपवलेली उत्पादने: <b>{inactive_products_cnt}</b> | एकूण: <b>{len(products)}</b></div>
            </div>
            <div class="kpi-card">
                <div class="kpi-title">👥 एकूण व्हिजिटर्स (Store Visitors)</div>
                <div class="kpi-val" style="color:var(--accent-cyan);">{total_visits}</div>
                <div class="kpi-sub">युनिक आयपी: <b>{unique_ips}</b> (📱 {mobile_cnt} | 💻 {desktop_cnt})</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-title">🛒 चेकआउट्स (Checkout Initiated)</div>
                <div class="kpi-val" style="color:var(--accent-gold);">{checkouts}</div>
                <div class="kpi-sub">कन्वर्जन दर: <b>{round((purchases/max(checkouts, 1))*100, 1)}%</b></div>
            </div>
            <div class="kpi-card">
                <div class="kpi-title">💰 एकूण महसूल (Verified Revenue)</div>
                <div class="kpi-val" style="color:var(--accent-emerald);">₹{int(total_revenue) or (purchases * 29)}</div>
                <div class="kpi-sub">एकूण यशस्वी खरेदी: <b>{purchases}</b></div>
            </div>
            <div class="kpi-card">
                <div class="kpi-title">📑 एकूण रिस्पॉन्स शीट्स (Uploads)</div>
                <div class="kpi-val" style="color:var(--accent-cyan);">{total_uploads_cnt}</div>
                <div class="kpi-sub">वेब व टेलिग्राम बॉट निकाल</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-title">🧠 केंद्रीय प्रश्नसंच (Q-Bank)</div>
                <div class="kpi-val" style="color:var(--accent-gold);">{total_qbank_cnt}</div>
                <div class="kpi-sub">अचूक TCS/IBPS प्रश्न</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-title">🤖 नोंदणीकृत सदस्य (Bot Users)</div>
                <div class="kpi-val" style="color:var(--accent-emerald);">{total_users_cnt}</div>
                <div class="kpi-sub">बॉट ॲक्टिव्ह परीक्षार्थी</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-title">💾 डेटाबेस व मेमरी (DB Health)</div>
                <div class="kpi-val" style="color:var(--accent-emerald);">{db_size_mb} MB</div>
                <div class="kpi-sub"><button onclick="optimizeSystemNow()" style="background:none; border:none; color:var(--accent-cyan); font-weight:700; cursor:pointer; text-decoration:underline;">⚡ Optimize Now</button></div>
            </div>
        </div>

        <!-- Manual Control & Studio Action Center -->
        <div class="toolbar">
            <div style="font-size:14px; font-weight:700; color:#fff;">
                🎛️ <b>प्रकल्प कमांड सेंटर व मॅन्युअल ऑपरेशन्स (Master Controls & Bot Offloader):</b>
            </div>
            <div style="display:flex; gap:10px; flex-wrap:wrap;">
                <button class="btn btn-gold" onclick="openAddModal()">➕ नवीन ई-बुक जोडा</button>
                <button class="btn btn-blue" onclick="openBulkUploadModal()" style="background:#2563eb; color:#fff;">📚 बल्क PDFs एकत्र अपलोड करा</button>
                <button class="btn btn-gold" onclick="dispatchQuizNow()" style="background:linear-gradient(135deg, #10b981, #059669); color:#fff; border:none;">🚀 चॅनेलवर थेट क्विझ पाठवा</button>
                <button class="btn btn-blue" onclick="optimizeSystemNow()" style="background:linear-gradient(135deg, #6366f1, #4f46e5); color:#fff; border:none;">⚡ बॉट मेमरी लोड कमी करा (Optimize)</button>
                <a href="/admin/export_qbank" class="btn btn-outline">📥 संपूर्ण प्रश्नसंच (Export QBank)</a>
                <button class="btn btn-outline" onclick="document.getElementById('pdfFileInput').click()">📁 थेट Single PDF</button>
                <input type="file" id="pdfFileInput" style="display:none;" accept=".pdf,.zip" onchange="uploadDirectPdf(this)">
                <input type="file" id="bulkModalFileInput" style="display:none;" accept=".pdf,.zip" multiple onchange="handleBulkFilesSelected(this.files)">
                <button class="btn btn-outline" onclick="syncFolderPdfs()">🔄 फोल्डर PDF सिंक</button>
                <button class="btn btn-danger" onclick="purgeAllProducts()">🧹 सर्व ई-बुक्स हटवा</button>
                <a href="/admin/download_all_products" class="btn btn-outline">📦 ZIP बॅकअप</a>
            </div>
        </div>

        <!-- Product Management Table -->
        <div class="section-box">
            <div class="section-header">
                <div class="section-title">
                    📦 डिजिटल ई-बुक्स व्यवस्थापन (Digital Products Catalog — {len(products)} Titles)
                </div>
                <div style="display:flex; align-items:center; gap:8px;">
                    <input type="text" placeholder="🔍 शीर्षक किंवा ID शोधा..." oninput="filterProductsTable(this.value)" style="padding:6px 12px; background:#1e293b; border:1px solid #334155; border-radius:6px; color:#fff; font-size:12px; width:210px; outline:none;">
                    <button class="btn btn-sm btn-gold" onclick="openAddModal()">➕ Add Product</button>
                    <button class="btn btn-sm btn-outline" onclick="location.reload()">🔄 रिफ्रेश</button>
                </div>
            </div>
            <div class="table-wrap">
                <table>
                    <thead>
                        <tr>
                            <th style="width:40px; text-align:center;">चिन्ह</th>
                            <th>ई-बुक शीर्षक व ID</th>
                            <th>विषय (Subject)</th>
                            <th style="width:140px;">किंमत (Price)</th>
                            <th style="width:140px; text-align:center;">PDF फाईल</th>
                            <th style="width:110px; text-align:center;">स्थिती</th>
                            <th style="width:180px; text-align:center;">नियंत्रण (Actions)</th>
                        </tr>
                    </thead>
                    <tbody>
                        {products_tbody_content}
                    </tbody>
                </table>
            </div>
        </div>

        <!-- Live Store Visitors Table -->
        <div class="section-box">
            <div class="section-header" style="flex-wrap:wrap; gap:10px;">
                <div class="section-title">
                    👥 थेट स्टोअर व्हिजिटर्स (Live Store Traffic — Recent 40 Visits)
                </div>
                <div style="display:flex; align-items:center; gap:8px;">
                    <span class="badge badge-blue" id="visitorScrollBadge">दाखवत आहे: १ ते ५ / {len(recent_visitors)}</span>
                    <button class="btn btn-sm btn-outline" onclick="scrollVisitors(-1)" title="मागील ५ व्हिजिटर्स पहा">⬆️ मागील ५</button>
                    <button class="btn btn-sm btn-outline" onclick="scrollVisitors(1)" title="पुढील ५ व्हिजिटर्स पहा">⬇️ पुढील ५</button>
                    <span style="font-size:12px; color:var(--text-muted); margin-left:6px;">रिअल-टाइम ट्रॅकिंग</span>
                </div>
            </div>
            <div class="table-wrap visitors-scroll-wrap" id="visitorsScrollBox" onscroll="updateVisitorScrollIndicator()">
                <table>
                    <thead>
                        <tr>
                            <th>आयपी (IP Address)</th>
                            <th>डिव्हाइस (Device)</th>
                            <th>कृती (Action)</th>
                            <th>भेट दिलेले पान (Path)</th>
                            <th>उत्पादन (Product ID)</th>
                            <th>वेळ (Timestamp)</th>
                        </tr>
                    </thead>
                    <tbody>
                        {"".join(visitor_rows_html) if visitor_rows_html else '<tr><td colspan="6" style="text-align:center; padding:20px; color:#64748b;">अद्याप कोणत्याही व्हिजिटरची नोंद नाही.</td></tr>'}
                    </tbody>
                </table>
            </div>
        </div>

        <!-- Recent Orders Table -->
        <div class="section-box">
            <div class="section-header" style="flex-wrap:wrap; gap:12px;">
                <div class="section-title">
                    🛒 थेट ऑर्डर्स व पेमेंट पडताळणी (Customer Orders & UTR Approvals)
                    <span class="badge badge-yellow" style="margin-left:8px;">{pending_count} प्रलंबित</span>
                </div>
                <div style="display:flex; align-items:center; gap:6px; flex-wrap:wrap;">
                    <input type="text" placeholder="🔍 Email किंवा Token शोधा..." oninput="filterOrdersTable(this.value)" style="padding:6px 12px; background:#1e293b; border:1px solid #334155; border-radius:6px; color:#fff; font-size:12px; width:200px; outline:none;">
                    <button class="filter-tab active" onclick="filterOrders('all', this)">सर्व ({len(recent_orders)})</button>
                    <button class="filter-tab" onclick="filterOrders('pending', this)">⏳ प्रलंबित ({pending_count})</button>
                    <button class="filter-tab" onclick="filterOrders('approved', this)">✅ मंजूर ({approved_count})</button>
                    <button class="filter-tab" onclick="filterOrders('rejected', this)">❌ नाकारले ({rejected_count})</button>
                </div>
            </div>
            <div class="table-wrap">
                <table>
                    <thead>
                        <tr>
                            <th>ऑर्डर टोकन</th>
                            <th>विद्यार्थी व ई-बुक</th>
                            <th>रक्कम</th>
                            <th>१२-अंकी UTR</th>
                            <th>स्थिती</th>
                            <th>दिनांक</th>
                            <th style="text-align:center; min-width:180px;">ॲक्शन (Actions)</th>
                        </tr>
                    </thead>
                    <tbody id="ordersTbody">
                        {"".join(order_rows_html) if order_rows_html else '<tr><td colspan="7" style="text-align:center; padding:20px; color:#64748b;">अद्याप कोणतीही ऑर्डर नोंदवलेली नाही.</td></tr>'}
                    </tbody>
                </table>
            </div>
        </div>

        <!-- Central Question Bank & Live Quiz Studio -->
        <div class="section-box">
            <div class="section-header" style="flex-wrap:wrap; gap:12px;">
                <div class="section-title">
                    🧠 केंद्रीय प्रश्नसंच व क्विझ व्यवस्थापन (Central Question Bank — {total_qbank_cnt} Questions)
                    <span class="badge badge-green" style="margin-left:8px;">Live Harvester</span>
                </div>
                <div style="display:flex; align-items:center; gap:8px; flex-wrap:wrap;">
                    <input type="text" placeholder="🔍 प्रश्न किंवा विषय शोधा..." oninput="filterQbankTable(this.value)" style="padding:6px 12px; background:#1e293b; border:1px solid #334155; border-radius:6px; color:#fff; font-size:12px; width:200px; outline:none;">
                    <button class="btn btn-sm btn-gold" onclick="dispatchQuizNow()">🚀 चॅनेलवर क्विझ पाठवा</button>
                    <a href="/admin/export_qbank" class="btn btn-sm btn-outline">📥 Export JSON</a>
                </div>
            </div>
            <div class="table-wrap">
                <table>
                    <thead>
                        <tr>
                            <th style="width:60px;">ID</th>
                            <th>विषय (Section)</th>
                            <th>परीक्षा (Exam)</th>
                            <th>प्रश्न मजकूर (Question Text)</th>
                            <th style="text-align:center; width:120px;">अधिकृत उत्तर</th>
                            <th style="width:110px;">स्रोत (Source)</th>
                        </tr>
                    </thead>
                    <tbody id="qbankTbody">
                        {"".join(qbank_rows_html) if qbank_rows_html else '<tr><td colspan="6" style="text-align:center; padding:20px; color:#64748b;">अद्याप प्रश्नसंचात कोणताही प्रश्न नोंदवलेला नाही. विद्यार्थी किंवा ॲडमिनने रिस्पॉन्स शीट अपलोड करताच येथे प्रश्न आपोआप साठवले जातील.</td></tr>'}
                    </tbody>
                </table>
            </div>
        </div>

        <!-- Live Candidate Submissions & Scores Table -->
        <div class="section-box">
            <div class="section-header" style="flex-wrap:wrap; gap:12px;">
                <div class="section-title">
                    📑 थेट परीक्षार्थी निकाल व अपलोड्स (Live Candidate Submissions — {total_uploads_cnt} Records)
                    <span class="badge badge-sub" style="margin-left:8px;">वेब व बॉट डेटा</span>
                </div>
                <div style="display:flex; align-items:center; gap:8px; flex-wrap:wrap;">
                    <select onchange="filterUploadsTable(this.value)" style="padding:6px 10px; background:#1e293b; border:1px solid #334155; border-radius:6px; color:#fff; font-size:12px; outline:none; cursor:pointer;">
                        <option value="">सर्व परीक्षा (All Exams)</option>
                        <option value="ZP_BHARTI">ZP Bharti (जिल्हा परिषद)</option>
                        <option value="MAHA_POLICE">Maha Police (महाराष्ट्र पोलीस)</option>
                        <option value="TALATHI">Talathi Bharti (तलाठी)</option>
                        <option value="AROGYA">Arogya Seva (आरोग्य सेवक)</option>
                        <option value="FOREST">Forest Guard (वनरक्षक)</option>
                        <option value="MPSC">MPSC Exams</option>
                    </select>
                    <input type="text" placeholder="🔍 नाव, रोल नं किंवा परीक्षा शोधा..." oninput="filterUploadsTable(this.value)" style="padding:6px 12px; background:#1e293b; border:1px solid #334155; border-radius:6px; color:#fff; font-size:12px; width:220px; outline:none;">
                    <button class="btn btn-sm btn-outline" onclick="location.reload()">🔄 रिफ्रेश</button>
                </div>
            </div>
            <div class="table-wrap">
                <table>
                    <thead>
                        <tr>
                            <th style="width:50px;">ID</th>
                            <th>परीक्षार्थी व रोल नंबर</th>
                            <th>परीक्षा</th>
                            <th>प्रवर्ग</th>
                            <th>गुण (Score)</th>
                            <th>रँक</th>
                            <th>प्रकार</th>
                            <th>वेळ</th>
                            <th style="text-align:center; width:90px;">ॲक्शन</th>
                        </tr>
                    </thead>
                    <tbody id="uploadsTbody">
                        {"".join(upload_rows_html) if upload_rows_html else '<tr><td colspan="9" style="text-align:center; padding:20px; color:#64748b;">अद्याप कोणत्याही परीक्षार्थ्याने रिस्पॉन्स शीट अपलोड केलेली नाही.</td></tr>'}
                    </tbody>
                </table>
            </div>
        </div>

    </main>

    <!-- Modal: Add New Product -->
    <div class="modal-overlay" id="bulkUploadModal">
        <div class="modal" style="max-width:680px;">
            <button class="modal-close" onclick="closeModal('bulkUploadModal')">&times;</button>
            <h2 style="color:#ffffff; font-size:18px; margin-bottom:8px;">📚 बल्क PDFs एकत्र अपलोड करा (Bulk Upload)</h2>
            <p style="font-size:12.5px; color:#94a3b8; margin-bottom:16px; line-height:1.5;">
                एकाच वेळी अनेक PDF ई-बुक्स निवडा किंवा ड्रॅग-अँड-ड्रॉप करा. सर्व फाईल्स थेट सर्व्हरवर अपलोड होऊन डिजिटल स्टोअरमध्ये आपोआप कॅटलॉग केल्या जातील.
            </p>

            <div class="dropzone-box" id="bulkDropZone" onclick="document.getElementById('bulkModalFileInput').click()">
                <div style="font-size:36px; margin-bottom:8px;">📥</div>
                <div style="font-size:14px; font-weight:700; color:#fff; margin-bottom:4px;">
                    येथे PDF / ZIP फाईल्स ड्रॅग करा किंवा कॉम्प्युटरमधून निवडण्यासाठी क्लिक करा
                </div>
                <div style="font-size:12px; color:#64748b;">
                    (एकाच वेळी अनेक PDFs किंवा १ ZIP फाईल निवडू शकता — ZIP मधील सर्व PDFs आपोआप अनपॅक होतात)
                </div>
            </div>

            <div class="bulk-progress-bar" id="bulkProgressBar">
                <div class="bulk-progress-fill" id="bulkProgressFill"></div>
            </div>
            <div id="bulkStatusText" style="font-size:12px; color:var(--accent-gold); margin-bottom:10px; display:none; font-weight:600;"></div>

            <div class="bulk-file-list" id="bulkFileList"></div>

            <div style="display:flex; justify-content:flex-end; gap:10px; margin-top:14px;">
                <button type="button" class="btn btn-outline" onclick="closeModal('bulkUploadModal')">रद्द करा (Cancel)</button>
                <button type="button" class="btn btn-blue" id="btnStartBulkUpload" onclick="startBulkUploadProcess()" style="background:#2563eb; color:#fff;" disabled>
                    🚀 सर्व फाईल्स अपलोड करा (Start Upload)
                </button>
            </div>
        </div>
    </div>

    <!-- Modal: Add New Product -->
    <div class="modal-overlay" id="addModal">
        <div class="modal">
            <button class="modal-close" onclick="closeModal('addModal')">&times;</button>
            <h2 style="color:#ffffff; font-size:18px; margin-bottom:14px;">➕ नवीन डिजिटल ई-बुक जोडा (Add Product)</h2>
            <form id="addForm" onsubmit="submitCreateProduct(event)">
                <div class="form-group">
                    <label class="form-label">ई-बुक शीर्षक (Title) *</label>
                    <input type="text" id="add_title" class="form-input" placeholder="उदा. TCS/IBPS चालू घडामोडी टॉप २०० प्रश्न" required>
                </div>
                <div class="form-group">
                    <label class="form-label">उपशीर्षक (Subtitle)</label>
                    <input type="text" id="add_subtitle" class="form-input" placeholder="उदा. सविस्तर विश्लेषण, शॉर्ट ट्रिक्स व रिव्हिजन चार्ट्स">
                </div>
                <div class="form-row">
                    <div class="form-group">
                        <label class="form-label">विषय / कॅटेगरी (Subject / Category) *</label>
                        <input type="text" id="add_subject" list="subject_list" class="form-input" placeholder="निवडा किंवा नवा विषय टाईप करा..." value="General Knowledge" required>
                        <datalist id="subject_list">
                            <option value="Current Affairs">
                            <option value="Marathi">
                            <option value="English">
                            <option value="General Knowledge">
                            <option value="Maths & Reasoning">
                            <option value="PYQ & Response Sheets">
                            <option value="Technical">
                            <option value="Comprehensive">
                            <option value="Maha Police Special">
                            <option value="Talathi Bharti Mock Series">
                            <option value="Arogya Sevak Test Series">
                            <option value="Formula Handbook">
                        </datalist>
                    </div>
                    <div class="form-group">
                        <label class="form-label">प्रॉडक्ट प्रकार (Product Type / Tier) *</label>
                        <input type="text" id="add_tier" list="tier_list" class="form-input" placeholder="उदा. PDF E-Book, Question Bank, Test Series" value="PDF E-Book" required>
                        <datalist id="tier_list">
                            <option value="PDF E-Book">
                            <option value="Question Bank">
                            <option value="Mock Test Series">
                            <option value="Formula Handbook">
                            <option value="Rapid Revision">
                            <option value="Handwritten Notes">
                            <option value="VIP Study Material">
                            <option value="Audio Revision">
                        </datalist>
                    </div>
                    <div class="form-group">
                        <label class="form-label">चिन्ह (Icon)</label>
                        <select id="add_icon" class="form-select">
                            <option value="📚">📚 पुस्तक (Books)</option>
                            <option value="📰">📰 वर्तमानपत्र (News)</option>
                            <option value="✍️">✍️ पेन (Writing)</option>
                            <option value="📖">📖 वाचन (Reading)</option>
                            <option value="🔢">🔢 गणित (Maths)</option>
                            <option value="⚡">⚡ वीज (Speed)</option>
                            <option value="🏆">🏆 ट्रॉफी (Topper)</option>
                            <option value="🎯">🎯 लक्ष्य (Target)</option>
                            <option value="💡">💡 दिवा (Idea)</option>
                        </select>
                    </div>
                </div>
                <div class="form-row">
                    <div class="form-group">
                        <label class="form-label">किंमत (Price INR) *</label>
                        <input type="number" id="add_price" class="form-input" value="19" min="10" max="100" required>
                    </div>
                    <div class="form-group">
                        <label class="form-label">मूळ किंमत (Original Price)</label>
                        <input type="number" id="add_orig_price" class="form-input" value="99" min="10" max="500">
                    </div>
                    <div class="form-group">
                        <label class="form-label">एकूण पृष्ठे (Pages)</label>
                        <input type="number" id="add_pages" class="form-input" value="48" min="1" max="1000">
                    </div>
                </div>
                <div class="form-row">
                    <div class="form-group">
                        <label class="form-label">बॅज (Badge Text)</label>
                        <input type="text" id="add_badge" class="form-input" value="🔥 BESTSELLER (₹19)">
                    </div>
                    <div class="form-group">
                        <label class="form-label">PDF फाईल नाव (Filename) *</label>
                        <input type="text" id="add_file" class="form-input" placeholder="उदा. my_new_book.pdf" required>
                    </div>
                </div>
                <div class="form-group">
                    <label class="form-label">सविस्तर माहिती (Description)</label>
                    <textarea id="add_desc" class="form-textarea" rows="3" placeholder="या ई-बुकची वैशिष्ट्ये व विद्यार्थ्यांना होणारे फायदे..."></textarea>
                </div>
                <button type="submit" class="btn btn-gold" style="width:100%; padding:12px; margin-top:8px;">💾 ई-बुक प्रकाशित करा (Publish Product)</button>
            </form>
        </div>
    </div>

    <!-- Modal: Edit Existing Product -->
    <div class="modal-overlay" id="editModal">
        <div class="modal">
            <button class="modal-close" onclick="closeModal('editModal')">&times;</button>
            <h2 style="color:#ffffff; font-size:18px; margin-bottom:14px;">✏️ ई-बुक संपादन (Edit Product)</h2>
            <form id="editForm" onsubmit="submitUpdateProduct(event)">
                <input type="hidden" id="edit_id">
                <div class="form-group">
                    <label class="form-label">ई-बुक शीर्षक (Title) *</label>
                    <input type="text" id="edit_title" class="form-input" required>
                </div>
                <div class="form-group">
                    <label class="form-label">उपशीर्षक (Subtitle)</label>
                    <input type="text" id="edit_subtitle" class="form-input">
                </div>
                <div class="form-row">
                    <div class="form-group">
                        <label class="form-label">विषय / कॅटेगरी (Subject / Category) *</label>
                        <input type="text" id="edit_subject" list="subject_list" class="form-input" required>
                    </div>
                    <div class="form-group">
                        <label class="form-label">प्रॉडक्ट प्रकार (Product Type / Tier) *</label>
                        <input type="text" id="edit_tier" list="tier_list" class="form-input" required>
                    </div>
                    <div class="form-group">
                        <label class="form-label">चिन्ह (Icon)</label>
                        <select id="edit_icon" class="form-select">
                            <option value="📚">📚 पुस्तक (Books)</option>
                            <option value="📰">📰 वर्तमानपत्र (News)</option>
                            <option value="✍️">✍️ पेन (Writing)</option>
                            <option value="📖">📖 वाचन (Reading)</option>
                            <option value="🔢">🔢 गणित (Maths)</option>
                            <option value="⚡">⚡ वीज (Speed)</option>
                            <option value="🏆">🏆 ट्रॉफी (Topper)</option>
                            <option value="🎯">🎯 लक्ष्य (Target)</option>
                            <option value="💡">💡 दिवा (Idea)</option>
                        </select>
                    </div>
                </div>
                <div class="form-row">
                    <div class="form-group">
                        <label class="form-label">किंमत (Price INR) *</label>
                        <input type="number" id="edit_price" class="form-input" min="10" max="100" required>
                    </div>
                    <div class="form-group">
                        <label class="form-label">मूळ किंमत (Original Price)</label>
                        <input type="number" id="edit_orig_price" class="form-input" min="10" max="500">
                    </div>
                    <div class="form-group">
                        <label class="form-label">एकूण पृष्ठे (Pages)</label>
                        <input type="number" id="edit_pages" class="form-input" min="1" max="1000">
                    </div>
                </div>
                <div class="form-row">
                    <div class="form-group">
                        <label class="form-label">बॅज (Badge Text)</label>
                        <input type="text" id="edit_badge" class="form-input">
                    </div>
                    <div class="form-group">
                        <label class="form-label">PDF फाईल नाव (Filename) *</label>
                        <input type="text" id="edit_file" class="form-input" required>
                    </div>
                </div>
                <div class="form-group">
                    <label class="form-label">सविस्तर माहिती (Description)</label>
                    <textarea id="edit_desc" class="form-textarea" rows="3"></textarea>
                </div>
                <button type="submit" class="btn btn-gold" style="width:100%; padding:12px; margin-top:8px;">💾 बदल जतन करा (Save Changes)</button>
            </form>
        </div>
    </div>

    <script>
        function getAdminKey() {{
            const urlParams = new URLSearchParams(window.location.search);
            const keyFromUrl = urlParams.get('key') || urlParams.get('token') || urlParams.get('admin_key');
            if (keyFromUrl) {{
                sessionStorage.setItem('admin_key', keyFromUrl);
                document.cookie = "admin_key=" + encodeURIComponent(keyFromUrl) + "; path=/; max-age=86400; SameSite=Lax";
                return keyFromUrl;
            }}
            let key = sessionStorage.getItem('admin_key');
            if (!key) {{
                const match = document.cookie.match(/(^|;)\\s*admin_key=([^;]+)/);
                if (match) {{
                    key = decodeURIComponent(match[2]);
                    sessionStorage.setItem('admin_key', key);
                }}
            }}
            return key || '';
        }}

        function handleLogout() {{
            if (confirm('तुम्हाला ॲडमिन पोर्टलवरून लॉगआउट करायचे आहे का?')) {{
                sessionStorage.removeItem('admin_key');
                document.cookie = "admin_key=; path=/; max-age=0; SameSite=Lax";
                window.location.href = '/admin';
            }}
        }}

        function showToast(message, type = 'info') {{
            let container = document.getElementById('toastContainer');
            if (!container) {{
                container = document.createElement('div');
                container.id = 'toastContainer';
                container.style.cssText = 'position:fixed; top:24px; right:24px; z-index:999999; display:flex; flex-direction:column; gap:12px; pointer-events:none;';
                document.body.appendChild(container);
            }}
            const toast = document.createElement('div');
            const bg = type === 'success' ? '#059669' : type === 'error' ? '#dc2626' : '#0284c7';
            toast.style.cssText = `background:${{bg}}; color:#ffffff; padding:14px 22px; border-radius:12px; font-weight:600; font-size:14px; box-shadow:0 12px 30px rgba(0,0,0,0.5); border:1px solid rgba(255,255,255,0.15); opacity:0; transform:translateY(-12px); transition:all 0.3s cubic-bezier(0.16, 1, 0.3, 1); pointer-events:auto; max-width:420px; line-height:1.45; word-break:break-word;`;
            toast.innerHTML = message;
            container.appendChild(toast);
            setTimeout(() => {{ toast.style.opacity = '1'; toast.style.transform = 'translateY(0)'; }}, 10);
            setTimeout(() => {{
                toast.style.opacity = '0';
                toast.style.transform = 'translateY(-12px)';
                setTimeout(() => toast.remove(), 350);
            }}, 4500);
        }}

        async function adminFetch(url, options = {{}}) {{
            const adminKey = getAdminKey();
            const headers = options.headers || {{}};
            if (adminKey) {{
                headers['X-Admin-Key'] = adminKey;
            }}
            options.headers = headers;
            let res;
            try {{
                res = await fetch(url, options);
            }} catch (netErr) {{
                showToast('❌ सर्व्हरशी संपर्क होऊ शकला नाही. इंटरनेट किंवा सर्व्हर चालू आहे का ते तपासा.', 'error');
                throw netErr;
            }}
            if (res.status === 403) {{
                const promptKey = prompt('🔑 कृपया अधिकृत ॲडमिन API Key प्रविष्ट करा (Enter Admin Key):');
                if (promptKey) {{
                    sessionStorage.setItem('admin_key', promptKey.trim());
                    headers['X-Admin-Key'] = promptKey.trim();
                    options.headers = headers;
                    try {{
                        res = await fetch(url, options);
                    }} catch (retryErr) {{
                        showToast('❌ सर्व्हरशी संपर्क होऊ शकला नाही: ' + retryErr.message, 'error');
                        throw retryErr;
                    }}
                }}
            }}
            return res;
        }}

        function filterProductsTable(query) {{
            const q = (query || '').toLowerCase().trim();
            const rows = document.querySelectorAll('tbody tr[id^="row_"]');
            rows.forEach(row => {{
                const text = row.innerText.toLowerCase();
                row.style.display = (!q || text.includes(q)) ? '' : 'none';
            }});
        }}

        function filterOrdersTable(query) {{
            const q = (query || '').toLowerCase().trim();
            const rows = document.querySelectorAll('#ordersTbody tr');
            rows.forEach(row => {{
                const text = row.innerText.toLowerCase();
                row.style.display = (!q || text.includes(q)) ? '' : 'none';
            }});
        }}

        function openAddModal() {{
            document.getElementById('addModal').style.display = 'flex';
        }}

        function openEditModal(prod) {{
            document.getElementById('edit_id').value = prod.id || '';
            document.getElementById('edit_title').value = prod.title || '';
            document.getElementById('edit_subtitle').value = prod.subtitle || '';
            document.getElementById('edit_subject').value = prod.subject || 'General Knowledge';
            document.getElementById('edit_tier').value = prod.tier || 'PDF E-Book';
            document.getElementById('edit_icon').value = prod.icon || '📚';
            document.getElementById('edit_price').value = prod.price_inr || 19;
            document.getElementById('edit_orig_price').value = prod.original_price_inr || 99;
            document.getElementById('edit_pages').value = prod.pages || 48;
            document.getElementById('edit_badge').value = prod.badge || '';
            document.getElementById('edit_file').value = prod.download_file || '';
            document.getElementById('edit_desc').value = prod.description || '';
            document.getElementById('editModal').style.display = 'flex';
        }}

        function closeModal(modalId) {{
            document.getElementById(modalId).style.display = 'none';
        }}

        // Smooth scroll for Live Store Visitors (5 rows at a time)
        function scrollVisitors(direction) {{
            const box = document.getElementById('visitorsScrollBox');
            if (!box) return;
            const rowHeight = 44; // approximate height per row in pixels
            const scrollDistance = rowHeight * 5 * direction;
            box.scrollBy({{ top: scrollDistance, behavior: 'smooth' }});
            setTimeout(updateVisitorScrollIndicator, 300);
        }}

        function updateVisitorScrollIndicator() {{
            const box = document.getElementById('visitorsScrollBox');
            const badge = document.getElementById('visitorScrollBadge');
            if (!box || !badge) return;
            const rows = box.querySelectorAll('tbody tr');
            const total = rows.length;
            if (total === 0 || (total === 1 && rows[0].innerText.includes('अद्याप कोणत्याही'))) {{
                badge.innerText = '० व्हिजिटर्स';
                return;
            }}
            const rowHeight = 44;
            const currentTop = box.scrollTop;
            const startIdx = Math.min(total, Math.floor(currentTop / rowHeight) + 1);
            const endIdx = Math.min(total, startIdx + 4);
            badge.innerText = `दाखवत आहे: ${{startIdx}} ते ${{endIdx}} / ${{total}}`;
        }}

        // Bulk PDF Upload logic
        let selectedBulkFiles = [];

        function openBulkUploadModal() {{
            selectedBulkFiles = [];
            document.getElementById('bulkFileList').innerHTML = '';
            document.getElementById('bulkFileList').style.display = 'none';
            document.getElementById('bulkProgressBar').style.display = 'none';
            document.getElementById('bulkProgressFill').style.width = '0%';
            document.getElementById('bulkStatusText').style.display = 'none';
            document.getElementById('btnStartBulkUpload').disabled = true;
            document.getElementById('bulkUploadModal').style.display = 'flex';
            setupBulkDropZone();
        }}

        function setupBulkDropZone() {{
            const dropZone = document.getElementById('bulkDropZone');
            if (!dropZone || dropZone.dataset.initialized) return;
            dropZone.dataset.initialized = 'true';

            ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {{
                dropZone.addEventListener(eventName, e => {{ e.preventDefault(); e.stopPropagation(); }}, false);
            }});
            ['dragenter', 'dragover'].forEach(eventName => {{
                dropZone.addEventListener(eventName, () => dropZone.classList.add('drag-over'), false);
            }});
            ['dragleave', 'drop'].forEach(eventName => {{
                dropZone.addEventListener(eventName, () => dropZone.classList.remove('drag-over'), false);
            }});
            dropZone.addEventListener('drop', e => {{
                const dt = e.dataTransfer;
                if (dt && dt.files && dt.files.length > 0) {{
                    handleBulkFilesSelected(dt.files);
                }}
            }});
        }}

        function handleBulkFilesSelected(files) {{
            if (!files || files.length === 0) return;
            for (let i = 0; i < files.length; i++) {{
                const f = files[i];
                if (f.name.toLowerCase().endsWith('.pdf')) {{
                    if (!selectedBulkFiles.some(item => item.name === f.name && item.size === f.size)) {{
                        selectedBulkFiles.push(f);
                    }}
                }}
            }}
            renderBulkFileList();
        }}

        function renderBulkFileList() {{
            const listEl = document.getElementById('bulkFileList');
            const btn = document.getElementById('btnStartBulkUpload');
            if (selectedBulkFiles.length === 0) {{
                listEl.style.display = 'none';
                btn.disabled = true;
                return;
            }}
            listEl.style.display = 'block';
            btn.disabled = false;
            let html = '';
            selectedBulkFiles.forEach((f, idx) => {{
                const mb = (f.size / (1024 * 1024)).toFixed(2);
                html += `<div class="bulk-file-item" id="bulk-item-${{idx}}">
                    <span style="font-weight:600; color:#e2e8f0;">📄 ${{f.name}}</span>
                    <span style="display:flex; align-items:center; gap:8px;">
                        <span style="color:#94a3b8; font-size:11px;">${{mb}} MB</span>
                        <span id="bulk-status-${{idx}}" class="badge badge-gray">तयार</span>
                        <button type="button" onclick="removeBulkFile(${{idx}})" style="background:none; border:none; color:#f87171; cursor:pointer; font-size:14px;">✕</button>
                    </span>
                </div>`;
            }});
            listEl.innerHTML = html;
        }}

        function removeBulkFile(index) {{
            selectedBulkFiles.splice(index, 1);
            renderBulkFileList();
        }}

        function readFileAsBase64(file) {{
            return new Promise((resolve, reject) => {{
                const reader = new FileReader();
                reader.onload = () => {{
                    const b64 = reader.result.split(',')[1];
                    resolve(b64);
                }};
                reader.onerror = err => reject(err);
                reader.readAsDataURL(file);
            }});
        }}

        async function startBulkUploadProcess() {{
            if (selectedBulkFiles.length === 0) return;
            const btn = document.getElementById('btnStartBulkUpload');
            const pBar = document.getElementById('bulkProgressBar');
            const pFill = document.getElementById('bulkProgressFill');
            const sText = document.getElementById('bulkStatusText');

            btn.disabled = true;
            pBar.style.display = 'block';
            sText.style.display = 'block';

            let successCount = 0;
            let failCount = 0;
            const total = selectedBulkFiles.length;

            for (let i = 0; i < total; i++) {{
                const f = selectedBulkFiles[i];
                const statusBadge = document.getElementById(`bulk-status-${{i}}`);
                if (statusBadge) {{
                    statusBadge.className = 'badge badge-yellow';
                    statusBadge.innerText = 'अपलोड होत आहे...';
                }}
                sText.innerText = `⏳ फाईल ${{i + 1}} / ${{total}} अपलोड होत आहे: ${{f.name}}...`;

                try {{
                    const data = await uploadFileInChunks(f, (done, totalCh, pct) => {{
                        sText.innerText = `⏳ फाईल ${{i + 1}} / ${{total}} अपलोड होत आहे: ${{f.name}} (${{pct}}%)...`;
                    }});
                    if (data && data.success) {{
                        successCount++;
                        if (statusBadge) {{
                            statusBadge.className = 'badge badge-green';
                            statusBadge.innerText = '✅ यशस्वी';
                        }}
                    }} else {{
                        failCount++;
                        if (statusBadge) {{
                            statusBadge.className = 'badge badge-red';
                            statusBadge.style.color = '#f87171';
                            statusBadge.innerText = '❌ त्रुटी: ' + (data && data.message ? data.message : 'त्रुटी');
                        }}
                    }}
                }} catch (err) {{
                    failCount++;
                    if (statusBadge) {{
                        statusBadge.className = 'badge badge-red';
                        statusBadge.style.color = '#f87171';
                        statusBadge.innerText = '❌ त्रुटी';
                    }}
                }}
                const progressPct = Math.round(((i + 1) / total) * 100);
                pFill.style.width = progressPct + '%';
            }}

            sText.innerText = `🔄 डिजिटल स्टोअर कॅटलॉग सिंक होत आहे...`;
            try {{
                await adminFetch('/api/admin/sync_products', {{ method: 'POST' }});
            }} catch(e) {{}}

            sText.innerText = `🎉 बल्क अपलोड पूर्ण! यशस्वी: ${{successCount}}, अयशस्वी: ${{failCount}}`;
            showToast(`✅ बल्क अपलोड पूर्ण: ${{successCount}} फाईल्स स्टोअरमध्ये जोडल्या गेल्या!`, 'success');
            setTimeout(() => {{
                location.reload();
            }}, 1500);
        }}

        // Resilient Chunked Admin PDF Upload (Bypasses proxy limits, zero memory leaks)
        async function uploadFileInChunks(file, onProgress) {{
            const CHUNK_SIZE = 1.5 * 1024 * 1024;
            const totalChunks = Math.ceil(file.size / CHUNK_SIZE);
            const uploadId = 'adm_' + Date.now() + '_' + Math.random().toString(36).substring(2, 9);

            for (let i = 0; i < totalChunks; i++) {{
                const start = i * CHUNK_SIZE;
                const end = Math.min(file.size, start + CHUNK_SIZE);
                const chunkBlob = file.slice(start, end);
                const chunkB64 = await readFileAsBase64(chunkBlob);

                let res;
                let retries = 3;
                while (retries > 0) {{
                    try {{
                        res = await adminFetch('/api/admin/upload_chunk', {{
                            method: 'POST',
                            headers: {{ 'Content-Type': 'application/json' }},
                            body: JSON.stringify({{
                                upload_id: uploadId,
                                chunk_index: i,
                                total_chunks: totalChunks,
                                filename: file.name,
                                data: chunkB64
                            }})
                        }});
                        if (res.ok) break;
                    }} catch (fetchErr) {{
                        console.warn('Chunk upload retry:', fetchErr);
                    }}
                    retries--;
                    if (retries === 0 && (!res || !res.ok)) {{
                        let errText = 'तुकडा ' + (i+1) + '/' + totalChunks + ' अपलोड अयशस्वी (Status: ' + (res ? res.status : 'Network Error') + ')';
                        try {{
                            const errJson = await res.json();
                            if (errJson.error || errJson.message) errText = errJson.error || errJson.message;
                        }} catch(e) {{}}
                        throw new Error(errText);
                    }}
                    await new Promise(r => setTimeout(r, 250));
                }}

                const data = await res.json();
                if (onProgress) {{
                    onProgress(i + 1, totalChunks, Math.round(((i + 1) / totalChunks) * 100));
                }}

                if (i === totalChunks - 1) {{
                    return data;
                }}
            }}
        }}

        // Direct PDF file upload with size validation & chunked progress
        async function uploadDirectPdf(input) {{
            if (!input.files || input.files.length === 0) return;
            const file = input.files[0];
            if (!file.name.toLowerCase().endsWith('.pdf') && !file.name.toLowerCase().endsWith('.zip')) {{
                showToast('⚠️ कृपया फक्त वैध .pdf किंवा .zip फाईल निवडा.', 'error');
                input.value = '';
                return;
            }}
            if (file.size > 524288000) {{
                showToast('⚠️ फाईल खूप मोठी आहे (' + (file.size / (1024*1024)).toFixed(1) + ' MB). कमाल मर्यादा ५०० MB आहे.', 'error');
                input.value = '';
                return;
            }}

            const fileSizeMb = (file.size / (1024 * 1024)).toFixed(2);
            showToast(`⏳ PDF अपलोड सुरू आहे (${{file.name}}, ${{fileSizeMb}} MB)... कृपया थांबा.`, 'info');

            try {{
                const data = await uploadFileInChunks(file, (done, total, pct) => {{
                    showToast(`⏳ PDF अपलोड सुरू आहे (${{file.name}}): ${{pct}}% (तुकडा ${{done}}/${{total}})...`, 'info');
                }});
                if (data && data.success) {{
                    showToast('✅ PDF फाईल यशस्वीरित्या अपलोड झाली: ' + data.filename, 'success');
                    document.getElementById('add_file').value = data.filename;
                    document.getElementById('add_title').value = file.name.replace(/\\.pdf$/i, '').replace(/_/g, ' ');
                    if (data.pages) {{
                        document.getElementById('add_pages').value = data.pages;
                    }}
                    openAddModal();
                }} else {{
                    showToast('❌ अपलोड त्रुटी: ' + (data && data.message ? data.message : 'Unknown error'), 'error');
                }}
            }} catch(err) {{
                showToast('❌ सर्व्हरशी संपर्क होऊ शकला नाही: ' + (err.message || 'Network error'), 'error');
            }} finally {{
                input.value = '';
            }}
        }}

        // Submit New Product
        async function submitCreateProduct(event) {{
            event.preventDefault();
            const payload = {{
                title: document.getElementById('add_title').value.trim(),
                subtitle: document.getElementById('add_subtitle').value.trim(),
                subject: (document.getElementById('add_subject').value || 'General Knowledge').trim(),
                tier: (document.getElementById('add_tier').value || 'PDF E-Book').trim(),
                icon: document.getElementById('add_icon').value,
                price_inr: parseInt(document.getElementById('add_price').value),
                original_price_inr: parseInt(document.getElementById('add_orig_price').value),
                pages: parseInt(document.getElementById('add_pages').value),
                badge: document.getElementById('add_badge').value.trim(),
                download_file: document.getElementById('add_file').value.trim(),
                description: document.getElementById('add_desc').value.trim(),
                is_active: 1
            }};

            try {{
                const res = await adminFetch('/api/admin/create_product', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify(payload)
                }});
                const data = await res.json();
                if (data.success) {{
                    alert('🎉 नवीन ई-बुक यशस्वीरित्या स्टोअरमध्ये जोडले गेले!');
                    location.reload();
                }} else {{
                    alert('❌ त्रुटी: ' + data.message);
                }}
            }} catch(e) {{
                alert('❌ सर्व्हर त्रुटी: ' + e.message);
            }}
        }}

        // Submit Update Product
        async function submitUpdateProduct(event) {{
            event.preventDefault();
            const prodId = document.getElementById('edit_id').value;
            const payload = {{
                product_id: prodId,
                title: document.getElementById('edit_title').value.trim(),
                subtitle: document.getElementById('edit_subtitle').value.trim(),
                subject: (document.getElementById('edit_subject').value || 'General Knowledge').trim(),
                tier: (document.getElementById('edit_tier').value || 'PDF E-Book').trim(),
                icon: document.getElementById('edit_icon').value,
                price_inr: parseInt(document.getElementById('edit_price').value),
                original_price_inr: parseInt(document.getElementById('edit_orig_price').value),
                pages: parseInt(document.getElementById('edit_pages').value),
                badge: document.getElementById('edit_badge').value.trim(),
                download_file: document.getElementById('edit_file').value.trim(),
                description: document.getElementById('edit_desc').value.trim()
            }};

            try {{
                const res = await adminFetch('/api/admin/update_product', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify(payload)
                }});
                const data = await res.json();
                if (data.success) {{
                    alert('✅ बदल यशस्वीरित्या जतन झाले!');
                    location.reload();
                }} else {{
                    alert('❌ त्रुटी: ' + data.message);
                }}
            }} catch(e) {{
                alert('❌ सर्व्हर त्रुटी: ' + e.message);
            }}
        }}

        // Toggle Product Active / Hidden
        async function toggleProductStatus(prodId) {{
            try {{
                const res = await adminFetch('/api/admin/toggle_product_status', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{ product_id: prodId }})
                }});
                const data = await res.json();
                if (data.success) {{
                    location.reload();
                }} else {{
                    alert('❌ त्रुटी: ' + data.message);
                }}
            }} catch(e) {{
                alert('❌ सर्व्हर त्रुटी: ' + e.message);
            }}
        }}

        // Delete Product
        async function deleteProduct(prodId) {{
            if (!confirm('⚠️ हे ई-बुक स्टोअरमधून कायमचे हटवायचे का?')) return;
            try {{
                const res = await adminFetch('/api/admin/delete_product', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{ product_id: prodId }})
                }});
                const data = await res.json();
                if (data.success) {{
                    const el = document.getElementById('row_' + prodId);
                    if (el) el.remove();
                    alert('🗑️ उत्पादन कायमचे हटवले गेले.');
                    location.reload();
                }} else {{
                    alert('❌ त्रुटी: ' + data.message);
                }}
            }} catch(e) {{
                alert('❌ सर्व्हर त्रुटी: ' + e.message);
            }}
        }}

        // Purge All Products
        async function purgeAllProducts() {{
            if (!confirm('🚨 सावधान! सर्व जुनी किंवा ऑटो-जनरेटेड ई-बुक्स स्टोअरमधून कायमची हटवायची का?\\n\\nयाने स्टोअर पूर्णपणे रिकामे होईल आणि तुम्ही स्वतः नवीन पुस्तके जोडू शकाल.')) return;
            try {{
                const res = await adminFetch('/api/admin/purge_products', {{ method: 'POST' }});
                const data = await res.json();
                if (data.success) {{
                    alert('🧹 सर्व उत्पादने हटवली गेली! आता तुमचे स्टोअर पूर्णपणे मॅन्युअल नियंत्रणात आहे.');
                    location.reload();
                }} else {{
                    alert('❌ त्रुटी: ' + data.message);
                }}
            }} catch(e) {{
                alert('❌ सर्व्हर त्रुटी: ' + e.message);
            }}
        }}

        // Filter Orders by Tab
        function filterOrders(filter, btn) {{
            document.querySelectorAll('.filter-tab').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            document.querySelectorAll('.order-row').forEach(row => {{
                const status = row.getAttribute('data-status');
                if (filter === 'all') {{
                    row.style.display = '';
                }} else if (filter === 'pending') {{
                    row.style.display = (status === 'pending' || status === 'pending_verification' || status === 'created') ? '' : 'none';
                }} else if (filter === 'approved') {{
                    row.style.display = (status === 'approved' || status === 'delivered' || status === 'paid') ? '' : 'none';
                }} else if (filter === 'rejected') {{
                    row.style.display = (status === 'rejected') ? '' : 'none';
                }}
            }});
        }}

        // Order Action (Approve Payment & Enable Instant Download / Reject)
        async function orderAction(orderToken, action) {{
            let actPrompt = 'या ऑर्डरचे पेमेंट मंजूर करून विद्यार्थ्याचे डाऊनलोड बटण (Download PDF) तात्काळ सक्रिय करायचे का?';
            if (action === 'reject') actPrompt = 'ही ऑर्डर नाकारायची (Reject) का?';
            if (!confirm(actPrompt)) return;
            try {{
                const res = await adminFetch('/api/admin/order_action', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{ order_token: orderToken, action: action }})
                }});
                const data = await res.json();
                if (data.success) {{
                    alert('✅ ' + (data.message || 'कृती यशस्वी! डाऊनलोड बटण सुरू केले आहे.'));
                    location.reload();
                }} else {{
                    alert('❌ त्रुटी: ' + data.message);
                }}
            }} catch(e) {{
                alert('❌ सर्व्हर त्रुटी: ' + e.message);
            }}
        }}

        // Fast price update
        async function updateProductPrice(prodId) {{
            const input = document.getElementById('price_' + prodId);
            const newPrice = parseInt(input.value);
            if (!newPrice || newPrice < 5 || newPrice > 500) {{
                alert('कृपया वैध किंमत टाका (₹१० ते ₹१००)');
                return;
            }}
            try {{
                const res = await adminFetch('/api/admin/update_price', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{ product_id: prodId, price_inr: newPrice }})
                }});
                const data = await res.json();
                if (data.success) {{
                    alert('✅ किंमत अद्ययावत केली: ₹' + newPrice);
                }} else {{
                    alert('❌ त्रुटी: ' + data.message);
                }}
            }} catch(e) {{
                alert('❌ सर्व्हरशी संपर्क होऊ शकला नाही.');
            }}
        }}

        async function syncFolderPdfs() {{
            try {{
                const res = await adminFetch('/api/admin/sync_products', {{ method: 'POST' }});
                const data = await res.json();
                alert('✅ फोल्डर सिंक यशस्वी! ' + (data.added || 0) + ' नवीन PDF ई-बुक्स स्टोअरमध्ये जोडली गेली.');
                location.reload();
            }} catch(e) {{
                alert('❌ सिंक अयशस्वी: ' + e.message);
            }}
        }}

        async function generateQBank() {{
            if (!confirm('नवीन ४-स्तंभ विषयवार प्रश्नसंच (Question Bank) तयार करायचा का?')) return;
            try {{
                const res = await adminFetch('/api/admin/generate_qbank', {{ method: 'POST' }});
                const data = await res.json();
                if (data.success) {{
                    alert('🎉 प्रश्नसंच तयार झाला व स्टोअरमध्ये जोडला गेला!');
                    location.reload();
                }} else {{
                    alert('❌ त्रुटी: ' + (data.message || 'त्रुटी आली'));
                }}
            }} catch(e) {{
                alert('❌ सर्व्हर त्रुटी: ' + e.message);
            }}
        }}

        async function generateChaluGhadamodi() {{
            if (!confirm('चालू घडामोडी मासिक संच PDF तयार करायची का?')) return;
            try {{
                const res = await adminFetch('/api/admin/generate_chalu_ghadamodi', {{ method: 'POST' }});
                const data = await res.json();
                if (data.success) {{
                    alert('🎉 चालू घडामोडी PDF तयार झाली व स्टोअरमध्ये जोडली गेली!');
                    location.reload();
                }} else {{
                    alert('❌ त्रुटी: ' + (data.message || 'त्रुटी आली'));
                }}
            }} catch(e) {{
                alert('❌ सर्व्हर त्रुटी: ' + e.message);
            }}
        }}

        async function dispatchQuizNow() {{
            const defaultCh = "-1004381339759";
            const targetChannel = prompt("📢 क्विझ पाठवण्यासाठी टेलिग्राम चॅनेल ID किंवा Username प्रविष्ट करा:", defaultCh);
            if (!targetChannel) return;

            showToast("⏳ चॅनेलवर सराव क्विझ पाठवत आहे...", "info");
            try {{
                const res = await adminFetch('/api/admin/dispatch_quiz', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{ channel: targetChannel.trim() }})
                }});
                const data = await res.json();
                if (data.success) {{
                    showToast('🚀 ' + (data.message || 'क्विझ चॅनेलवर पाठवला!'), 'success');
                    alert('🚀 ' + (data.message || 'क्विझ चॅनेलवर पाठवला!'));
                }} else {{
                    showToast('❌ त्रुटी: ' + data.message, 'error');
                    alert('❌ त्रुटी: ' + data.message);
                }}
            }} catch(e) {{
                showToast('❌ सर्व्हर त्रुटी: ' + e.message, 'error');
                alert('❌ सर्व्हर त्रुटी: ' + e.message);
            }}
        }}

        async function optimizeSystemNow() {{
            if (!confirm('⚡ बॉट मेमरी लोड कमी करण्यासाठी आणि डेटाबेस ऑप्टिमाईझ करण्यासाठी VACUUM चालवायचा का?')) return;
            try {{
                const res = await adminFetch('/api/admin/optimize_system', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{}})
                }});
                const data = await res.json();
                if (data.success) {{
                    alert('⚡ ' + (data.message || 'सिस्टीम ऑप्टिमायझेशन यशस्वी!'));
                    location.reload();
                }} else {{
                    alert('❌ त्रुटी: ' + data.message);
                }}
            }} catch(e) {{
                alert('❌ सर्व्हर त्रुटी: ' + e.message);
            }}
        }}

        async function deleteUploadRecord(uploadId) {{
            if (!confirm('हा निकाल / अपलोड कायमचा हटवायचा का?')) return;
            try {{
                const res = await adminFetch('/api/admin/delete_upload', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{ upload_id: uploadId }})
                }});
                const data = await res.json();
                if (data.success) {{
                    const row = document.getElementById('upload_row_' + uploadId);
                    if (row) row.remove();
                    alert('✅ अपलोड हटवले गेले.');
                }} else {{
                    alert('❌ त्रुटी: ' + data.message);
                }}
            }} catch(e) {{
                alert('❌ सर्व्हर त्रुटी: ' + e.message);
            }}
        }}

        function filterUploadsTable(query) {{
            const q = (query || '').toLowerCase().trim();
            const rows = document.querySelectorAll('#uploadsTbody tr');
            rows.forEach(row => {{
                const text = row.innerText.toLowerCase();
                row.style.display = (!q || text.includes(q)) ? '' : 'none';
            }});
        }}

        function filterQbankTable(query) {{
            const q = (query || '').toLowerCase().trim();
            const rows = document.querySelectorAll('#qbankTbody tr');
            rows.forEach(row => {{
                const text = row.innerText.toLowerCase();
                row.style.display = (!q || text.includes(q)) ? '' : 'none';
            }});
        }}
    </script>
</body>
</html>
"""
    return html

def render_admin_login_html(error_msg: str = "") -> str:
    err_html = f'<div style="background:rgba(239,68,68,0.15); border:1px solid #ef4444; border-radius:8px; padding:10px; color:#fca5a5; font-size:12.5px; margin-bottom:16px;">❌ {html.escape(error_msg)}</div>' if error_msg else ''
    return f"""<!DOCTYPE html>
<html lang="mr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ExamRankers™ Admin Studio — Login</title>
    <style>
        :root {{ --primary: #0284c7; --bg: #090d16; --card: #111827; --text: #f8fafc; }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: var(--bg); color: var(--text); min-height: 100vh; display: flex; align-items: center; justify-content: center; padding: 20px; }}
        .login-box {{ background: var(--card); border: 1px solid rgba(255,255,255,0.1); border-radius: 16px; padding: 32px 28px; width: 100%; max-width: 440px; box-shadow: 0 20px 25px -5px rgba(0,0,0,0.5); text-align: center; }}
        .logo-icon {{ font-size: 42px; margin-bottom: 12px; }}
        h1 {{ font-size: 21px; font-weight: 800; color: #fff; margin-bottom: 6px; }}
        p {{ font-size: 13px; color: #94a3b8; line-height: 1.5; margin-bottom: 20px; }}
        .input-group {{ text-align: left; margin-bottom: 20px; }}
        label {{ display: block; font-size: 12px; font-weight: 700; color: #cbd5e1; margin-bottom: 8px; text-transform: uppercase; letter-spacing: 0.5px; }}
        input[type="password"] {{ width: 100%; padding: 14px; background: #1e293b; border: 1px solid #334155; border-radius: 10px; color: #fff; font-size: 14px; outline: none; transition: 0.2s; }}
        input:focus {{ border-color: var(--primary); box-shadow: 0 0 0 3px rgba(2,132,199,0.25); }}
        .btn {{ width: 100%; padding: 14px; background: var(--primary); color: #fff; font-weight: 700; font-size: 15px; border-radius: 10px; border: none; cursor: pointer; transition: 0.2s; }}
        .btn:hover {{ background: #0369a1; }}
        .back-link {{ margin-top: 18px; display: block; color: #64748b; font-size: 13px; text-decoration: none; }}
        .back-link:hover {{ color: #94a3b8; }}
        .hint {{ font-size: 11.5px; color: #64748b; margin-top: 6px; }}
    </style>
</head>
<body>
    <div class="login-box">
        <div class="logo-icon">🔐</div>
        <h1>ExamRankers™ Admin Studio</h1>
        <p>सुरक्षित ॲडमिन पोर्टलमध्ये प्रवेश करण्यासाठी तुमची अधिकृत <b>Admin API Key</b> प्रविष्ट करा:</p>

        {err_html}

        <form onsubmit="handleLogin(event)">
            <div class="input-group">
                <label>Admin Secret Key</label>
                <input type="password" id="keyInput" placeholder="उदा. admin_prod_examrankers_sec_..." required autofocus />
                <div class="hint">💡 ही की तुमच्या सर्व्हरच्या .env फाईलमध्ये ADMIN_API_KEY म्हणून सेव्ह आहे.</div>
            </div>
            <button type="submit" class="btn">🚀 ॲडमिन पोर्टल उघडा (Login)</button>
        </form>

        <a href="/" class="back-link">← मुख्य ई-बुक स्टोअरवर परत जा</a>
    </div>

    <script>
        // Clear rejected invalid key if server rendered login page with a key parameter
        if (window.location.search.includes('key=') || window.location.search.includes('token=') || window.location.search.includes('admin_key=')) {{
            sessionStorage.removeItem('admin_key');
            document.cookie = "admin_key=; path=/; max-age=0; SameSite=Lax";
        }}

        // Check if a valid key is stored in sessionStorage
        const savedKey = sessionStorage.getItem('admin_key');
        if (savedKey && !window.location.search.includes('key=')) {{
            window.location.href = '/admin?key=' + encodeURIComponent(savedKey);
        }}

        function handleLogin(e) {{
            e.preventDefault();
            const val = document.getElementById('keyInput').value.trim();
            if (!val) return;
            sessionStorage.setItem('admin_key', val);
            document.cookie = "admin_key=" + encodeURIComponent(val) + "; path=/; max-age=86400; SameSite=Lax";
            window.location.href = '/admin?key=' + encodeURIComponent(val);
        }}
    </script>
</body>
</html>"""
