#!/usr/bin/env python3
"""
Arihant Enterprises Mobile CRM — Native-feeling PWA.
Run: python mobile.py  →  http://localhost:8080
"""

import json, sqlite3, csv, io, os, re, random, time, base64, threading
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import quote, parse_qs, urlparse
from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.request, ssl

DB_PATH = "./data/inquiries.db"
PORT = 8080
COMPANY = "Arihant Enterprises"
PHONE = "+917020134619"
LOCATION = "Pune"
BIZ_TYPE = "Manufacturer & Exporter"

# ── Email Extraction (background) ───────────────────────────────────────────

_extract_status = {"running": False, "progress": "", "last_run": None, "count": 0}

def run_extraction():
    """Fetch Indiamart emails from Gmail in background thread."""
    global _extract_status
    if _extract_status["running"]:
        return
    _extract_status["running"] = True
    _extract_status["progress"] = "Connecting to Gmail..."

    try:
        from dotenv import load_dotenv
        from bs4 import BeautifulSoup
        import imaplib, email
        from email.header import decode_header
        import quopri

        load_dotenv(Path(__file__).parent / ".env")
        GMAIL_USER = os.environ.get("GMAIL_USER", "")
        GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "")

        if not GMAIL_USER or not GMAIL_APP_PASSWORD:
            _extract_status["progress"] = "❌ Set GMAIL_USER and GMAIL_APP_PASSWORD in .env"
            _extract_status["running"] = False
            return

        _extract_status["progress"] = f"Connecting as {GMAIL_USER}..."
        mail = imaplib.IMAP4_SSL("imap.gmail.com", 993)
        mail.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        mail.select("INBOX")

        _extract_status["progress"] = "Searching for Indiamart emails..."
        status, message_ids = mail.search(None, '(FROM "indiamart")')
        if status != "OK":
            _extract_status["progress"] = "❌ Search failed"
            mail.logout()
            _extract_status["running"] = False
            return

        ids = message_ids[0].split()
        if not ids:
            _extract_status["progress"] = "📭 No emails found"
            mail.logout()
            _extract_status["running"] = False
            return

        # Take last 2000
        ids = ids[-2000:]
        _extract_status["progress"] = f"Processing {len(ids)} emails..."

        conn = sqlite3.connect(DB_PATH)
        conn.execute("""CREATE TABLE IF NOT EXISTS inquiries (
            id TEXT PRIMARY KEY, customer_name TEXT, phone TEXT, all_phones TEXT,
            email TEXT, product_interest TEXT, categories TEXT, requirement TEXT,
            quantity TEXT, location TEXT, inquiry_date TEXT, status TEXT DEFAULT 'new',
            follow_up_day INTEGER DEFAULT -1, source_message_id TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )""")

        phone_re = re.compile(r'(?:\+91[\s\-\.]?)?[6-9]\d{4}[\s\-\.]?\d{5}|\+91[6-9]\d{9}|(?:^|\s)[6-9]\d{9}(?:\s|$)')
        email_re = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')
        cities = ["Mumbai","Delhi","Bangalore","Bengaluru","Hyderabad","Ahmedabad","Chennai","Kolkata","Pune","Jaipur","Lucknow","Kanpur","Nagpur","Indore","Thane","Bhopal","Visakhapatnam","Patna","Vadodara","Ghaziabad","Ludhiana","Agra","Nashik","Faridabad","Meerut","Rajkot","Varanasi","Srinagar","Aurangabad","Amritsar","Coimbatore","Jabalpur","Gwalior","Vijayawada","Jodhpur","Madurai","Raipur","Kochi","Chandigarh","Mysore","Thiruvananthapuram","Surat"]
        categories_kw = {"Vending Machines":["vending","coffee machine","automatic machine","dispenser"],"Tea/Coffee Premix":["premix","tea premix","coffee premix","instant mix"],"Jaggery Products":["jaggery","gur","organic sweetener"],"Nescafe Premix":["nescafe","nestle premix"],"Bru Premix":["bru","bru premix","hcc premix"],"Society Premix":["society","housing society","apartment","bulk"]}

        count = 0
        for idx, mid in enumerate(ids):
            if idx % 50 == 0:
                _extract_status["progress"] = f"Processing {idx+1}/{len(ids)}..."
            try:
                st, msg_data = mail.fetch(mid, "(RFC822)")
                if st != "OK": continue
                raw = msg_data[0][1]
                msg = email.message_from_bytes(raw)

                # Decode headers
                subject = ""
                for part, charset in decode_header(msg.get("Subject","")):
                    subject += (part.decode(charset or "utf-8","replace") if isinstance(part,bytes) else str(part)) + " "
                subject = subject.strip()

                sender = ""
                for part, charset in decode_header(msg.get("From","")):
                    sender += (part.decode(charset or "utf-8","replace") if isinstance(part,bytes) else str(part)) + " "
                sender = sender.strip()

                date_str = msg.get("Date","")
                msg_id = msg.get("Message-ID", mid.decode())

                sender_name = ""
                sender_email = ""
                if "<" in sender and ">" in sender:
                    sender_name = sender.split("<")[0].strip().strip('"')
                    sender_email = sender.split("<")[1].split(">")[0]
                else:
                    sender_email = sender

                # Get body (HTML → text)
                body = ""
                html_body = ""
                if msg.is_multipart():
                    for part in msg.walk():
                        ct = part.get_content_type()
                        cd = str(part.get("Content-Disposition",""))
                        if "attachment" in cd: continue
                        payload = part.get_payload(decode=True)
                        if not payload: continue
                        charset = part.get_content_charset() or "utf-8"
                        try: text = payload.decode(charset, errors="replace")
                        except: text = payload.decode("utf-8","replace")
                        if ct == "text/html": html_body = text
                        elif ct == "text/plain" and not body: body = text
                else:
                    payload = msg.get_payload(decode=True)
                    if payload:
                        charset = msg.get_content_charset() or "utf-8"
                        try: text = payload.decode(charset,"replace")
                        except: text = payload.decode("utf-8","replace")
                        if msg.get_content_type() == "text/html": html_body = text
                        else: body = text

                if html_body:
                    try:
                        soup = BeautifulSoup(html_body, "html.parser")
                        for tag in soup(["script","style"]): tag.decompose()
                        body = soup.get_text("\n", strip=True)
                        body = re.sub(r'\n{3,}', '\n\n', body)
                    except: pass

                combined = f"{subject}\n{body}"

                # Extract name
                name = sender_name
                for pat in [r'(?:from|name|contact\s*person|buyer\s*name)[\s:]+([A-Z][a-z]+(?:\s[A-Z][a-z]+)*)', r'Name\s*[:\-]\s*([A-Z][a-z]+(?:\s[A-Z][a-z]+)*)']:
                    m = re.search(pat, body, re.IGNORECASE)
                    if m:
                        name = m.group(1).strip()
                        break

                system_names = ["IndiaMART","IndiaMART Feedback","IndiaMART Advantage","IndiaMART BuyLeads","IndiaMART Reminder","Customer Care-IM","IndiaMART.com","noreply"]
                if any(s.lower() in (name or "").lower() for s in system_names):
                    for pat in [r'(?:from|name|contact\s*person)[\s:]+([A-Z][a-z]+(?:\s[A-Z][a-z]+)*)']:
                        m = re.search(pat, body, re.IGNORECASE)
                        if m:
                            candidate = m.group(1).strip()
                            if not any(s.lower() in candidate.lower() for s in system_names):
                                name = candidate
                                break

                # Extract phones
                raw_phones = phone_re.findall(combined)
                phones = []
                for p in raw_phones:
                    digits = re.sub(r'\D','',p)
                    if len(digits)==12 and digits.startswith('91'): digits=digits[2:]
                    if len(digits)==10 and digits[0] in '6789': phones.append(f"+91{digits}")
                phones = list(set(phones))

                # Extract emails
                found_emails = [e for e in email_re.findall(combined) if 'indiamart' not in e.lower() and e != sender_email]

                # Classify
                text_lower = combined.lower()
                matched = [cat for cat, kw in categories_kw.items() if any(k in text_lower for k in kw)]
                cats = matched if matched else ["Other"]

                # Location
                loc = None
                for city in cities:
                    if re.search(rf'\b{city}\b', combined, re.IGNORECASE):
                        loc = city; break

                inquiry = {
                    "id": f"IND-{datetime.now().strftime('%Y%m%d')}-{msg_id[:8]}",
                    "customer_name": name or "Unknown",
                    "phone": phones[0] if phones else None,
                    "all_phones": json.dumps(phones),
                    "email": found_emails[0] if found_emails else sender_email,
                    "product_interest": subject,
                    "categories": json.dumps(cats),
                    "requirement": body[:500].strip(),
                    "location": loc,
                    "inquiry_date": date_str,
                    "status": "new",
                    "follow_up_day": -1,
                    "source_message_id": msg_id,
                }

                conn.execute("""INSERT OR REPLACE INTO inquiries
                    (id,customer_name,phone,all_phones,email,product_interest,categories,requirement,location,inquiry_date,status,follow_up_day,source_message_id)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (inquiry["id"],inquiry["customer_name"],inquiry["phone"],inquiry["all_phones"],inquiry["email"],inquiry["product_interest"],inquiry["categories"],inquiry["requirement"],inquiry["location"],inquiry["inquiry_date"],inquiry["status"],inquiry["follow_up_day"],inquiry["source_message_id"]))
                count += 1
            except Exception as e:
                continue

        conn.commit()
        conn.close()
        mail.logout()

        _extract_status["progress"] = f"✅ Done! {count} emails extracted"
        _extract_status["count"] = count
        _extract_status["last_run"] = datetime.now().isoformat()

    except Exception as e:
        _extract_status["progress"] = f"❌ Error: {str(e)[:100]}"
    finally:
        _extract_status["running"] = False

# ── Gemini ───────────────────────────────────────────────────────────────────

def gemini(api_key, prompt):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"
    data = json.dumps({"contents":[{"parts":[{"text":prompt}]}],"generationConfig":{"temperature":0.8,"maxOutputTokens":500}}).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type":"application/json"})
    try:
        with urllib.request.urlopen(req, context=ssl.create_default_context(), timeout=15) as r:
            return json.loads(r.read())["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        return f"Error: {e}"

# ── DB ───────────────────────────────────────────────────────────────────────

def db():
    c = sqlite3.connect(DB_PATH); c.row_factory = sqlite3.Row; return c

def rows(r): return [dict(x) for x in r]

def parse_cats(c):
    if not c: return ["Other"]
    try: return json.loads(c)
    except: return [c]

def get_stats():
    c = db()
    t = c.execute("SELECT COUNT(*) FROM inquiries").fetchone()[0]
    n = c.execute("SELECT COUNT(*) FROM inquiries WHERE status='new'").fetchone()[0]
    ct = c.execute("SELECT COUNT(*) FROM inquiries WHERE status='contacted'").fetchone()[0]
    cl = c.execute("SELECT COUNT(*) FROM inquiries WHERE status='closed'").fetchone()[0]
    ph = c.execute("SELECT COUNT(*) FROM inquiries WHERE phone IS NOT NULL AND phone!=''").fetchone()[0]
    cats = {}
    for r in c.execute("SELECT categories,COUNT(*) as cnt FROM inquiries GROUP BY categories"):
        for cat in parse_cats(r["categories"]):
            cats[cat] = cats.get(cat, 0) + r["cnt"]
    recent = rows(c.execute("SELECT * FROM inquiries ORDER BY created_at DESC LIMIT 15").fetchall())
    c.close()
    return {"total":t,"new":n,"contacted":ct,"closed":cl,"phone":ph,"no_phone":t-ph,"cats":cats,"recent":recent}

def get_inquiries(f=None):
    c = db(); q = "SELECT * FROM inquiries WHERE 1=1"; p = []
    if f:
        if f.get("status"): q += " AND status=?"; p.append(f["status"])
        if f.get("cat"): q += " AND categories LIKE ?"; p.append(f"%{f['cat']}%")
        if f.get("q"): q += " AND (customer_name LIKE ? OR product_interest LIKE ? OR phone LIKE ?)"; s=f"%{f['q']}%"; p.extend([s,s,s])
        if f.get("ph"):
            if f["ph"]=="yes": q += " AND phone IS NOT NULL AND phone!=''"
            else: q += " AND (phone IS NULL OR phone='')"
    q += " ORDER BY inquiry_date DESC"
    r = rows(c.execute(q, p).fetchall()); c.close()
    for x in r: x["_cats"] = parse_cats(x.get("categories"))
    return r

def get_one(id):
    c = db(); r = c.execute("SELECT * FROM inquiries WHERE id=?",(id,)).fetchone(); c.close()
    if r: r = dict(r); r["_cats"] = parse_cats(r.get("categories"))
    return r

def update(id, d):
    c = db()
    for k in ["customer_name","phone","email","product_interest","categories","status","follow_up_day","location"]:
        if k in d: c.execute(f"UPDATE inquiries SET {k}=? WHERE id=?",(d[k],id))
    c.commit(); c.close()

def add_inq(d):
    c = db()
    rid = ''.join(random.choices("abcdefghijklmnopqrstuvwxyz0123456789",k=8))
    iid = f"IND-{datetime.now().strftime('%Y%m%d')}-{rid}"
    c.execute("INSERT INTO inquiries (id,customer_name,phone,email,product_interest,categories,requirement,location,inquiry_date,status,follow_up_day) VALUES (?,?,?,?,?,?,?,?,?,?,0)",
        (iid,d.get("customer_name","Unknown"),d.get("phone") or None,d.get("email",""),d.get("product_interest",""),json.dumps([d.get("category","Other")]),d.get("requirement",""),d.get("location",""),datetime.now().isoformat(),"new"))
    c.commit(); c.close(); return iid

def delete(id):
    c = db(); c.execute("DELETE FROM inquiries WHERE id=?",(id,)); c.commit(); c.close()

def bulk_status(ids, st):
    c = db()
    for i in ids: c.execute("UPDATE inquiries SET status=? WHERE id=?",(st,i))
    c.commit(); c.close()

# ── HTML ─────────────────────────────────────────────────────────────────────

def html():
    return '''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no,viewport-fit=cover">
<meta name="theme-color" content="#0a0e27">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="Arihant CRM">
<link rel="manifest" href="/manifest.json">
<link rel="apple-touch-icon" href="/icon.png">
<title>Arihant CRM</title>
<style>
:root{--bg:#0a0e27;--card:#131836;--card2:#1a2040;--primary:#6c5ce7;--green:#00b894;--red:#ff6b6b;--orange:#fdcb6e;--blue:#74b9ff;--text:#dfe6e9;--muted:#636e72;--border:#2d3436;--glass:rgba(19,24,54,.85);--radius:16px;--shadow:0 8px 32px rgba(0,0,0,.3)}
*{margin:0;padding:0;box-sizing:border-box;-webkit-tap-highlight-color:transparent}
body{font-family:-apple-system,BlinkMacSystemFont,'SF Pro','Segoe UI',Roboto,sans-serif;background:var(--bg);color:var(--text);min-height:100vh;min-height:100dvh;overflow-x:hidden;user-select:none;-webkit-user-select:none}
.app{max-width:500px;margin:0 auto;min-height:100vh;min-height:100dvh;position:relative;padding-bottom:calc(70px + env(safe-area-inset-bottom))}
.header{background:linear-gradient(135deg,#0a0e27 0%,#1a1e3e 100%);padding:calc(12px + env(safe-area-inset-top)) 16px 12px;position:sticky;top:0;z-index:100;border-bottom:1px solid var(--border)}
.header-row{display:flex;align-items:center;justify-content:space-between}
.header h1{font-size:18px;font-weight:800;background:linear-gradient(135deg,#fff,#74b9ff);-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.header .sub{font-size:10px;color:var(--muted);margin-top:2px;letter-spacing:.5px}
.settings-btn{width:36px;height:36px;border-radius:12px;background:var(--card);border:1px solid var(--border);display:flex;align-items:center;justify-content:center;cursor:pointer;font-size:16px}
.tab-bar{display:flex;gap:4px;padding:8px 16px;overflow-x:auto;scrollbar-width:none;-webkit-overflow-scrolling:touch}
.tab-bar::-webkit-scrollbar{display:none}
.tab{padding:8px 14px;border-radius:20px;font-size:12px;font-weight:600;white-space:nowrap;cursor:pointer;transition:all .2s;background:var(--card);color:var(--muted);border:1px solid transparent}
.tab.active{background:var(--primary);color:#fff;border-color:var(--primary)}
.tab .cnt{font-size:10px;opacity:.7;margin-left:4px}
.page{display:none;padding:12px 16px;animation:fadeUp .3s ease}
.page.active{display:block}
@keyframes fadeUp{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:translateY(0)}}
.stats{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-bottom:16px}
.stat{background:var(--card);border-radius:var(--radius);padding:14px 10px;text-align:center;border:1px solid var(--border)}
.stat .n{font-size:24px;font-weight:800}.stat .l{font-size:9px;color:var(--muted);text-transform:uppercase;letter-spacing:1px;margin-top:2px}
.stat.g .n{color:var(--green)}.stat.o .n{color:var(--orange)}.stat.r .n{color:var(--red)}.stat.b .n{color:var(--blue)}
.card{background:var(--card);border-radius:var(--radius);padding:14px;margin-bottom:10px;border:1px solid var(--border)}
.card h3{font-size:13px;font-weight:700;margin-bottom:10px;display:flex;align-items:center;gap:6px}
.list-item{display:flex;align-items:center;gap:10px;padding:10px 0;border-bottom:1px solid var(--border);cursor:pointer;transition:background .15s}
.list-item:last-child{border-bottom:none}
.list-item:active{background:var(--card2)}
.avatar{width:38px;height:38px;border-radius:12px;display:flex;align-items:center;justify-content:center;font-weight:800;font-size:15px;color:#fff;flex-shrink:0}
.info{flex:1;min-width:0}.info .name{font-size:13px;font-weight:700;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.info .prod{font-size:11px;color:var(--muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;margin-top:2px}
.meta{text-align:right;flex-shrink:0}.meta .date{font-size:10px;color:var(--muted)}
.badge{font-size:9px;padding:2px 8px;border-radius:10px;font-weight:700;display:inline-block;margin-top:3px}
.badge-new{background:rgba(0,184,148,.15);color:var(--green)}.badge-contacted{background:rgba(253,203,110,.15);color:var(--orange)}.badge-closed{background:rgba(255,107,107,.15);color:var(--red)}
.cat{display:inline-block;padding:2px 7px;border-radius:8px;font-size:9px;font-weight:600;background:rgba(116,185,255,.12);color:var(--blue);margin:1px}
.search{display:flex;gap:8px;margin-bottom:10px}
.search input{flex:1;background:var(--card);border:1px solid var(--border);border-radius:12px;padding:10px 14px;color:var(--text);font-size:13px;outline:none}
.search input:focus{border-color:var(--primary)}
.filters{display:flex;gap:6px;margin-bottom:12px;overflow-x:auto;scrollbar-width:none}
.filters::-webkit-scrollbar{display:none}
.filters select{background:var(--card);border:1px solid var(--border);border-radius:10px;padding:7px 10px;color:var(--text);font-size:11px;outline:none;flex-shrink:0}
.btn{display:inline-flex;align-items:center;justify-content:center;gap:6px;padding:10px 18px;border:none;border-radius:12px;font-size:13px;font-weight:700;cursor:pointer;transition:all .2s}
.btn:active{transform:scale(.96)}.btn-green{background:var(--green);color:#fff}.btn-blue{background:var(--primary);color:#fff}
.btn-outline{background:transparent;border:1.5px solid var(--border);color:var(--text)}.btn-red{background:var(--red);color:#fff}
.btn-sm{padding:7px 12px;font-size:11px;border-radius:10px}.btn-block{display:flex;width:100%}
input,select,textarea{width:100%;background:var(--card);border:1.5px solid var(--border);border-radius:12px;padding:10px 12px;color:var(--text);font-size:13px;margin-bottom:10px;font-family:inherit;outline:none}
input:focus,select:focus,textarea:focus{border-color:var(--primary)}
textarea{resize:none;min-height:60px}
label{font-size:11px;font-weight:600;color:var(--muted);margin-bottom:4px;display:block;text-transform:uppercase;letter-spacing:.5px}
.sheet{position:fixed;inset:0;z-index:200;display:none}
.sheet.show{display:block}
.sheet-bg{position:absolute;inset:0;background:rgba(0,0,0,.6);backdrop-filter:blur(4px);-webkit-backdrop-filter:blur(4px)}
.sheet-content{position:absolute;bottom:0;left:0;right:0;background:var(--card);border-radius:20px 20px 0 0;max-height:90vh;overflow-y:auto;padding:20px 16px calc(20px + env(safe-area-inset-bottom));animation:slideUp .3s ease}
@keyframes slideUp{from{transform:translateY(100%)}to{transform:translateY(0)}}
.sheet-handle{width:36px;height:4px;background:var(--border);border-radius:2px;margin:0 auto 16px}
.field{margin-bottom:14px}.field label{margin-bottom:4px}.field .val{font-size:14px;padding:4px 0}
.msg-box{background:rgba(0,184,148,.08);border:1px solid rgba(0,184,148,.2);border-radius:12px;padding:12px;font-size:12px;white-space:pre-wrap;line-height:1.6;margin:8px 0}
.wa-btn{display:flex;align-items:center;justify-content:center;gap:8px;padding:12px;background:#25d366;color:#fff;border-radius:12px;text-decoration:none;font-weight:700;font-size:14px;margin:8px 0}
.wa-btn:active{background:#1da851}
.pill{display:inline-flex;align-items:center;gap:4px;padding:6px 12px;border-radius:20px;font-size:11px;font-weight:600;cursor:pointer;border:1.5px solid var(--border);background:var(--card);color:var(--muted);transition:all .2s}
.pill.active{background:var(--primary);color:#fff;border-color:var(--primary)}
.pill:active{transform:scale(.95)}
.check-row{display:flex;align-items:center;gap:10px;padding:10px 0;border-bottom:1px solid var(--border)}
.check-row:last-child{border-bottom:none}
.check-row input[type=checkbox]{width:20px;height:20px;accent-color:var(--green);margin:0}
.toast{position:fixed;bottom:calc(80px + env(safe-area-inset-bottom));left:50%;transform:translateX(-50%);background:var(--card2);color:#fff;padding:10px 20px;border-radius:20px;font-size:12px;z-index:300;display:none;border:1px solid var(--border);backdrop-filter:blur(10px)}
.toast.show{display:block;animation:fadeIn .3s}
@keyframes fadeIn{from{opacity:0;transform:translateX(-50%) translateY(10px)}to{opacity:1;transform:translateX(-50%) translateY(0)}}
.fab{position:fixed;bottom:calc(76px + env(safe-area-inset-bottom));right:16px;width:52px;height:52px;border-radius:16px;background:linear-gradient(135deg,var(--primary),#a29bfe);color:#fff;display:flex;align-items:center;justify-content:center;font-size:24px;box-shadow:0 8px 24px rgba(108,92,231,.4);cursor:pointer;z-index:90;border:none}
.fab:active{transform:scale(.9)}
.bottom-nav{position:fixed;bottom:0;left:0;right:0;background:var(--glass);backdrop-filter:blur(20px);-webkit-backdrop-filter:blur(20px);border-top:1px solid var(--border);display:flex;z-index:100;padding-bottom:env(safe-area-inset-bottom)}
.nav{flex:1;padding:10px 4px 8px;text-align:center;font-size:9px;color:var(--muted);cursor:pointer;transition:color .2s}
.nav.active{color:var(--primary)}.nav svg{display:block;margin:0 auto 2px;width:22px;height:22px}
.install-banner{display:none;position:fixed;bottom:calc(70px + env(safe-area-inset-bottom));left:12px;right:12px;background:linear-gradient(135deg,var(--primary),#a29bfe);padding:14px;border-radius:16px;z-index:95;box-shadow:0 8px 32px rgba(108,92,231,.4)}
.install-banner .row{display:flex;align-items:center;gap:10px}
.install-banner .ico{font-size:28px}.install-banner .txt{flex:1}
.install-banner .t{font-weight:700;font-size:13px}.install-banner .s{font-size:10px;opacity:.8}
.empty{text-align:center;padding:40px 20px;color:var(--muted)}
.empty .ico{font-size:48px;margin-bottom:12px}
.empty .t{font-size:14px;font-weight:600}.empty .s{font-size:12px;margin-top:4px}
</style>
</head>
<body>
<div class="app">

<div class="header">
  <div class="header-row">
    <div>
      <h1>🏢 Arihant Enterprises</h1>
      <div class="sub">Manufacturer & Exporter • Pune</div>
    </div>
    <div class="settings-btn" onclick="togglePanel('settings')">⚙️</div>
  </div>
</div>

<div class="tab-bar" id="main-tabs">
  <div class="tab active" data-page="home" onclick="go('home')">📊 Home</div>
  <div class="tab" data-page="inquiries" onclick="go('inquiries')">📋 Inquiries<span class="cnt" id="cnt-total"></span></div>
  <div class="tab" data-page="bulk" onclick="go('bulk')">🚀 Bulk Send</div>
  <div class="tab" data-page="follow" onclick="go('follow')">📱 Follow-up</div>
</div>

<!-- HOME -->
<div class="page active" id="page-home">
  <div class="stats" id="stats"></div>
  <div class="card" style="background:linear-gradient(135deg,rgba(0,184,148,.1),rgba(0,184,148,.05));border-color:rgba(0,184,148,.2)">
    <h3>📬 Fetch New Emails</h3>
    <p style="font-size:11px;color:var(--muted);margin-bottom:10px">Pull latest Indiamart inquiries from Gmail</p>
    <button class="btn btn-green btn-block" id="home-extract-btn" onclick="startExtractHome()">🔄 Fetch from Gmail</button>
    <div id="home-extract-status" style="font-size:11px;margin-top:8px;color:var(--muted);min-height:16px"></div>
  </div>
  <div class="card">
    <h3>📂 Categories</h3>
    <div id="cat-list"></div>
  </div>
  <div class="card">
    <h3>🕐 Recent</h3>
    <div id="recent"></div>
  </div>
</div>

<!-- INQUIRIES -->
<div class="page" id="page-inquiries">
  <div class="search"><input type="text" id="s-q" placeholder="🔍 Search name, product, phone..." oninput="deb(loadInq,300)"></div>
  <div class="filters">
    <select id="s-st" onchange="loadInq()"><option value="">All Status</option><option value="new">New</option><option value="contacted">Contacted</option><option value="closed">Closed</option></select>
    <select id="s-ph" onchange="loadInq()"><option value="">All</option><option value="yes">Has Phone</option><option value="no">No Phone</option></select>
    <select id="s-cat" onchange="loadInq()"><option value="">All Categories</option><option>Vending Machines</option><option>Tea/Coffee Premix</option><option>Jaggery Products</option><option>Nescafe Premix</option><option>Bru Premix</option><option>Society Premix</option><option>Other</option></select>
  </div>
  <div id="inq-list"></div>
</div>

<!-- BULK -->
<div class="page" id="page-bulk">
  <div class="card" style="background:linear-gradient(135deg,rgba(108,92,231,.15),rgba(162,155,254,.1));border-color:rgba(108,92,231,.3)">
    <h3>🚀 WhatsApp Bulk Sender</h3>
    <p style="font-size:11px;color:var(--muted)">Select category → contacts → AI generates messages → send</p>
  </div>
  <div class="card"><h3>1️⃣ Category</h3><div id="bulk-cats" style="display:flex;flex-wrap:wrap;gap:6px"></div></div>
  <div class="card"><h3>2️⃣ Message Type</h3>
    <div style="display:flex;flex-wrap:wrap;gap:6px">
      <span class="pill active" data-t="thank_you" onclick="selTpl(this)">👋 Thank You</span>
      <span class="pill" data-t="offer" onclick="selTpl(this)">🎯 Offer</span>
      <span class="pill" data-t="reengagement" onclick="selTpl(this)">🔄 Follow-up</span>
    </div>
  </div>
  <div class="card"><h3>3️⃣ Contacts</h3>
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
      <label style="margin:0;display:flex;align-items:center;gap:6px"><input type="checkbox" id="sel-all" onchange="toggleAll()" style="width:16px;height:16px;margin:0"> Select All</label>
      <span id="sel-cnt" style="font-size:11px;color:var(--green);font-weight:700">0 selected</span>
    </div>
    <div id="bulk-list" style="max-height:250px;overflow-y:auto"></div>
  </div>
  <div class="card"><h3>4️⃣ Send</h3>
    <button class="btn btn-blue btn-block" onclick="genBulk()">🤖 AI Generate Messages</button>
    <div id="bulk-preview"></div>
  </div>
</div>

<!-- FOLLOW-UP -->
<div class="page" id="page-follow">
  <div class="card" style="background:rgba(0,184,148,.08);border-color:rgba(0,184,148,.2)">
    <h3>📱 Auto Follow-ups</h3>
    <p style="font-size:11px;color:var(--muted)">Based on inquiry age — tap to send via WhatsApp</p>
  </div>
  <div id="follow-list"></div>
</div>

</div><!-- .app -->

<!-- DETAIL SHEET -->
<div class="sheet" id="detail-sheet">
  <div class="sheet-bg" onclick="closeSheet()"></div>
  <div class="sheet-content" id="detail-body"></div>
</div>

<!-- ADD SHEET -->
<div class="sheet" id="add-sheet">
  <div class="sheet-bg" onclick="closeAddSheet()"></div>
  <div class="sheet-content">
    <div class="sheet-handle"></div>
    <h3 style="margin-bottom:16px">➕ New Inquiry</h3>
    <label>Name</label><input id="a-name" placeholder="Customer name">
    <label>Phone</label><input id="a-phone" type="tel" placeholder="+91XXXXXXXXXX">
    <label>Product</label><input id="a-prod" placeholder="e.g., Tea Vending Machine">
    <label>Category</label>
    <select id="a-cat"><option>Vending Machines</option><option>Tea/Coffee Premix</option><option>Jaggery Products</option><option>Nescafe Premix</option><option>Bru Premix</option><option>Society Premix</option><option>Other</option></select>
    <label>Location</label><input id="a-loc" placeholder="City">
    <label>Notes</label><textarea id="a-notes" placeholder="Requirements..."></textarea>
    <div style="display:flex;gap:8px;margin-top:8px">
      <button class="btn btn-outline" style="flex:1" onclick="closeAddSheet()">Cancel</button>
      <button class="btn btn-green" style="flex:1" onclick="saveNew()">Save</button>
    </div>
  </div>
</div>

<!-- SETTINGS PANEL -->
<div class="sheet" id="settings-sheet">
  <div class="sheet-bg" onclick="closeSettingsSheet()"></div>
  <div class="sheet-content">
    <div class="sheet-handle"></div>
    <h3 style="margin-bottom:16px">⚙️ Settings</h3>

    <div class="card" style="background:rgba(0,184,148,.08);border-color:rgba(0,184,148,.2);margin-bottom:16px">
      <h3>📬 Fetch Indiamart Emails</h3>
      <p style="font-size:11px;color:var(--muted);margin-bottom:10px">Pull latest inquiries from Gmail into the app</p>
      <button class="btn btn-green btn-block" id="extract-btn" onclick="startExtract()">🔄 Fetch Emails from Gmail</button>
      <div id="extract-status" style="font-size:11px;margin-top:8px;color:var(--muted);min-height:16px"></div>
    </div>

    <label>Gemini API Key</label>
    <input id="g-key" type="password" placeholder="AIza..." style="font-size:12px">
    <div style="display:flex;gap:6px">
      <button class="btn btn-blue btn-sm" style="flex:1" onclick="saveKey()">Save Key</button>
      <button class="btn btn-outline btn-sm" style="flex:1" onclick="testKey()">Test</button>
    </div>
    <div id="key-status" style="font-size:10px;margin-top:8px;color:var(--muted)"></div>
    <div style="font-size:9px;color:var(--muted);margin-top:12px">Get free key: <a href="https://aistudio.google.com/apikey" target="_blank" style="color:var(--blue)">aistudio.google.com</a></div>
    <hr style="border:none;border-top:1px solid var(--border);margin:16px 0">
    <div style="font-size:11px;color:var(--muted);text-align:center">Arihant CRM v1.0 • Pune</div>
  </div>
</div>

<!-- TOAST -->
<div class="toast" id="toast"></div>

<!-- FAB -->
<button class="fab" onclick="openAddSheet()">+</button>

<!-- INSTALL BANNER -->
<div class="install-banner" id="install-banner">
  <div class="row">
    <div class="ico">📱</div>
    <div class="txt"><div class="t">Install Arihant CRM</div><div class="s">Add to home screen</div></div>
    <button class="btn btn-sm" style="background:#fff;color:var(--primary)" onclick="doInstall()">Install</button>
    <span onclick="el('install-banner').style.display='none'" style="cursor:pointer;font-size:18px;opacity:.6">×</span>
  </div>
</div>

<!-- BOTTOM NAV -->
<div class="bottom-nav">
  <div class="nav active" data-page="home" onclick="go('home')">
    <svg viewBox="0 0 24 24" fill="currentColor"><path d="M10 20v-6h4v6h5v-8h3L12 3 2 12h3v8z"/></svg>Home
  </div>
  <div class="nav" data-page="inquiries" onclick="go('inquiries')">
    <svg viewBox="0 0 24 24" fill="currentColor"><path d="M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm-5 14H7v-2h7v2zm3-4H7v-2h10v2zm0-4H7V7h10v2z"/></svg>Inquiries
  </div>
  <div class="nav" data-page="bulk" onclick="go('bulk')">
    <svg viewBox="0 0 24 24" fill="currentColor"><path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347z"/><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2z"/></svg>Bulk
  </div>
  <div class="nav" data-page="follow" onclick="go('follow')">
    <svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/></svg>Follow-up
  </div>
</div>

<script>
const C=['#6c5ce7','#00b894','#e17055','#0984e3','#fdcb6e','#d63031','#00cec9','#e84393','#2d3436'];
function av(n){return C[(n||'A').charCodeAt(0)%C.length]}
function el(id){return document.getElementById(id)}
function deb(fn,ms){let t;return(...a)=>{clearTimeout(t);t=setTimeout(()=>fn(...a),ms)}}
function toast(m){const t=el('toast');t.textContent=m;t.classList.add('show');setTimeout(()=>t.classList.remove('show'),2000)}
async function api(p,o={}){return(await fetch('/api'+p,{headers:{'Content-Type':'application/json'},...o,body:o.body?JSON.stringify(o.body):undefined})).json()}
function fmtDate(d){if(!d)return'';try{const dt=new Date(d),now=new Date(),diff=Math.floor((now-dt)/864e5);if(diff===0)return'Today';if(diff===1)return'Yesterday';if(diff<7)return diff+'d ago';return dt.toLocaleDateString('en-IN',{day:'numeric',month:'short'})}catch{return d.slice(0,10)}}
function badge(s){return`<span class="badge badge-${s}">${s}</span>`}
function cats(c){if(!c)return'';try{c=JSON.parse(c)}catch{c=[c]}return c.map(x=>`<span class="cat">${x}</span>`).join('')}

// Nav
let curPage='home';
function go(p){
  curPage=p;
  document.querySelectorAll('.page').forEach(x=>x.classList.toggle('active',x.id==='page-'+p));
  document.querySelectorAll('.tab').forEach(x=>x.classList.toggle('active',x.dataset.page===p));
  document.querySelectorAll('.nav').forEach(x=>x.classList.toggle('active',x.dataset.page===p));
  if(p==='inquiries')loadInq();
  if(p==='bulk')loadBulk();
  if(p==='follow')loadFollow();
  if(p==='home')loadHome();
}

// Home
async function loadHome(){
  const s=await api('/stats');
  el('cnt-total').textContent=s.total;
  el('stats').innerHTML=`
    <div class="stat"><div class="n">${s.total}</div><div class="l">Total</div></div>
    <div class="stat g"><div class="n">${s.new}</div><div class="l">New</div></div>
    <div class="stat o"><div class="n">${s.contacted}</div><div class="l">Contacted</div></div>
    <div class="stat b"><div class="n">${s.phone}</div><div class="l">Has Phone</div></div>
    <div class="stat r"><div class="n">${s.no_phone}</div><div class="l">No Phone</div></div>
    <div class="stat"><div class="n">${s.closed}</div><div class="l">Closed</div></div>
  `;
  const cats=s.cats||{};
  el('cat-list').innerHTML=Object.entries(cats).sort((a,b)=>b[1]-a[1]).map(([c,n])=>
    `<div style="display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid var(--border)"><span class="cat">${c}</span><strong style="font-size:13px">${n}</strong></div>`
  ).join('');
  el('recent').innerHTML=(s.recent||[]).map(inqRow).join('')||'<div class="empty"><div class="ico">📭</div><div class="t">No inquiries yet</div></div>';
}

// Inquiries
async function loadInq(){
  const p=new URLSearchParams();
  const q=el('s-q').value,st=el('s-st').value,ph=el('s-ph').value,cat=el('s-cat').value;
  if(q)p.set('q',q);if(st)p.set('status',st);if(ph)p.set('has_phone',ph);if(cat)p.set('cat',cat);
  const inqs=await api('/inquiries?'+p);
  el('cnt-total').textContent=inqs.length;
  el('inq-list').innerHTML=inqs.length?inqs.map(inqRow).join(''):'<div class="empty"><div class="ico">🔍</div><div class="t">No inquiries found</div></div>';
}
function inqRow(i){
  const n=i.customer_name||'Unknown';
  return`<div class="list-item" onclick="showDetail('${i.id}')">
    <div class="avatar" style="background:${av(n)}">${n[0]}</div>
    <div class="info"><div class="name">${n}</div><div class="prod">${(i.product_interest||'').slice(0,50)}</div>${cats(i.categories)}</div>
    <div class="meta"><div class="date">${fmtDate(i.inquiry_date)}</div>${badge(i.status)}</div>
  </div>`;
}

// Detail
async function showDetail(id){
  const i=await api('/inquiries/'+id);if(!i)return;
  const ph=i.phone||'';
  const wa=ph?`https://wa.me/${ph.replace(/[^0-9]/g,'')}?text=${encodeURIComponent('Hi '+(i.customer_name||'')+' 👋')}`:'';
  el('detail-body').innerHTML=`
    <div class="sheet-handle"></div>
    <div style="display:flex;align-items:center;gap:12px;margin-bottom:16px">
      <div class="avatar" style="background:${av(i.customer_name)};width:48px;height:48px;font-size:20px;border-radius:14px">${(i.customer_name||'?')[0]}</div>
      <div><div style="font-size:16px;font-weight:800">${i.customer_name||'Unknown'}</div><div style="font-size:12px;color:var(--muted)">${(i.product_interest||'').slice(0,50)}</div></div>
    </div>
    <div class="field"><label>📞 Phone</label><div class="val">${ph||'<span style="color:var(--red)">Not available</span>'}</div></div>
    <div class="field"><label>📧 Email</label><div class="val">${i.email||'N/A'}</div></div>
    <div class="field"><label>📍 Location</label><div class="val">${i.location||'N/A'}</div></div>
    <div class="field"><label>🏷️ Category</label><div class="val">${cats(i.categories)}</div></div>
    <div class="field"><label>📋 Notes</label><div class="val" style="font-size:12px">${(i.requirement||'N/A').slice(0,200)}</div></div>
    <div class="field"><label>📅 Date</label><div class="val">${i.inquiry_date||'N/A'}</div></div>
    <div class="field"><label>🔄 Status</label>
      <select onchange="updStatus('${i.id}',this.value)" style="margin-bottom:0">
        <option value="new" ${i.status==='new'?'selected':''}>New</option>
        <option value="contacted" ${i.status==='contacted'?'selected':''}>Contacted</option>
        <option value="closed" ${i.status==='closed'?'selected':''}>Closed</option>
      </select>
    </div>
    <div class="field"><label>📱 Update Phone</label>
      <div style="display:flex;gap:6px"><input id="ed-ph" value="${ph}" placeholder="+91XXXXXXXXXX" style="margin-bottom:0"><button class="btn btn-blue btn-sm" onclick="updPh('${i.id}')">Save</button></div>
    </div>
    ${wa?`<a class="wa-btn" href="${wa}" target="_blank">💬 Open WhatsApp</a>`:''}
    <div style="display:flex;gap:6px;margin-top:12px;flex-wrap:wrap">
      <button class="btn btn-outline btn-sm" style="flex:1" onclick="genMsg('${i.id}','thank_you')">👋 Thank You</button>
      <button class="btn btn-outline btn-sm" style="flex:1" onclick="genMsg('${i.id}','offer')">🎯 Offer</button>
      <button class="btn btn-outline btn-sm" style="flex:1" onclick="genMsg('${i.id}','reengagement')">🔄 Follow-up</button>
    </div>
    <button class="btn btn-blue btn-sm btn-block" style="margin-top:8px" onclick="researchGen('${i.id}')">🔍 Research & Generate</button>
    <div id="biz-${i.id}"></div>
    <div id="msg-${i.id}"></div>
    <button class="btn btn-red btn-sm btn-block" style="margin-top:12px" onclick="delInq('${i.id}')">🗑️ Delete</button>
  `;
  el('detail-sheet').classList.add('show');
}
function closeSheet(){el('detail-sheet').classList.remove('show')}
function closeAddSheet(){el('add-sheet').classList.remove('show')}
function openAddSheet(){el('add-sheet').classList.add('show')}
function closeSettingsSheet(){el('settings-sheet').classList.remove('show')}
function togglePanel(p){el(p+'-sheet').classList.add('show')}

async function updStatus(id,s){await api('/inquiries/'+id,{method:'PUT',body:{status:s}});toast('Updated');loadInq();loadHome()}
async function updPh(id){await api('/inquiries/'+id,{method:'PUT',body:{phone:el('ed-ph').value}});toast('Saved');showDetail(id)}
async function delInq(id){if(!confirm('Delete?'))return;await api('/inquiries/'+id,{method:'DELETE'});closeSheet();toast('Deleted');loadInq();loadHome()}

// AI Messages
const TPLS={"Vending Machines":{thank_you:["Hi {name} 👋\\n\\nThank you for your interest in {product}! We\\'re {company} — a leading manufacturer & exporter from {location}.\\n\\n🏭 What we offer:\\n• Tea/Coffee vending machines (2-8 lane)\\n• Free site visit & demo\\n• Installation + 1-year warranty\\n• AMC packages\\n\\n📞 {phone}\\n— {company}"],offer:["Hi {name} 👋\\n\\n🎯 Direct-from-manufacturer offer:\\n• ₹5,000 OFF first order\\n• FREE installation\\n• 1-year warranty\\n• Free 100 cups premix test\\n\\n📞 {phone}\\n— {company}"],reengagement:["Hi {name},\\n\\nStill looking for {product}?\\n\\n💡 Book now: 6 months FREE maintenance.\\n📞 {phone}\\n— {company}"]},"Tea/Coffee Premix":{thank_you:["Hi {name} 👋\\n\\nThanks for your interest in our premix! We\\'re {company} — manufacturer & exporter from {location}.\\n\\n☕ Our Range:\\n• Tea Premix (Regular/Masala/Kadak)\\n• Coffee Premix (Strong/Mild)\\n\\n📦 500g, 1kg, 5kg packs\\n📞 {phone}\\n— {company}"],offer:["Hi {name} 👋\\n\\n🎯 Bulk Premix Deal:\\n• 10% OFF on 10kg+\\n• FREE 3-flavor sample pack\\n• Free delivery first order\\n\\nReply \\"SAMPLE\\"!\\n📞 {phone}\\n— {company}"],reengagement:["Hi {name},\\n\\nStill looking for premix? Our Kadak Chai is a hit! ☕\\n📞 {phone}\\n— {company}"]},"Jaggery Products":{thank_you:["Hi {name} 👋\\n\\nThank you! We\\'re {company} — organic jaggery manufacturer from {location}.\\n\\n🍯 Products:\\n• Jaggery Powder/Blocks/Syrup\\n• 100% organic, FSSAI certified\\n• Export quality\\n\\n📞 {phone}\\n— {company}"],offer:["Hi {name} 👋\\n\\n🎯 Jaggery Bulk Offer:\\n• 15% OFF on 50kg+\\n• FREE sample kit\\n• Private labeling available\\n\\n📞 {phone}\\n— {company}"],reengagement:["Hi {name},\\n\\nFresh harvest stock at lowest prices!\\n📞 {phone}\\n— {company}"]},"Nescafe Premix":{thank_you:["Hi {name} 👋\\n\\nThanks! We\\'re authorized Nescafé distributor. {company} from {location}.\\n\\n☕ Nescafé Range:\\n• Classic, Latte, Cappuccino\\n• Genuine Nestlé products\\n\\n📞 {phone}\\n— {company}"],offer:["Hi {name} 👋\\n\\n🎯 Nescafé Deal:\\n• Buy 5kg get 1kg FREE\\n• Free machine on 50kg+\\n\\n📞 {phone}\\n— {company}"],reengagement:["Hi {name},\\n\\nFresh Nescafé stock at special prices!\\n📞 {phone}\\n— {company}"]},"Bru Premix":{thank_you:["Hi {name} 👋\\n\\nThanks! We supply Bru coffee premix in bulk. {company}, {location}.\\n\\n📞 {phone}\\n— {company}"],offer:["Hi {name} 👋\\n\\n🎯 Bru Bulk: 12% OFF on 25kg+. Free sample!\\n📞 {phone}\\n— {company}"],reengagement:["Hi {name},\\n\\nAuto-supply plan: 10% discount + free monthly delivery.\\n📞 {phone}\\n— {company}"]},"Society Premix":{thank_you:["Hi {name} 👋\\n\\nWe specialize in society premix solutions. {company}, {location}.\\n\\n📞 {phone}\\n— {company}"],offer:["Hi {name} 👋\\n\\n🎯 Society Combo: FREE machine install + wholesale premix rates.\\n📞 {phone}\\n— {company}"],reengagement:["Hi {name},\\n\\nFirst 10kg premix FREE with machine order!\\n📞 {phone}\\n— {company}"]},"Other":{thank_you:["Hi {name} 👋\\n\\nThank you for reaching out about {product}! We\\'re {company} — manufacturer & exporter from {location}.\\n\\n🏭 500+ clients • Free demo • Best prices\\n\\n📞 {phone}\\n— {company}"],offer:["Hi {name} 👋\\n\\n🎯 Direct-from-manufacturer pricing. 10% early-bird discount!\\n📞 {phone}\\n— {company}"],reengagement:["Hi {name},\\n\\nStill interested in {product}? We\\'re here to help.\\n📞 {phone}\\n— {company}"]}};

function aiGen(cat,tpl,name,prod){
  const c=TPLS[cat]||TPLS.Other;const t=c[tpl]||c.thank_you;
  return t[Math.floor(Math.random()*t.length)].replace(/{name}/g,name).replace(/{product}/g,prod).replace(/{phone}/g,'+917020134619').replace(/{company}/g,'Arihant Enterprises').replace(/{location}/g,'Pune');
}

async function aiGenGemini(cat,tpl,name,prod){
  const key=getKey();if(!key)return aiGen(cat,tpl,name,prod);
  const labels={thank_you:'a warm thank-you',offer:'a special offer',reengagement:'a re-engagement follow-up'};
  const prompt=`You are WhatsApp writer for Arihant Enterprises (${PHONE}), manufacturer & exporter from Pune. Write ${labels[tpl]||'a message'} for customer "${name}" interested in "${prod}" (${cat}). Under 100 words. Use emojis. Include call-to-action. End with: — Arihant Enterprises. Just return message text.`;
  try{const r=await fetch('/api/gemini',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({key,prompt})});const d=await r.json();if(d.result&&!d.result.includes('Error'))return d.result}catch(e){}
  return aiGen(cat,tpl,name,prod);
}

async function genMsg(id,tpl){
  const i=await api('/inquiries/'+id);
  el('msg-'+id).innerHTML='<div style="text-align:center;padding:10px;color:var(--muted)">🤖 Generating...</div>';
  const msg=await aiGenGemini((i._cats||['Other'])[0],tpl,i.customer_name||'there',(i.product_interest||'').slice(0,60));
  const ph=(i.phone||'').replace(/[^0-9]/g,'');
  const wa=ph?`https://wa.me/${ph}?text=${encodeURIComponent(msg)}`:'';
  el('msg-'+id).innerHTML=`<div class="msg-box">${msg}</div>${wa?`<a class="wa-btn" href="${wa}" target="_blank">💬 Send WhatsApp</a>`:'<div style="color:var(--red);font-size:12px">⚠️ No phone</div>'}`;
}

async function researchGen(id){
  const i=await api('/inquiries/'+id);const key=getKey();
  if(!key){toast('Add Gemini key in Settings ⚙️');return}
  const q=`${i.customer_name||''} ${i.location||''} ${(i.product_interest||'').slice(0,40)} business`;
  el('biz-'+id).innerHTML=`<div class="card" style="background:var(--card2);padding:12px;margin:8px 0">
    <strong style="font-size:12px">🔍 Research</strong>
    <div style="display:flex;gap:4px;flex-wrap:wrap;margin:8px 0">
      <a href="https://www.google.com/search?q=${encodeURIComponent(q)}" target="_blank" class="btn btn-outline btn-sm" style="font-size:10px;text-decoration:none">🌐 Google</a>
      <a href="https://www.google.com/search?q=${encodeURIComponent(i.customer_name+' linkedin')}" target="_blank" class="btn btn-outline btn-sm" style="font-size:10px;text-decoration:none">💼 LinkedIn</a>
      <a href="https://www.google.com/search?q=${encodeURIComponent(i.customer_name+' indiamart')}" target="_blank" class="btn btn-outline btn-sm" style="font-size:10px;text-decoration:none">🏪 IndiaMART</a>
    </div>
    <label style="font-size:10px">Paste business info:</label>
    <textarea id="ctx-${id}" placeholder="e.g., Office in Andheri, 50 staff, uses competitor machine..." style="font-size:11px;min-height:40px"></textarea>
    <button class="btn btn-blue btn-sm btn-block" onclick="genWithContext('${id}')">🤖 Generate with Context</button>
  </div>`;
}

async function genWithContext(id){
  const i=await api('/inquiries/'+id);const key=getKey();const ctx=el('ctx-'+id).value;
  if(!ctx.trim()){toast('Paste business info first!');return}
  el('msg-'+id).innerHTML='<div style="text-align:center;padding:10px;color:var(--muted)">🤖 Generating personalized...</div>';
  const prompt=`WhatsApp writer for Arihant Enterprises (manufacturer/exporter, Pune). Customer: ${i.customer_name||'N/A'}, interested in: ${(i.product_interest||'').slice(0,60)}, category: ${(i._cats||['Other'])[0]}. Business research: ${ctx}. Write personalized follow-up under 100 words. Use emojis. CTA. End: — Arihant Enterprises.`;
  try{const r=await fetch('/api/gemini',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({key,prompt})});const d=await r.json();
    if(d.result&&!d.result.includes('Error')){
      const ph=(i.phone||'').replace(/[^0-9]/g,'');const wa=ph?`https://wa.me/${ph}?text=${encodeURIComponent(d.result)}`:'';
      el('msg-'+id).innerHTML=`<div style="font-size:10px;color:var(--green);margin:4px 0">✨ AI + business context</div><div class="msg-box">${d.result}</div>${wa?`<a class="wa-btn" href="${wa}" target="_blank">💬 Send WhatsApp</a>`:''}`;
    }else{el('msg-'+id).innerHTML='<div style="color:var(--red);font-size:12px">❌ Failed</div>'}
  }catch(e){el('msg-'+id).innerHTML='<div style="color:var(--red);font-size:12px">❌ '+e.message+'</div>'}
}

// Bulk
let bulkCat='',bulkTpl='thank_you',bulkSel=new Set(),bulkInqs=[];
async function loadBulk(){
  bulkInqs=await api('/inquiries?ph=yes');
  const cats={};
  bulkInqs.forEach(i=>{(i._cats||['Other']).forEach(c=>{if(!cats[c])cats[c]=[];cats[c].push(i)})});
  const allCats=Object.keys(cats).sort((a,b)=>cats[b].length-cats[a].length);
  el('bulk-cats').innerHTML=allCats.map(c=>`<span class="pill ${c===bulkCat?'active':''}" onclick="selBulkCat('${c}',this)">${c} (${cats[c].length})</span>`).join('')+`<span class="pill ${bulkCat===''?'active':''}" onclick="selBulkCat('',this)">All (${bulkInqs.length})</span>`;
  const filtered=bulkCat?(cats[bulkCat]||[]):bulkInqs;
  bulkSel.clear();el('sel-all').checked=false;el('sel-cnt').textContent='0 selected';
  el('bulk-list').innerHTML=filtered.map(i=>`
    <div class="check-row"><input type="checkbox" data-id="${i.id}" onchange="updSel()">
    <div class="avatar" style="background:${av(i.customer_name)};width:30px;height:30px;font-size:11px;border-radius:10px">${(i.customer_name||'?')[0]}</div>
    <div style="flex:1;min-width:0"><div style="font-size:12px;font-weight:600">${i.customer_name||'?'}</div><div style="font-size:10px;color:var(--muted)">${i.phone||''}</div></div>${cats(i.categories)}</div>
  `).join('')||'<div class="empty"><div class="ico">📱</div><div class="t">No contacts with phone</div></div>';
}
function selBulkCat(c,el2){bulkCat=c;document.querySelectorAll('#bulk-cats .pill').forEach(p=>p.classList.remove('active'));el2.classList.add('active');loadBulk()}
function selTpl(el2){document.querySelectorAll('[data-t]').forEach(p=>p.classList.remove('active'));el2.classList.add('active');bulkTpl=el2.dataset.t}
function toggleAll(){const ch=el('sel-all').checked;document.querySelectorAll('#bulk-list input[type=checkbox]').forEach(c=>c.checked=ch);updSel()}
function updSel(){bulkSel.clear();document.querySelectorAll('#bulk-list input[type=checkbox]:checked').forEach(c=>bulkSel.add(c.dataset.id));el('sel-cnt').textContent=bulkSel.size+' selected'}

async function genBulk(){
  if(!bulkSel.size){toast('Select contacts first!');return}
  const inqs=bulkInqs.filter(i=>bulkSel.has(i.id));
  el('bulk-preview').innerHTML='<div style="text-align:center;padding:16px;color:var(--muted)">🤖 Generating '+inqs.length+' messages...</div>';
  const msgs=[];
  for(const i of inqs){
    const msg=await aiGenGemini((i._cats||['Other'])[0],bulkTpl,i.customer_name||'there',(i.product_interest||'').slice(0,60));
    const ph=(i.phone||'').replace(/[^0-9]/g,'');
    msgs.push({id:i.id,name:i.customer_name,phone:i.phone,msg,wa:ph?`https://wa.me/${ph}?text=${encodeURIComponent(msg)}`:''});
  }
  el('bulk-preview').innerHTML=`
    <div style="padding:12px;text-align:center"><strong>📨 ${msgs.length} messages ready</strong></div>
    <button class="btn btn-green btn-block" onclick="openAll()" style="margin-bottom:8px">📱 Open All WhatsApp (${msgs.length})</button>
    <button class="btn btn-outline btn-block" onclick="markAll()" style="margin-bottom:8px">✅ Mark All Sent</button>
    ${msgs.map(m=>`<div class="card" style="padding:10px">
      <div style="display:flex;justify-content:space-between"><strong style="font-size:12px">${m.name}</strong><span style="font-size:10px;color:var(--muted)">${m.phone||''}</span></div>
      <div class="msg-box" style="font-size:11px">${m.msg}</div>
      <div style="display:flex;gap:6px">${m.wa?`<a class="btn btn-green btn-sm" href="${m.wa}" target="_blank" style="flex:1;text-decoration:none;text-align:center">💬 Send</a>`:''}<button class="btn btn-outline btn-sm" onclick="navigator.clipboard.writeText(${JSON.stringify(m.msg)});toast('Copied!')">📋</button></div>
    </div>`).join('')}
  `;
  window._msgs=msgs;
}
function openAll(){const m=window._msgs||[];let i=0;function n(){if(i>=m.length)return;window.open(m[i].wa,'_blank');i++;setTimeout(n,2000)}n()}
async function markAll(){await api('/bulk-status',{method:'POST',body:{ids:Array.from(bulkSel),status:'contacted'}});toast('Marked sent!');loadBulk();loadHome()}

// Follow-ups
async function loadFollow(){
  const fs=await api('/followups');
  el('follow-list').innerHTML=fs.length?fs.map(f=>`<div class="card">
    <div style="display:flex;justify-content:space-between"><strong>${f.inquiry.customer_name}</strong><span style="font-size:10px;color:var(--muted)">${f.days_since}d</span></div>
    <div style="font-size:11px;color:var(--muted);margin:4px 0">${(f.inquiry.product_interest||'').slice(0,40)}</div>
    <span class="cat">${f.template_label}</span>
    <div class="msg-box" style="font-size:11px;margin:6px 0">${f.message.slice(0,150)}...</div>
    <div style="display:flex;gap:6px">
      <a class="btn btn-green btn-sm" href="${f.wa_link}" target="_blank" style="flex:1;text-decoration:none;text-align:center">💬 Send</a>
      <button class="btn btn-outline btn-sm" onclick="markFollow('${f.inquiry.id}','${f.template}')">✓ Sent</button>
    </div>
  </div>`).join(''):'<div class="empty"><div class="ico">📱</div><div class="t">No follow-ups due</div><div class="s">Add phone numbers to contacts first</div></div>';
}
async function markFollow(id,t){await api('/followups/mark',{method:'POST',body:{id,template:t}});toast('Done');loadFollow();loadHome()}

// Settings
function getKey(){return localStorage.getItem('gkey')||''}
function saveKey(){const k=el('g-key').value.trim();if(k){localStorage.setItem('gkey',k);el('key-status').textContent='✅ Saved';el('key-status').style.color='var(--green)'}else{localStorage.removeItem('gkey');el('key-status').textContent='Removed'}}
async function testKey(){const k=getKey();if(!k){el('key-status').textContent='❌ Enter key';return}el('key-status').textContent='⏳ Testing...';try{const r=await fetch('/api/gemini',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({key:k,prompt:'Say hi in 5 words'})});const d=await r.json();el('key-status').textContent=d.result&&!d.result.includes('Error')?'✅ Connected!':'❌ Failed';el('key-status').style.color=d.result&&!d.result.includes('Error')?'var(--green)':'var(--red)'}catch(e){el('key-status').textContent='❌ Error';el('key-status').style.color='var(--red)'}}
document.addEventListener('DOMContentLoaded',()=>{const k=getKey();if(k)el('g-key').value=k});

// Email Extraction
let extractPolling = null;
async function startExtract(){
  const btn=el('extract-btn');
  const st=el('extract-status');
  btn.disabled=true;btn.textContent='⏳ Starting...';btn.style.opacity='.6';
  try{
    const r=await api('/extract',{method:'POST'});
    st.textContent=r.status||'Starting...';
    extractPolling=setInterval(async()=>{
      try{
        const s=await api('/extract/status');
        st.textContent=s.progress||'Running...';
        if(!s.running){
          clearInterval(extractPolling);extractPolling=null;
          btn.disabled=false;btn.textContent='🔄 Fetch Emails from Gmail';btn.style.opacity='1';
          st.textContent=s.progress||'Done!';
          toast('Emails fetched! '+s.count+' new');
          loadHome();
        }
      }catch(e){}
    },2000);
  }catch(e){
    btn.disabled=false;btn.textContent='🔄 Fetch Emails from Gmail';btn.style.opacity='1';
    st.textContent='❌ Error: '+e.message;
  }
}
async function startExtractHome(){
  const btn=el('home-extract-btn');
  const st=el('home-extract-status');
  btn.disabled=true;btn.textContent='⏳ Fetching...';btn.style.opacity='.6';
  try{
    const r=await api('/extract',{method:'POST'});
    st.textContent=r.status||'Starting...';
    extractPolling=setInterval(async()=>{
      try{
        const s=await api('/extract/status');
        st.textContent=s.progress||'Running...';
        if(!s.running){
          clearInterval(extractPolling);extractPolling=null;
          btn.disabled=false;btn.textContent='🔄 Fetch from Gmail';btn.style.opacity='1';
          st.textContent=s.progress||'Done!';
          toast('✅ '+s.count+' emails fetched!');
          loadHome();
        }
      }catch(e){}
    },2000);
  }catch(e){
    btn.disabled=false;btn.textContent='🔄 Fetch from Gmail';btn.style.opacity='1';
    st.textContent='❌ Error: '+e.message;
  }
}

// Add
async function saveNew(){
  const d={customer_name:el('a-name').value||'Unknown',phone:el('a-phone').value,product_interest:el('a-prod').value,category:el('a-cat').value,location:el('a-loc').value,requirement:el('a-notes').value};
  await api('/inquiries',{method:'POST',body:d});closeAddSheet();toast('Added!');loadInq();loadHome();
  ['a-name','a-phone','a-prod','a-loc','a-notes'].forEach(id=>el(id).value='');
}

// PWA Install
let deferredPrompt;
window.addEventListener('beforeinstallprompt',e=>{e.preventDefault();deferredPrompt=e;el('install-banner').style.display='block'});
function doInstall(){if(deferredPrompt){deferredPrompt.prompt();deferredPrompt.userChoice.then(r=>{if(r.outcome==='accepted')toast('Installed!');el('install-banner').style.display='none';deferredPrompt=null})}}
window.addEventListener('appinstalled',()=>{el('install-banner').style.display='none'});

// Init
loadHome();
</script>
</body>
</html>'''

# ── Handler ──────────────────────────────────────────────────────────────────

class H(BaseHTTPRequestHandler):
    def log_message(self,*a):pass
    def send_json(self,d,s=200):
        self.send_response(s);self.send_header('Content-Type','application/json');self.send_header('Access-Control-Allow-Origin','*');self.end_headers()
        self.wfile.write(json.dumps(d,default=str).encode())
    def send_html(self,h):
        self.send_response(200);self.send_header('Content-Type','text/html;charset=utf-8');self.end_headers()
        self.wfile.write(h.encode())
    def do_OPTIONS(self):
        self.send_response(200);self.send_header('Access-Control-Allow-Origin','*');self.send_header('Access-Control-Allow-Methods','GET,POST,PUT,DELETE,OPTIONS');self.send_header('Access-Control-Allow-Headers','Content-Type');self.end_headers()
    def body(self):
        l=int(self.headers.get('Content-Length',0));return json.loads(self.rfile.read(l)) if l else {}
    def do_GET(self):
        p=urlparse(self.path).path;q=parse_qs(urlparse(self.path).query)
        if p in('/','/index.html'):self.send_html(html())
        elif p=='/manifest.json':
            self.send_response(200);self.send_header('Content-Type','application/manifest+json');self.end_headers()
            self.wfile.write(json.dumps({"name":"Arihant CRM","short_name":"Arihant","start_url":"/","display":"standalone","background_color":"#0a0e27","theme_color":"#0a0e27","orientation":"portrait","icons":[{"src":"/icon.svg","sizes":"any","type":"image/svg+xml"}]}).encode())
        elif p=='/icon.svg':
            self.send_response(200);self.send_header('Content-Type','image/svg+xml');self.end_headers()
            self.wfile.write(b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512"><rect width="512" height="512" rx="96" fill="#0a0e27"/><text x="256" y="300" font-size="200" text-anchor="middle" fill="#6c5ce7">A</text><text x="256" y="420" font-size="60" text-anchor="middle" fill="#00b894">CRM</text></svg>')
        elif p=='/sw.js':
            self.send_response(200);self.send_header('Content-Type','application/javascript');self.end_headers()
            self.wfile.write(b"const C='v3';self.addEventListener('install',e=>{e.waitUntil(caches.open(C).then(c=>c.addAll(['/','/manifest.json','/icon.svg'])).then(()=>self.skipWaiting()))});self.addEventListener('activate',e=>{e.waitUntil(caches.keys().then(k=>Promise.all(k.filter(x=>x!==C).map(x=>caches.delete(x)))).then(()=>self.clients.claim()))});self.addEventListener('fetch',e=>{if(e.request.url.includes('/api/'))return;e.respondWith(caches.match(e.request).then(r=>r||fetch(e.request).then(resp=>{if(resp.status===200){const c=resp.clone();caches.open(C).then(cache=>cache.put(e.request,c))}return resp}).catch(()=>caches.match('/'))))});")
        elif p=='/api/stats':self.send_json(get_stats())
        elif p=='/api/inquiries':f={k:v[0] for k,v in q.items() if v};self.send_json(get_inquiries(f))
        elif p.startswith('/api/inquiries/'):self.send_json(get_one(p.split('/')[-1]))
        elif p=='/api/followups':self.send_json(get_due_follow_ups())
        elif p=='/api/export':
            self.send_response(200);self.send_header('Content-Type','text/csv');self.send_header('Content-Disposition','attachment;filename=inquiries.csv');self.end_headers()
            self.wfile.write(export_csv().encode())
        elif p=='/download' or p=='/download.apk' or p=='/arihant-crm.apk':
            apk_path = Path(__file__).parent / "arihant-crm.apk"
            if apk_path.exists():
                self.send_response(200)
                self.send_header('Content-Type','application/vnd.android.package-archive')
                self.send_header('Content-Disposition','attachment; filename="Arihant-CRM.apk"')
                self.send_header('Content-Length', str(apk_path.stat().st_size))
                self.end_headers()
                with open(apk_path, 'rb') as f:
                    self.wfile.write(f.read())
            else:
                self.send_response(404);self.end_headers()
                self.wfile.write(b"APK not found")
        elif p=='/install':
            self.send_html(install_page())
        else:self.send_response(404);self.end_headers()
    def do_POST(self):
        p=urlparse(self.path).path;b=self.body()
        if p=='/api/inquiries':self.send_json({"id":add_inq(b),"ok":True})
        elif p=='/api/followups/mark':mark_follow_up(b.get('id'),b.get('template'));self.send_json({"ok":True})
        elif p=='/api/bulk-status':bulk_status(b.get('ids',[]),b.get('status','contacted'));self.send_json({"ok":True})
        elif p=='/api/gemini':
            k=b.get('key','');pr=b.get('prompt','')
            if not k or not pr:self.send_json({"error":"Missing"},400)
            else:self.send_json({"result":gemini(k,pr)})
        elif p=='/api/extract':
            if _extract_status["running"]:
                self.send_json({"ok":True,"running":True,"status":_extract_status["progress"]})
            else:
                t = threading.Thread(target=run_extraction, daemon=True)
                t.start()
                self.send_json({"ok":True,"running":True,"status":"Starting extraction..."})
        elif p=='/api/extract/status':
            self.send_json(_extract_status)
        else:self.send_response(404);self.end_headers()
    def do_PUT(self):
        p=urlparse(self.path).path;b=self.body()
        if p.startswith('/api/inquiries/'):update(p.split('/')[-1],b);self.send_json({"ok":True})
        else:self.send_response(404);self.end_headers()
    def do_DELETE(self):
        p=urlparse(self.path).path
        if p.startswith('/api/inquiries/'):delete(p.split('/')[-1]);self.send_json({"ok":True})
        else:self.send_response(404);self.end_headers()

def get_due_follow_ups():
    c=db();inqs=rows(c.execute("SELECT * FROM inquiries WHERE status!='closed' AND phone IS NOT NULL AND phone!='' ORDER BY inquiry_date ASC").fetchall());c.close()
    today=datetime.now().date();due=[];sched=[{"day":0,"label":"Thank You","key":"thank_you"},{"day":2,"label":"Offer","key":"offer"},{"day":10,"label":"Re-engagement","key":"reengagement"}]
    for r in inqs:
        try:
            d=r["inquiry_date"]
            if "T" in d:dt=datetime.fromisoformat(d.split("+")[0]).date()
            else:dt=datetime.strptime(d[:10],"%Y-%m-%d").date()
            days=(today-dt).days
        except:continue
        for step in reversed(sched):
            if days>=step["day"] and(r.get("follow_up_day")or 0)<step["day"]:
                name=r["customer_name"]if r["customer_name"]!="Unknown"else"there"
                prod=(r["product_interest"]or"")[:80]
                cats_l=r.get("_cats")if"_cats"in r else parse_cats(r.get("categories"))
                msg=ai_gen_local(cats_l[0]if cats_l else"Other",step["key"],name,prod)
                ph=(r["phone"]or"").replace("+","").replace("-","").replace(" ","")
                due.append({"inquiry":r,"template":step["key"],"template_label":step["label"],"message":msg,"wa_link":f"https://wa.me/{ph}?text={quote(msg)}","days_since":days})
                break
    return due

def ai_gen_local(cat,tpl,name,prod):
    tpls={"Vending Machines":{"thank_you":"Hi {name} 👋\n\nThank you for interest in {product}! We're Arihant Enterprises — manufacturer & exporter from Pune.\n\n🏭 Free demo • 1-year warranty • Best prices\n\n📞 +917020134619\n— Arihant Enterprises","offer":"Hi {name} 👋\n\n🎯 ₹5,000 OFF + FREE installation!\n\n📞 +917020134619\n— Arihant Enterprises","reengagement":"Hi {name},\n\nStill looking for {product}? Book now for 6 months FREE maintenance.\n\n📞 +917020134619"},"Tea/Coffee Premix":{"thank_you":"Hi {name} 👋\n\nThanks for interest in our premix! Manufacturer from Pune.\n\n☕ Tea/Coffee premix • Bulk pricing\n\n📞 +917020134619\n— Arihant Enterprises","offer":"Hi {name} 👋\n\n🎯 10% OFF on 10kg+ orders + FREE samples!\n\n📞 +917020134619\n— Arihant Enterprises","reengagement":"Hi {name},\n\nStill looking for premix? Our Kadak Chai is a hit! ☕\n\n📞 +917020134619"},"Other":{"thank_you":"Hi {name} 👋\n\nThank you for interest in {product}! We're Arihant Enterprises — manufacturer from Pune.\n\n📞 +917020134619\n— Arihant Enterprises","offer":"Hi {name} 👋\n\n🎯 Direct-from-manufacturer pricing. 10% OFF!\n\n📞 +917020134619\n— Arihant Enterprises","reengagement":"Hi {name},\n\nStill interested in {product}?\n\n📞 +917020134619"}}
    c=tpls.get(cat,tpls["Other"]);t=c.get(tpl,c["thank_you"])
    return t.replace("{name}",name).replace("{product}",prod)

def mark_follow_up(id,key):
    c=db();d={"thank_you":0,"offer":2,"reengagement":10};c.execute("UPDATE inquiries SET follow_up_day=?,status='contacted' WHERE id=?",(d.get(key,0),id));c.commit();c.close()

def export_csv():
    inqs=get_inquiries();out=io.StringIO();w=csv.writer(out)
    w.writerow(["id","name","phone","email","product","category","location","status","date"])
    for i in inqs:w.writerow([i["id"],i["customer_name"],i.get("phone",""),i.get("email",""),(i.get("product_interest","")[:50]),"; ".join(parse_cats(i.get("categories"))),i.get("location",""),i["status"],(i.get("inquiry_date","")[:10])])
    return out.getvalue()

def install_page():
    return '''<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Install Arihant CRM</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,sans-serif;background:#0a0e27;color:#fff;min-height:100vh;display:flex;align-items:center;justify-content:center;padding:20px}
.c{background:#131836;border-radius:24px;padding:32px;max-width:400px;width:100%;text-align:center;border:1px solid #2d3436}
.ico{font-size:72px;margin-bottom:16px}
h1{font-size:24px;margin-bottom:4px;background:linear-gradient(135deg,#fff,#74b9ff);-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.sub{color:#636e72;font-size:14px;margin-bottom:24px}
.steps{text-align:left;margin:20px 0}
.s{display:flex;align-items:flex-start;gap:12px;padding:12px 0;border-bottom:1px solid #2d3436}
.s:last-child{border:none}
.n{background:#6c5ce7;color:#fff;width:32px;height:32px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:700;flex-shrink:0}
.t{font-size:14px;line-height:1.5}.t b{color:#00b894}
.btn{display:block;background:linear-gradient(135deg,#6c5ce7,#a29bfe);color:#fff;padding:16px;border-radius:16px;text-decoration:none;font-weight:700;font-size:18px;margin:16px 0;transition:all .2s}
.btn:active{transform:scale(.96)}
.btn2{display:block;background:#00b894;color:#fff;padding:14px;border-radius:14px;text-decoration:none;font-weight:600;font-size:14px;margin:8px 0}
.url{background:rgba(108,92,231,.1);border:1px solid rgba(108,92,231,.3);border-radius:12px;padding:12px;margin:16px 0;font-size:12px;word-break:break-all;color:#74b9ff}
.ios{background:rgba(0,184,148,.1);border:1px solid rgba(0,184,148,.3);border-radius:12px;padding:12px;margin:12px 0;font-size:12px}
</style></head><body>
<div class="c">
  <div class="ico">📱</div>
  <h1>Arihant Enterprises CRM</h1>
  <div class="sub">Manufacturer & Exporter, Pune</div>

  <a class="btn" href="/download">⬇️ Download APK (17KB)</a>

  <div class="steps">
    <div class="s"><div class="n">1</div><div class="t">Download the <b>APK file</b> above</div></div>
    <div class="s"><div class="n">2</div><div class="t">Open the downloaded file</div></div>
    <div class="s"><div class="n">3</div><div class="t">Tap <b>"Allow from this source"</b> if asked</div></div>
    <div class="s"><div class="n">4</div><div class="t">Tap <b>"Install"</b> — Done! 🎉</div></div>
  </div>

  <div class="ios">
    <b>📱 Or install as PWA (no APK needed):</b><br>
    Open <b>/</b> in Chrome → Tap ⋮ → <b>"Install app"</b>
  </div>

  <div class="url">App connects to:<br>https://locator-vote-toddler-measurement.trycloudflare.com</div>
</div>
</body></html>'''

if __name__=='__main__':
    print(f"\n🏢 Arihant Enterprises Mobile CRM")
    print(f"📍 http://localhost:{PORT}")
    print(f"📱 Open on phone → Add to Home Screen\n")
    HTTPServer(('0.0.0.0',PORT),H).serve_forever()
