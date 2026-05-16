#!/usr/bin/env python3
"""
Indiamart Inquiry Dashboard — Web UI for managing inquiries.
Run: python dashboard.py  →  http://localhost:8080
"""

import json
import sqlite3
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse
from pathlib import Path
import csv
import io

DB_PATH = "./data/inquiries.db"
PORT = 8080

CSS = """
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #f0f2f5; color: #1a1a2e; }
  .header { background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); color: white; padding: 24px 32px; }
  .header h1 { font-size: 24px; font-weight: 600; }
  .header .subtitle { opacity: 0.7; margin-top: 4px; font-size: 14px; }
  .stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 16px; padding: 24px 32px; }
  .stat-card { background: white; border-radius: 12px; padding: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }
  .stat-card .number { font-size: 32px; font-weight: 700; color: #1a1a2e; }
  .stat-card .label { font-size: 13px; color: #666; margin-top: 4px; }
  .filters { padding: 0 32px 16px; display: flex; gap: 12px; flex-wrap: wrap; }
  .filters select, .filters input { padding: 8px 14px; border: 1px solid #ddd; border-radius: 8px; font-size: 14px; }
  .filters button { padding: 8px 20px; background: #1a1a2e; color: white; border: none; border-radius: 8px; cursor: pointer; font-size: 14px; }
  .filters button:hover { background: #16213e; }
  table { width: calc(100% - 64px); margin: 0 32px 32px; background: white; border-radius: 12px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.08); border-collapse: collapse; }
  th { background: #f8f9fa; text-align: left; padding: 12px 16px; font-size: 13px; color: #666; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; }
  td { padding: 12px 16px; border-top: 1px solid #f0f0f0; font-size: 14px; }
  tr:hover { background: #f8f9fa; }
  .badge { display: inline-block; padding: 2px 10px; border-radius: 12px; font-size: 12px; font-weight: 500; }
  .badge-new { background: #e3f2fd; color: #1565c0; }
  .badge-contacted { background: #fff3e0; color: #e65100; }
  .badge-qualified { background: #e8f5e9; color: #2e7d32; }
  .badge-closed { background: #f5f5f5; color: #616161; }
  .btn { padding: 4px 12px; border-radius: 6px; font-size: 12px; cursor: pointer; border: none; margin-right: 4px; text-decoration: none; display: inline-block; }
  .btn-call { background: #e8f5e9; color: #2e7d32; }
  .btn-sms { background: #e3f2fd; color: #1565c0; }
  .btn-wa { background: #e8f5e9; color: #075e54; }
  .btn-close { background: #ffebee; color: #c62828; }
  .empty { text-align: center; padding: 48px; color: #999; }
  @media (max-width: 768px) {
    .stats { grid-template-columns: repeat(2, 1fr); }
    table { font-size: 13px; }
    td, th { padding: 8px; }
  }
"""


def html_page(total, new_count, contacted, qualified, category_options, table_rows):
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Indiamart Inquiry Dashboard</title>
<style>{CSS}</style>
</head>
<body>
  <div class="header">
    <h1>📊 Indiamart Inquiry Dashboard</h1>
    <div class="subtitle">Manage and track business inquiries from Indiamart</div>
  </div>
  <div class="stats">
    <div class="stat-card"><div class="number">{total}</div><div class="label">Total Inquiries</div></div>
    <div class="stat-card"><div class="number">{new_count}</div><div class="label">New Today</div></div>
    <div class="stat-card"><div class="number">{contacted}</div><div class="label">Contacted</div></div>
    <div class="stat-card"><div class="number">{qualified}</div><div class="label">Qualified</div></div>
  </div>
  <div class="filters">
    <select id="categoryFilter" onchange="filterTable()">
      <option value="">All Categories</option>
      {category_options}
    </select>
    <select id="statusFilter" onchange="filterTable()">
      <option value="">All Status</option>
      <option value="new">New</option>
      <option value="contacted">Contacted</option>
      <option value="qualified">Qualified</option>
      <option value="closed">Closed</option>
    </select>
    <input type="text" id="searchBox" placeholder="Search name, phone, product..." oninput="filterTable()">
    <button onclick="exportCSV()">📥 Export CSV</button>
    <button onclick="refreshPage()">🔄 Refresh</button>
  </div>
  <table id="inquiryTable">
    <thead>
      <tr><th>ID</th><th>Name</th><th>Phone</th><th>Product</th><th>Category</th><th>City</th><th>Date</th><th>Status</th><th>Actions</th></tr>
    </thead>
    <tbody>
      {table_rows}
    </tbody>
  </table>
  <script>
    function filterTable() {{
      const cat = document.getElementById('categoryFilter').value.toLowerCase();
      const status = document.getElementById('statusFilter').value.toLowerCase();
      const search = document.getElementById('searchBox').value.toLowerCase();
      document.querySelectorAll('#inquiryTable tbody tr').forEach(row => {{
        const text = row.textContent.toLowerCase();
        const rowCat = row.dataset.category.toLowerCase();
        const rowStatus = row.dataset.status.toLowerCase();
        const show = (!cat || rowCat.includes(cat)) && (!status || rowStatus === status) && (!search || text.includes(search));
        row.style.display = show ? '' : 'none';
      }});
    }}
    function exportCSV() {{ window.location.href = '/export'; }}
    function refreshPage() {{ location.reload(); }}
    function updateStatus(id, status) {{ fetch(`/api/status?id=${{id}}&status=${{status}}`).then(() => location.reload()); }}
  </script>
</body>
</html>"""


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def render_dashboard():
    conn = get_db()
    rows = conn.execute("SELECT * FROM inquiries ORDER BY created_at DESC LIMIT 200").fetchall()
    total = conn.execute("SELECT COUNT(*) FROM inquiries").fetchone()[0]
    today = datetime.now().strftime("%Y-%m-%d")
    new_count = conn.execute("SELECT COUNT(*) FROM inquiries WHERE created_at LIKE ?", (f"{today}%",)).fetchone()[0]
    contacted = conn.execute("SELECT COUNT(*) FROM inquiries WHERE status='contacted'").fetchone()[0]
    qualified = conn.execute("SELECT COUNT(*) FROM inquiries WHERE status='qualified'").fetchone()[0]
    conn.close()

    categories = set()
    table_rows = []
    for r in rows:
        cats = json.loads(r["categories"]) if r["categories"] else ["Other"]
        categories.update(cats)
        badge_class = f"badge-{r['status']}"
        phone = r["phone"] or "N/A"
        city = r["location"] or "—"
        date_str = r["inquiry_date"][:10] if r["inquiry_date"] else "—"

        actions = ""
        if r["phone"]:
            clean_phone = r["phone"].replace("+", "")
            actions += f'<a class="btn btn-call" href="tel:{r["phone"]}">📞</a>'
            actions += f'<a class="btn btn-sms" href="sms:{r["phone"]}">💬</a>'
            actions += f'<a class="btn btn-wa" href="https://wa.me/{clean_phone}" target="_blank">📱</a>'
        actions += f'<button class="btn btn-close" onclick="updateStatus(\'{r["id"]}\',\'closed\')">✕</button>'

        table_rows.append(
            f'<tr data-category="{" ".join(cats)}" data-status="{r["status"]}">'
            f'<td>{r["id"]}</td><td>{r["customer_name"]}</td><td>{phone}</td>'
            f'<td>{r["product_interest"][:40]}</td><td>{", ".join(cats)}</td>'
            f'<td>{city}</td><td>{date_str}</td>'
            f'<td><span class="badge {badge_class}">{r["status"]}</span></td>'
            f'<td>{actions}</td></tr>'
        )

    category_options = "".join(f'<option value="{c}">{c}</option>' for c in sorted(categories))

    if not table_rows:
        table_rows = ['<tr><td colspan="9" class="empty">No inquiries yet. Run the extractor first.</td></tr>']

    return html_page(total, new_count, contacted, qualified, category_options, "\n      ".join(table_rows))


def export_csv():
    conn = get_db()
    rows = conn.execute("SELECT * FROM inquiries ORDER BY created_at DESC").fetchall()
    conn.close()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id", "name", "phone", "email", "product", "category", "city", "date", "status"])
    for r in rows:
        cats = json.loads(r["categories"])[0] if r["categories"] else "Other"
        writer.writerow([r["id"], r["customer_name"], r["phone"], r["email"],
                         r["product_interest"], cats, r["location"], r["inquiry_date"], r["status"]])
    return output.getvalue()


class DashboardHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/export":
            self.send_response(200)
            self.send_header("Content-Type", "text/csv")
            self.send_header("Content-Disposition", "attachment; filename=inquiries_export.csv")
            self.end_headers()
            self.wfile.write(export_csv().encode())
        elif parsed.path == "/api/status":
            params = parse_qs(parsed.query)
            inq_id = params.get("id", [""])[0]
            status = params.get("status", ["new"])[0]
            conn = get_db()
            conn.execute("UPDATE inquiries SET status = ? WHERE id = ?", (status, inq_id))
            conn.commit()
            conn.close()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"ok":true}')
        else:
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(render_dashboard().encode())

    def log_message(self, format, *args):
        pass


def main():
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""CREATE TABLE IF NOT EXISTS inquiries (
        id TEXT PRIMARY KEY, customer_name TEXT, phone TEXT, all_phones TEXT,
        email TEXT, product_interest TEXT, categories TEXT, requirement TEXT,
        quantity TEXT, location TEXT, inquiry_date TEXT, status TEXT DEFAULT 'new',
        follow_up_day INTEGER DEFAULT 0, source_message_id TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""")
    conn.commit()
    conn.close()

    server = HTTPServer(("0.0.0.0", PORT), DashboardHandler)
    print(f"🌐 Dashboard running at http://localhost:{PORT}")
    print("   Press Ctrl+C to stop")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
