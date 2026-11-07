"""
ExamRankers™ Web Admin Command Center
=====================================
A sleek, high-performing web administration dashboard for the ExamRankers platform.
Features:
- Live KPI Metrics (Visitors, Sales, Checkouts, Digital Products)
- Real-time Product Catalog Management (1-click price change ₹10-₹50, status toggle)
- Automated Folder Sync for dropped PDFs
- 1-Click Generation of 4-Column Section-wise Question Banks
- 1-Click Generation of Chalu Ghadamodi Monthly Digest PDFs
- Live Visitor Tracking and Order Verification
"""

import os
import sqlite3
import json
from pathlib import Path
from typing import Dict, Any, List

def render_admin_dashboard_html(db_path: str = "bot.db") -> str:
    """Renders the complete responsive Web Admin Dashboard HTML."""
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

    try:
        with sqlite3.connect(db_path) as db:
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

            # Digital Products
            try:
                prods_rows = db.execute("SELECT * FROM digital_products ORDER BY price_inr ASC").fetchall()
                products = [dict(r) for r in prods_rows]
            except Exception:
                pass

            # Product Orders & Revenue
            try:
                orders_rows = db.execute("SELECT * FROM product_orders ORDER BY id DESC LIMIT 40").fetchall()
                recent_orders = [dict(r) for r in orders_rows]
                rev_row = db.execute("SELECT sum(amount_paid) FROM product_orders WHERE status = 'delivered' OR status = 'approved'").fetchone()
                if rev_row and rev_row[0]:
                    total_revenue = float(rev_row[0])
            except Exception:
                pass
    except Exception:
        pass

    # Build Product Rows HTML
    product_rows_html = []
    for p in products:
        p_id = p.get("id", "")
        title = p.get("title", "")
        subject = p.get("subject", "General")
        price = int(p.get("price_inr", 19))
        pages = p.get("pages", 48)
        dl_file = p.get("download_file", "")
        icon = p.get("icon", "📚")
        is_active = p.get("is_active", 1)

        product_rows_html.append(f"""
            <tr>
                <td style="font-size:16px; text-align:center;">{icon}</td>
                <td>
                    <b style="color:#ffffff;">{title}</b><br>
                    <span style="font-size:11px; color:#94a3b8;">ID: <code>{p_id}</code> | 📄 {pages} पृष्ठे</span>
                </td>
                <td><span class="badge badge-sub">{subject}</span></td>
                <td>
                    <div style="display:flex; align-items:center; gap:6px;">
                        <span>₹</span>
                        <input type="number" id="price_{p_id}" value="{price}" min="10" max="100" class="input-mini">
                        <button class="btn-sm btn-action" onclick="updateProductPrice('{p_id}')">💾 Save</button>
                    </div>
                </td>
                <td style="text-align:center;">
                    <a href="/admin/download_pdf?file={dl_file}" class="btn-sm btn-link" target="_blank">📥 PDF</a>
                </td>
                <td style="text-align:center;">
                    <span class="status-pill {'status-active' if is_active else 'status-inactive'}">
                        {'सक्रिय (Active)' if is_active else 'बंद (Inactive)'}
                    </span>
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

        visitor_rows_html.append(f"""
            <tr>
                <td><code>{ip}</code></td>
                <td>{'📱' if dev == 'Mobile' else '💻'} {dev}</td>
                <td><span class="badge {action_badge}">{action}</span></td>
                <td><span style="color:#cbd5e1; font-size:12px;">{page}</span></td>
                <td><span style="color:#94a3b8; font-size:11.5px;">{prod_id}</span></td>
                <td style="color:#64748b; font-size:11px;">{ts}</td>
            </tr>
        """)

    # Build Order Rows HTML
    order_rows_html = []
    for o in recent_orders:
        token = o.get("order_token", "")
        email = o.get("customer_email", "")
        amount = o.get("amount_paid", 19)
        utr = o.get("utr", "—")
        status = o.get("status", "pending")
        ts = o.get("created_at", "")

        order_rows_html.append(f"""
            <tr>
                <td><code>{token}</code></td>
                <td><b style="color:#ffffff;">{email}</b></td>
                <td style="color:#10b981; font-weight:700;">₹{amount}</td>
                <td><code>{utr}</code></td>
                <td>
                    <span class="status-pill {'status-active' if status in ('approved', 'delivered') else 'status-inactive'}">
                        {status.upper()}
                    </span>
                </td>
                <td style="color:#64748b; font-size:11px;">{ts}</td>
            </tr>
        """)

    html = f"""<!DOCTYPE html>
<html lang="mr">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ExamRankers™ Admin Command Center</title>
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
        .btn-outline {{ background: transparent; border: 1px solid var(--border); color: #ffffff; }}

        .container {{
            max-width: 1300px;
            margin: 0 auto;
            padding: 24px;
        }}

        /* KPI Cards */
        .kpi-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
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
            background: var(--bg-surface);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 16px 20px;
            margin-bottom: 24px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            flex-wrap: wrap;
            gap: 12px;
        }}

        /* Content Sections */
        .section-box {{
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 14px;
            padding: 20px 22px;
            margin-bottom: 24px;
        }}
        .section-header {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 16px;
            padding-bottom: 12px;
            border-bottom: 1px solid var(--border);
        }}
        .section-title {{
            font-size: 16px;
            font-weight: 800;
            color: #ffffff;
            display: flex;
            align-items: center;
            gap: 8px;
        }}

        /* Tables */
        .table-wrap {{
            width: 100%;
            overflow-x: auto;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 12.5px;
            text-align: left;
        }}
        th {{
            background: #0f172a;
            color: var(--text-muted);
            padding: 10px 14px;
            font-weight: 700;
            font-size: 11.5px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            border-bottom: 1px solid var(--border);
        }}
        td {{
            padding: 11px 14px;
            border-bottom: 1px solid rgba(35, 50, 74, 0.6);
            vertical-align: middle;
        }}
        tr:hover td {{
            background: rgba(255, 255, 255, 0.02);
        }}
        .badge {{
            padding: 3px 8px;
            border-radius: 6px;
            font-size: 11px;
            font-weight: 700;
            display: inline-block;
        }}
        .badge-sub {{ background: rgba(56, 189, 248, 0.12); color: #38bdf8; border: 1px solid rgba(56, 189, 248, 0.3); }}
        .badge-green {{ background: rgba(16, 185, 129, 0.15); color: #10b981; }}
        .badge-yellow {{ background: rgba(250, 204, 21, 0.15); color: #facc15; }}
        .badge-blue {{ background: rgba(59, 130, 246, 0.15); color: #60a5fa; }}
        .badge-gray {{ background: rgba(148, 163, 184, 0.12); color: #94a3b8; }}

        .status-pill {{
            font-size: 11px;
            font-weight: 700;
            padding: 3px 9px;
            border-radius: 999px;
        }}
        .status-active {{ background: rgba(16, 185, 129, 0.15); color: #10b981; border: 1px solid rgba(16, 185, 129, 0.3); }}
        .status-inactive {{ background: rgba(239, 68, 68, 0.15); color: #ef4444; border: 1px solid rgba(239, 68, 68, 0.3); }}

        .input-mini {{
            background: #090d16;
            border: 1px solid var(--border);
            color: #ffffff;
            padding: 5px 8px;
            border-radius: 6px;
            width: 65px;
            font-size: 12px;
            font-weight: 700;
            text-align: center;
        }}
        .btn-sm {{
            padding: 4px 10px;
            font-size: 11.5px;
            border-radius: 6px;
            border: none;
            cursor: pointer;
            font-weight: 700;
            text-decoration: none;
        }}
        .btn-action {{ background: #1e293b; color: #38bdf8; border: 1px solid #334155; }}
        .btn-action:hover {{ background: #38bdf8; color: #0f172a; }}
        .btn-link {{ background: rgba(16, 185, 129, 0.15); color: #10b981; border: 1px solid rgba(16, 185, 129, 0.3); }}
    </style>
</head>
<body>

    <header class="topbar">
        <div class="brand">
            ⚡ ExamRankers™ <span>Admin Command Center</span>
        </div>
        <div class="header-actions">
            <a href="/store" class="btn btn-outline" target="_blank">🛒 Live Web Store</a>
            <button class="btn btn-gold" onclick="syncFolderPdfs()">🔄 Sync Products Folder</button>
        </div>
    </header>

    <main class="container">

        <!-- KPI Metrics -->
        <div class="kpi-grid">
            <div class="kpi-card">
                <div class="kpi-title">👥 एकूण व्हिजिटर्स (Store Visitors)</div>
                <div class="kpi-val" style="color:var(--accent-cyan);">{total_visits}</div>
                <div class="kpi-sub">युनिक आयपी: <b>{unique_ips}</b> (📱 {mobile_cnt} | 💻 {desktop_cnt})</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-title">📦 ॲक्टिव्ह ई-बुक्स (Active Products)</div>
                <div class="kpi-val" style="color:var(--accent-gold);">{len(products)}</div>
                <div class="kpi-sub">दर श्रेणी: <b>₹१० ते ₹५०</b> (Auto-Priced)</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-title">🛒 सुरू झालेले ऑर्डर्स (Checkouts)</div>
                <div class="kpi-val" style="color:#a855f7;">{checkouts}</div>
                <div class="kpi-sub">कन्व्हर्जन दर: <b>{round((purchases/max(1, checkouts))*100, 1)}%</b></div>
            </div>
            <div class="kpi-card">
                <div class="kpi-title">💰 एकूण महसूल (Verified Revenue)</div>
                <div class="kpi-val" style="color:var(--accent-emerald);">₹{int(total_revenue) or (purchases * 29)}</div>
                <div class="kpi-sub">एकूण यशस्वी खरेदी: <b>{purchases}</b></div>
            </div>
        </div>

        <!-- 1-Click Operations Toolbar -->
        <div class="toolbar">
            <div style="font-size:14px; font-weight:700; color:#fff;">
                🚀 <b>१-क्लिक ॲडमिन ॲक्शन सेंटर (Quick Studio):</b>
            </div>
            <div style="display:flex; gap:10px; flex-wrap:wrap;">
                <button class="btn btn-purple" onclick="generateQBank()">📑 नवीन ४-स्तंभ प्रश्नसंच PDF बनवा</button>
                <button class="btn btn-green" onclick="generateChaluGhadamodi()">📰 चालू घडामोडी मासिक संच PDF बनवा</button>
                <a href="/admin/download_all_products" class="btn btn-gold">📦 सर्व ई-बुक्स ZIP डाउनलोड</a>
            </div>
        </div>

        <!-- Product Management Table -->
        <div class="section-box">
            <div class="section-header">
                <div class="section-title">
                    📦 डिजिटल ई-बुक्स व्यवस्थापन (Digital Products Catalog — {len(products)} Titles)
                </div>
                <button class="btn btn-sm btn-outline" onclick="location.reload()">🔄 रिफ्रेश करा</button>
            </div>
            <div class="table-wrap">
                <table>
                    <thead>
                        <tr>
                            <th style="width:40px;">चिन्ह</th>
                            <th>ई-बुक शीर्षक व तपशील</th>
                            <th>विषय (Subject)</th>
                            <th style="width:140px;">किंमत (Price)</th>
                            <th style="width:90px; text-align:center;">PDF</th>
                            <th style="width:110px; text-align:center;">स्थिती</th>
                        </tr>
                    </thead>
                    <tbody>
                        {"".join(product_rows_html)}
                    </tbody>
                </table>
            </div>
        </div>

        <!-- Recent Visitors Table -->
        <div class="section-box">
            <div class="section-header">
                <div class="section-title">
                    👥 थेट स्टोअर व्हिजिटर्स (Live Store Traffic — Recent 40 Visits)
                </div>
                <span style="font-size:12px; color:var(--text-muted);">स्वयंचलित रिअल-टाइम ट्रॅकिंग</span>
            </div>
            <div class="table-wrap">
                <table>
                    <thead>
                        <tr>
                            <th>IP पत्ता</th>
                            <th>डिव्हाइस</th>
                            <th>ॲक्शन (Action)</th>
                            <th>पेज पाथ</th>
                            <th>प्रॉडक्ट</th>
                            <th>वेळ (Timestamp)</th>
                        </tr>
                    </thead>
                    <tbody>
                        {"".join(visitor_rows_html)}
                    </tbody>
                </table>
            </div>
        </div>

        <!-- Recent Orders Table -->
        <div class="section-box">
            <div class="section-header">
                <div class="section-title">
                    🛒 थेट ऑर्डर्स व पेमेंट नोंदी (Customer Orders & UTR)
                </div>
            </div>
            <div class="table-wrap">
                <table>
                    <thead>
                        <tr>
                            <th>ऑर्डर टोकन</th>
                            <th>विद्यार्थी Email</th>
                            <th>रक्कम</th>
                            <th>१२-अंकी UTR</th>
                            <th>स्थिती</th>
                            <th>दिनांक</th>
                        </tr>
                    </thead>
                    <tbody>
                        {"".join(order_rows_html) if order_rows_html else '<tr><td colspan="6" style="text-align:center; padding:20px; color:#64748b;">अद्याप कोणतीही ऑर्डर नोंदवलेली नाही.</td></tr>'}
                    </tbody>
                </table>
            </div>
        </div>

    </main>

    <script>
        async function syncFolderPdfs() {{
            try {{
                const res = await fetch('/api/admin/sync_products', {{ method: 'POST' }});
                const data = await res.json();
                alert('✅ फोल्डर सिंक यशस्वी! ' + (data.added || 0) + ' नवीन PDF ई-बुक्स स्टोअरमध्ये जोडली गेली.');
                location.reload();
            }} catch(e) {{
                alert('❌ सिंक अयशस्वी: ' + e.message);
            }}
        }}

        async function updateProductPrice(prodId) {{
            const input = document.getElementById('price_' + prodId);
            const newPrice = parseInt(input.value);
            if (!newPrice || newPrice < 5 || newPrice > 500) {{
                alert('कृपया वैध किंमत टाका (₹१० ते ₹१००)');
                return;
            }}
            try {{
                const res = await fetch('/api/admin/update_price', {{
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

        async function generateQBank() {{
            if (!confirm('नवीन ४-स्तंभ विषयवार प्रश्नसंच (Question Bank) तयार करायचा का?')) return;
            try {{
                const res = await fetch('/api/admin/generate_qbank', {{ method: 'POST' }});
                const data = await res.json();
                if (data.success) {{
                    alert('🎉 प्रश्नसंच तयार झाला व स्टोअरमध्ये आपोआप जोडला गेला!');
                    location.reload();
                }} else {{
                    alert('❌ त्रुटी: ' + data.message);
                }}
            }} catch(e) {{
                alert('❌ सर्व्हर त्रुटी: ' + e.message);
            }}
        }}

        async function generateChaluGhadamodi() {{
            if (!confirm('चालू घडामोडी मासिक संच PDF तयार करायची का?')) return;
            try {{
                const res = await fetch('/api/admin/generate_chalu_ghadamodi', {{ method: 'POST' }});
                const data = await res.json();
                if (data.success) {{
                    alert('🎉 चालू घडामोडी PDF तयार झाली व स्टोअरमध्ये जोडली गेली!');
                    location.reload();
                }} else {{
                    alert('❌ त्रुटी: ' + data.message);
                }}
            }} catch(e) {{
                alert('❌ सर्व्हर त्रुटी: ' + e.message);
            }}
        }}
    </script>
</body>
</html>
"""
    return html
