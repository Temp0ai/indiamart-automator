#!/usr/bin/env python3
"""
Indiamart CRM — Full-featured PWA with Bulk WhatsApp & AI Messages.
Run: python crm.py  →  http://localhost:8080
"""

import json
import sqlite3
import csv
import io
import os
import re
import random
import time
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import quote, parse_qs, urlparse
from http.server import HTTPServer, BaseHTTPRequestHandler
from concurrent.futures import ThreadPoolExecutor
import urllib.request
import urllib.error
import ssl

DB_PATH = "./data/inquiries.db"
PORT = 8080
COMPANY_NAME = "Arihant Enterprises"
COMPANY_PHONE = "+917020134619"
COMPANY_TAGLINE = "Your trusted partner for premium vending machines & premix supplies"

# ── AI Message Generator ─────────────────────────────────────────────────────

CATEGORY_MESSAGES = {
    "Vending Machines": {
        "thank_you": [
            "Hi {name} 👋\n\nThank you for your interest in {product}! We're one of India's leading suppliers of automatic vending machines with 500+ happy clients.\n\n🏭 *What we offer:*\n• Tea/Coffee vending machines (2-lane to 8-lane)\n• Free site visit & demo\n• Installation + 1-year warranty\n• AMC packages available\n\n📞 Call us: {phone}\n💬 WhatsApp: This number\n\n— {company}",
            "Hi {name} 👋\n\nGreat to hear from you! We saw your inquiry about {product}.\n\nWe specialize in:\n✅ Automatic vending machines\n✅ Free installation & training\n✅ 24/7 service support\n✅ Bulk pricing for offices & societies\n\nLet's schedule a quick demo at your location?\n\n📞 {phone}\n— {company}",
        ],
        "offer": [
            "Hi {name} 👋\n\nFollowing up on your vending machine inquiry.\n\n🎯 *Exclusive Offer:*\n• ₹5,000 OFF on first order\n• FREE installation (worth ₹3,000)\n• 1-year comprehensive warranty\n• Free 100 cups of premix to test\n\n⏰ Offer valid this week only!\n\nShall I reserve a unit for you?\n\n📞 {phone}\n— {company}",
            "Hi {name} 👋\n\nStill thinking about that vending machine? Here's something to help you decide:\n\n💡 *Limited Time Deal:*\n• Premium 4-lane machine at ₹{price}\n• Includes 5kg premix starter kit\n• Free delivery & setup\n• EMI options available\n\nReply \"YES\" to book or \"CALL\" for a callback.\n\n— {company}",
        ],
        "reengagement": [
            "Hi {name},\n\nJust checking in — are you still looking for {product}?\n\nWe recently installed machines at 3 offices in {city} and the feedback has been amazing.\n\n💡 *This week's special:* Book now and get 6 months FREE maintenance.\n\nWant me to arrange a demo?\n\n📞 {phone}\n— {company}",
        ],
    },
    "Tea/Coffee Premix": {
        "thank_you": [
            "Hi {name} 👋\n\nThank you for your interest in our tea/coffee premix! We supply premium quality instant premixes to offices, canteens, and hotels across India.\n\n☕ *Our Range:*\n• Tea Premix (Regular & Masala)\n• Coffee Premix (Strong & Mild)\n• Kadak Chai Premix\n• Customizable sweetness levels\n\n📦 Available in 500g, 1kg, 5kg packs\n\n📞 {phone}\n— {company}",
        ],
        "offer": [
            "Hi {name} 👋\n\nSpecial offer on tea/coffee premix!\n\n🎯 *Bulk Deal:*\n• 10% OFF on orders above 10kg\n• FREE sample pack (500g x 3 flavors)\n• Free delivery on first order\n• Consistent taste, 6-month shelf life\n\nPerfect for offices, canteens & vending machines.\n\nReply \"SAMPLE\" to get free samples!\n\n📞 {phone}\n— {company}",
        ],
        "reengagement": [
            "Hi {name},\n\nStill looking for quality premix supply?\n\nWe just launched our new *Kadak Chai Premix* — 90% of our clients say it tastes like fresh chai! ☕\n\n💡 *Try before you buy:* Order a 500g trial pack at ₹{trial_price}.\n\nShall I send it over?\n\n📞 {phone}\n— {company}",
        ],
    },
    "Jaggery Products": {
        "thank_you": [
            "Hi {name} 👋\n\nThank you for your interest in our jaggery products! We're a direct manufacturer of organic jaggery from Maharashtra.\n\n🍯 *Our Products:*\n• Organic Jaggery Powder\n• Jaggery Blocks & Cubes\n• Jaggery Syrup (liquid)\n• Custom packaging for bulk orders\n\n🌿 100% organic, no chemicals\n📦 Pan-India delivery\n\n📞 {phone}\n— {company}",
        ],
        "offer": [
            "Hi {name} 👋\n\nSpecial pricing on jaggery products!\n\n🎯 *Bulk Offer:*\n• 15% OFF on orders above 50kg\n• FREE sample kit (5 varieties)\n• Custom private labeling available\n• FSSAI certified, export quality\n\nIdeal for: Sweets shops, bakeries, health food brands\n\nReply \"CATALOG\" for full price list.\n\n📞 {phone}\n— {company}",
        ],
        "reengagement": [
            "Hi {name},\n\nAre you still interested in jaggery supply?\n\nOur harvest-season stock is fresh and prices are at their lowest right now.\n\n💡 *Seasonal Special:* Order 100kg+ and get free doorstep delivery anywhere in India.\n\nShall I send you samples first?\n\n📞 {phone}\n— {company}",
        ],
    },
    "Nescafe Premix": {
        "thank_you": [
            "Hi {name} 👋\n\nThanks for your interest in Nescafé premix! We're an authorized distributor of Nestlé professional products.\n\n☕ *Nescafé Range:*\n• Nescafé Classic Premix\n• Nescafé Latte Premix\n• Nescafé Cappuccino\n• Nescafé Choco Mocha\n\n📦 Genuine Nestlé products\n🚚 Bulk pricing available\n\n📞 {phone}\n— {company}",
        ],
        "offer": [
            "Hi {name} 👋\n\nExclusive Nescafé premix deal!\n\n🎯 *Office Pack Offer:*\n• Buy 5kg, get 1kg FREE\n• Free vending machine on 50kg+ order\n• Installation & training included\n• Genuine Nestlé products only\n\nPerfect for offices & cafeterias.\n\nReply \"ORDER\" to avail!\n\n📞 {phone}\n— {company}",
        ],
        "reengagement": [
            "Hi {name},\n\nStill looking for Nescafé premix supply?\n\nWe have fresh stock with special pricing this month.\n\n💡 *Did you know?* Our clients save ₹2,000/month by switching from café coffee to Nescafé premix.\n\nWant a free taste test?\n\n📞 {phone}\n— {company}",
        ],
    },
    "Bru Premix": {
        "thank_you": [
            "Hi {name} 👋\n\nThank you for your interest in Bru premix! We supply authentic Bru coffee premix in bulk.\n\n☕ *Bru Range:*\n• Bru Instant Coffee Premix\n Bru Gold Premium\n• Bru Cappuccino Mix\n• Bru Green Label\n\n📦 Pack sizes: 1kg, 5kg, 25kg\n🚚 Free delivery on bulk orders\n\n📞 {phone}\n— {company}",
        ],
        "offer": [
            "Hi {name} 👋\n\nSpecial Bru premix pricing!\n\n🎯 *Bulk Deal:*\n• 12% OFF on 25kg+ orders\n• Free 1kg sample pack\n• Consistent quality guarantee\n• Monthly supply contracts available\n\nReply \"BULK\" for wholesale pricing.\n\n📞 {phone}\n— {company}",
        ],
        "reengagement": [
            "Hi {name},\n\nStill need Bru premix supply?\n\nWe can set up a monthly delivery schedule so you never run out.\n\n💡 *Auto-supply plan:* 10% discount + free delivery every month.\n\nInterested?\n\n📞 {phone}\n— {company}",
        ],
    },
    "Society Premix": {
        "thank_you": [
            "Hi {name} 👋\n\nThank you for your interest! We specialize in premix supply for housing societies & apartment complexes.\n\n🏢 *Society Packages:*\n• Tea/Coffee premix for common areas\n• Vending machine + premix combo\n• Bulk pricing for 50+ households\n• Monthly subscription plans\n\n☕ Make your society's common area premium!\n\n📞 {phone}\n— {company}",
        ],
        "offer": [
            "Hi {name} 👋\n\nSpecial offer for housing societies!\n\n🎯 *Society Combo:*\n• FREE vending machine installation\n• Premix at ₹{premix_price}/kg (20% below MRP)\n• Maintenance included for 1 year\n• Resident feedback: 4.8/5 rating\n\nBook a free demo for your society!\n\n📞 {phone}\n— {company}",
        ],
        "reengagement": [
            "Hi {name},\n\nStill thinking about a vending solution for your society?\n\nWe just installed one at {nearby_society} and the residents love it!\n\n💡 *Society Special:* First 10kg premix FREE with machine order.\n\nCan we schedule a demo?\n\n📞 {phone}\n— {company}",
        ],
    },
    "Other": {
        "thank_you": [
            "Hi {name} 👋\n\nThank you for reaching out! We received your inquiry about {product}.\n\nWe'd love to help you with the best solution.\n\n🏭 *About Us:*\n• Leading supplier of vending machines & premixes\n• 500+ satisfied clients across India\n• Free consultation & demo\n• Competitive pricing\n\nLet's discuss your requirements?\n\n📞 {phone}\n— {company}",
        ],
        "offer": [
            "Hi {name} 👋\n\nFollowing up on your inquiry about {product}.\n\n🎯 *Special Offer:*\n• 10% early-bird discount\n• Free consultation & demo\n• Flexible payment options\n• Pan-India delivery\n\nShall we schedule a call?\n\n📞 {phone}\n— {company}",
        ],
        "reengagement": [
            "Hi {name},\n\nJust checking in — are you still interested in {product}?\n\nWe'd be happy to help whenever you're ready.\n\n💡 Feel free to call us anytime at {phone}.\n\n— {company}",
        ],
    },
}

def ai_generate_message(category, template_type, name, product, phone):
    """Generate contextual message based on category and template type."""
    cat_msgs = CATEGORY_MESSAGES.get(category, CATEGORY_MESSAGES["Other"])
    templates = cat_msgs.get(template_type, cat_msgs["thank_you"])
    tpl = random.choice(templates)
    
    # Fill in variables
    prices = ["25,000", "35,000", "45,000", "55,000", "65,000"]
    trial_prices = ["149", "199", "249"]
    premix_prices = ["280", "320", "350"]
    nearby = ["Green Valley Apartments", "Sunshine Towers", "Royal Residency", "Metro Heights"]
    
    msg = tpl.format(
        name=name,
        product=product[:60],
        phone=phone,
        company=COMPANY_NAME,
        price=random.choice(prices),
        trial_price=random.choice(trial_prices),
        premix_price=random.choice(premix_prices),
        city="your area",
        nearby_society=random.choice(nearby),
    )
    return msg

def generate_bulk_messages(inquiries, template_type="thank_you"):
    """Generate AI messages for a list of inquiries."""
    results = []
    for inq in inquiries:
        name = inq["customer_name"] if inq["customer_name"] != "Unknown" else "there"
        product = (inq.get("product_interest") or "our products")[:60]
        phone = COMPANY_PHONE
        cats = inq.get("categories_parsed", ["Other"])
        category = cats[0] if cats else "Other"
        
        msg = ai_generate_message(category, template_type, name, product, phone)
        phone_clean = (inq.get("phone") or "").replace("+", "").replace("-", "").replace(" ", "").replace(" ", "")
        wa_link = f"https://wa.me/{phone_clean}?text={quote(msg)}" if phone_clean else ""
        
        results.append({
            "id": inq["id"],
            "name": inq["customer_name"],
            "phone": inq.get("phone"),
            "category": category,
            "message": msg,
            "wa_link": wa_link,
            "product": product,
        })
    return results


# ── Database ─────────────────────────────────────────────────────────────────

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def dict_row(row):
    return dict(row) if row else None

def dict_rows(rows):
    return [dict(r) for r in rows]

def parse_categories(cat_str):
    if not cat_str:
        return ["Other"]
    try:
        return json.loads(cat_str)
    except:
        return [cat_str]

def enrich_inquiry(inq):
    """Add parsed categories to inquiry dict."""
    inq["categories_parsed"] = parse_categories(inq.get("categories"))
    return inq

def get_stats():
    db = get_db()
    total = db.execute("SELECT COUNT(*) FROM inquiries").fetchone()[0]
    new = db.execute("SELECT COUNT(*) FROM inquiries WHERE status='new'").fetchone()[0]
    contacted = db.execute("SELECT COUNT(*) FROM inquiries WHERE status='contacted'").fetchone()[0]
    closed = db.execute("SELECT COUNT(*) FROM inquiries WHERE status='closed'").fetchone()[0]
    with_phone = db.execute("SELECT COUNT(*) FROM inquiries WHERE phone IS NOT NULL AND phone != ''").fetchone()[0]
    
    # Category breakdown
    all_inq = dict_rows(db.execute("SELECT categories, COUNT(*) as cnt FROM inquiries GROUP BY categories").fetchall())
    cat_counts = {}
    for row in all_inq:
        for cat in parse_categories(row["categories"]):
            cat_counts[cat] = cat_counts.get(cat, 0) + row["cnt"]
    
    recent = dict_rows(db.execute("SELECT * FROM inquiries ORDER BY created_at DESC LIMIT 10").fetchall())
    db.close()
    return {
        "total": total, "new": new, "contacted": contacted, "closed": closed,
        "with_phone": with_phone, "without_phone": total - with_phone,
        "category_counts": cat_counts, "recent": [enrich_inquiry(r) for r in recent],
    }

def get_inquiries(filters=None):
    db = get_db()
    query = "SELECT * FROM inquiries WHERE 1=1"
    params = []
    
    if filters:
        if filters.get("status"):
            query += " AND status = ?"
            params.append(filters["status"])
        if filters.get("category"):
            query += " AND categories LIKE ?"
            params.append(f"%{filters['category']}%")
        if filters.get("search"):
            query += " AND (customer_name LIKE ? OR product_interest LIKE ? OR email LIKE ? OR phone LIKE ?)"
            s = f"%{filters['search']}%"
            params.extend([s, s, s, s])
        if filters.get("has_phone"):
            if filters["has_phone"] == "yes":
                query += " AND phone IS NOT NULL AND phone != ''"
            else:
                query += " AND (phone IS NULL OR phone = '')"
    
    query += " ORDER BY inquiry_date DESC"
    rows = dict_rows(db.execute(query, params).fetchall())
    db.close()
    return [enrich_inquiry(r) for r in rows]

def get_inquiry(inquiry_id):
    db = get_db()
    row = db.execute("SELECT * FROM inquiries WHERE id = ?", (inquiry_id,)).fetchone()
    db.close()
    return enrich_inquiry(dict_row(row)) if row else None

def update_inquiry(inquiry_id, data):
    db = get_db()
    allowed = ["customer_name", "phone", "email", "product_interest", "categories",
               "requirement", "quantity", "location", "status", "follow_up_day"]
    sets = []
    params = []
    for k in allowed:
        if k in data:
            sets.append(f"{k} = ?")
            params.append(data[k])
    if not sets:
        return False
    params.append(inquiry_id)
    db.execute(f"UPDATE inquiries SET {', '.join(sets)} WHERE id = ?", params)
    db.commit()
    db.close()
    return True

def add_inquiry(data):
    db = get_db()
    rid = ''.join(random.choices("abcdefghijklmnopqrstuvwxyz0123456789", k=8))
    inq_id = f"IND-{datetime.now().strftime('%Y%m%d')}-{rid}"
    db.execute("""
        INSERT INTO inquiries (id, customer_name, phone, email, product_interest,
            categories, requirement, quantity, location, inquiry_date, status, follow_up_day)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
    """, (
        inq_id,
        data.get("customer_name", "Unknown"),
        data.get("phone") or None,
        data.get("email", ""),
        data.get("product_interest", ""),
        json.dumps([data.get("category", "Other")]),
        data.get("requirement", ""),
        data.get("quantity"),
        data.get("location"),
        datetime.now().isoformat(),
        "new",
    ))
    db.commit()
    db.close()
    return inq_id

def delete_inquiry(inquiry_id):
    db = get_db()
    db.execute("DELETE FROM inquiries WHERE id = ?", (inquiry_id,))
    db.commit()
    db.close()

def bulk_update_status(inquiry_ids, status):
    db = get_db()
    for inq_id in inquiry_ids:
        db.execute("UPDATE inquiries SET status = ? WHERE id = ?", (status, inq_id))
    db.commit()
    db.close()

def mark_sent(inquiry_id, template_key):
    db = get_db()
    day_map = {"thank_you": 0, "offer": 2, "reengagement": 10}
    day = day_map.get(template_key, 0)
    db.execute("UPDATE inquiries SET follow_up_day = ?, status = 'contacted' WHERE id = ?", (day, inquiry_id))
    db.commit()
    db.close()

def export_csv():
    inquiries = get_inquiries()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id", "name", "phone", "email", "product", "category", "city", "status", "date", "wa_me_link"])
    for inq in inquiries:
        cats = parse_categories(inq["categories"])
        phone = (inq["phone"] or "").replace("+", "")
        wa = f"https://wa.me/{phone}" if phone else ""
        writer.writerow([
            inq["id"], inq["customer_name"], inq["phone"] or "",
            inq["email"] or "", (inq["product_interest"] or "")[:50],
            "; ".join(cats), inq["location"] or "", inq["status"],
            (inq["inquiry_date"] or "")[:10], wa,
        ])
    return output.getvalue()


# ── HTML Frontend ────────────────────────────────────────────────────────────

def get_html():
    return '''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no">
<meta name="theme-color" content="#1a1a2e">
<meta name="apple-mobile-web-app-capable" content="yes">
<link rel="manifest" href="/manifest.json">
<link rel="icon" href="/icon.svg">
<title>Arihant CRM</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
:root{--bg:#f0f2f5;--card:#fff;--primary:#1a1a2e;--accent:#0f3460;--green:#00a884;--red:#e74c3c;--orange:#f39c12;--blue:#2196f3;--text:#1a1a2e;--muted:#666;--border:#e0e0e0;--shadow:0 1px 3px rgba(0,0,0,0.08)}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:var(--bg);color:var(--text);min-height:100vh;padding-bottom:70px}
.header{background:linear-gradient(135deg,#1a1a2e 0%,#16213e 100%);color:#fff;padding:16px;position:sticky;top:0;z-index:100}
.header h1{font-size:18px;font-weight:700}.header .sub{opacity:.7;font-size:11px;margin-top:2px}
.tabs{display:flex;background:#fff;border-bottom:1px solid var(--border);position:sticky;top:56px;z-index:99;overflow-x:auto;-webkit-overflow-scrolling:touch}
.tab{flex:1;padding:10px 6px;text-align:center;font-size:12px;font-weight:600;color:var(--muted);cursor:pointer;border-bottom:3px solid transparent;white-space:nowrap}
.tab.active{color:var(--primary);border-bottom-color:var(--green)}
.tab .badge{background:var(--green);color:#fff;border-radius:10px;padding:1px 5px;font-size:9px;margin-left:3px}
.page{display:none;padding:12px}.page.active{display:block}
.stats{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-bottom:12px}
.stat{background:var(--card);border-radius:10px;padding:12px;box-shadow:var(--shadow);text-align:center}
.stat .num{font-size:24px;font-weight:700}.stat .lbl{font-size:10px;color:var(--muted);margin-top:2px}
.stat.green .num{color:var(--green)}.stat.orange .num{color:var(--orange)}.stat.red .num{color:var(--red)}
.card{background:var(--card);border-radius:10px;padding:14px;margin-bottom:10px;box-shadow:var(--shadow)}
.card h3{font-size:14px;margin-bottom:8px}
.inquiry{display:flex;align-items:center;gap:10px;padding:10px;border-bottom:1px solid var(--border);cursor:pointer;transition:background .15s}
.inquiry:last-child{border-bottom:none}.inquiry:hover{background:#f8f9fa}
.inquiry .avatar{width:36px;height:36px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:14px;color:#fff;flex-shrink:0}
.inquiry .info{flex:1;min-width:0}.inquiry .name{font-weight:600;font-size:13px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.inquiry .product{font-size:11px;color:var(--muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.inquiry .meta{text-align:right;flex-shrink:0}.inquiry .date{font-size:10px;color:var(--muted)}
.inquiry .status{font-size:9px;padding:2px 6px;border-radius:8px;font-weight:600;display:inline-block;margin-top:3px}
.status-new{background:#e8f5e9;color:#2e7d32}.status-contacted{background:#fff3e0;color:#e65100}.status-closed{background:#fce4ec;color:#c62828}
.cat-tag{display:inline-block;padding:2px 6px;border-radius:8px;font-size:10px;font-weight:600;margin:1px;background:#e3f2fd;color:#1565c0}
.btn{display:inline-block;padding:10px 16px;border:none;border-radius:10px;font-size:13px;font-weight:600;cursor:pointer;transition:all .2s}
.btn-green{background:var(--green);color:#fff}.btn-green:hover{background:#008f72}
.btn-blue{background:var(--accent);color:#fff}.btn-blue:hover{background:#0d2d52}
.btn-outline{background:transparent;border:1.5px solid var(--border);color:var(--text)}.btn-outline:hover{background:#f5f5f5}
.btn-red{background:var(--red);color:#fff}
.btn-orange{background:var(--orange);color:#fff}
.btn-sm{padding:6px 12px;font-size:11px;border-radius:8px}
.btn-block{display:block;width:100%;text-align:center}
input,select,textarea{width:100%;padding:9px 11px;border:1.5px solid var(--border);border-radius:10px;font-size:13px;margin-bottom:10px;font-family:inherit}
input:focus,select:focus,textarea:focus{outline:none;border-color:var(--accent)}
textarea{resize:vertical;min-height:70px}
label{font-size:12px;font-weight:600;color:var(--muted);margin-bottom:3px;display:block}
.search-bar{display:flex;gap:8px;margin-bottom:12px}
.search-bar input{flex:1;margin-bottom:0}
.filter-row{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:10px}
.filter-row select{flex:1;min-width:100px;margin-bottom:0}
.detail-overlay{position:fixed;inset:0;background:rgba(0,0,0,.5);z-index:200;display:none;align-items:flex-end;justify-content:center}
.detail-overlay.show{display:flex}
.detail-panel{background:#fff;border-radius:14px 14px 0 0;width:100%;max-width:500px;max-height:85vh;overflow-y:auto;padding:16px;animation:slideUp .3s ease}
@keyframes slideUp{from{transform:translateY(100%)}to{transform:translateY(0)}}
.detail-panel .close{position:absolute;right:14px;top:14px;font-size:22px;cursor:pointer;background:none;border:none}
.detail-field{margin-bottom:14px}.detail-field label{margin-bottom:3px}.detail-field .val{font-size:14px;padding:6px 0}
.msg-preview{background:#e8f5e9;border-radius:10px;padding:12px;font-size:12px;white-space:pre-wrap;line-height:1.5;margin:10px 0}
.wa-link{display:flex;align-items:center;gap:6px;padding:10px;background:#25d366;color:#fff;border-radius:10px;text-decoration:none;font-weight:600;margin-top:6px;justify-content:center;font-size:13px}
.wa-link:hover{background:#1da851}
.bottom-nav{position:fixed;bottom:0;left:0;right:0;background:#fff;border-top:1px solid var(--border);display:flex;z-index:100}
.nav-item{flex:1;padding:8px 4px;text-align:center;font-size:9px;color:var(--muted);cursor:pointer;transition:color .2s}
.nav-item.active{color:var(--green)}.nav-item svg{display:block;margin:0 auto 1px;width:22px;height:22px}
.toast{position:fixed;bottom:72px;left:50%;transform:translateX(-50%);background:#333;color:#fff;padding:8px 18px;border-radius:18px;font-size:12px;z-index:300;display:none;animation:fadeIn .3s}
.toast.show{display:block}@keyframes fadeIn{from{opacity:0;transform:translateX(-50%) translateY(8px)}to{opacity:1;transform:translateX(-50%) translateY(0)}}
.fab{position:fixed;bottom:72px;right:14px;width:50px;height:50px;border-radius:50%;background:var(--green);color:#fff;display:flex;align-items:center;justify-content:center;font-size:24px;box-shadow:0 4px 12px rgba(0,168,132,.4);cursor:pointer;z-index:90;border:none}
.modal-bg{position:fixed;inset:0;background:rgba(0,0,0,.5);z-index:250;display:none;align-items:center;justify-content:center}
.modal-bg.show{display:flex}
.modal{background:#fff;border-radius:14px;padding:20px;width:92%;max-width:420px;max-height:80vh;overflow-y:auto}
.modal h2{margin-bottom:14px;font-size:16px}
.color-dot{width:8px;height:8px;border-radius:50%;display:inline-block;margin-right:5px}
.checkbox-row{display:flex;align-items:center;gap:8px;padding:8px 0;border-bottom:1px solid var(--border)}
.checkbox-row:last-child{border-bottom:none}
.checkbox-row input[type=checkbox]{width:18px;height:18px;margin:0;accent-color:var(--green)}
.bulk-bar{display:flex;gap:6px;align-items:center;padding:10px;background:#fff;border-bottom:1px solid var(--border);flex-wrap:wrap}
.bulk-bar select,.bulk-bar input{margin-bottom:0;padding:7px 10px;font-size:12px}
.msg-template{background:#f0f7ff;border:1px solid #bbdefb;border-radius:10px;padding:12px;margin:8px 0;font-size:12px;white-space:pre-wrap;line-height:1.5;max-height:200px;overflow-y:auto}
.msg-actions{display:flex;gap:6px;margin-top:8px;flex-wrap:wrap}
.msg-actions .btn{flex:1;min-width:80px}
.cat-pill{display:inline-block;padding:4px 10px;border-radius:14px;font-size:11px;font-weight:600;margin:3px;cursor:pointer;border:1.5px solid var(--border);background:#fff;transition:all .2s}
.cat-pill.active{background:var(--green);color:#fff;border-color:var(--green)}
.cat-pill:hover{border-color:var(--green)}
.select-all-bar{display:flex;justify-content:space-between;align-items:center;padding:8px 0;font-size:12px}
.select-all-bar a{color:var(--blue);cursor:pointer;font-weight:600}
.send-progress{background:#fff3e0;border-radius:10px;padding:12px;margin:10px 0;text-align:center}
.send-progress .bar{height:6px;background:#e0e0e0;border-radius:3px;overflow:hidden;margin-top:8px}
.send-progress .bar .fill{height:100%;background:var(--green);border-radius:3px;transition:width .3s}
</style>
</head>
<body>

<div class="header">
  <div style="display:flex;justify-content:space-between;align-items:center">
    <div>
      <h1>🏢 Arihant Enterprises CRM</h1>
      <div class="sub">Indiamart Inquiry Manager • WhatsApp Bulk Sender</div>
    </div>
    <div onclick="toggleSettings()" style="cursor:pointer;padding:6px;opacity:0.5;font-size:18px" title="Settings">⚙️</div>
  </div>
</div>

<!-- Settings Panel (hidden) -->
<div id="settings-panel" style="display:none;position:fixed;top:56px;right:0;background:#fff;border-radius:0 0 0 12px;padding:14px;box-shadow:-2px 2px 10px rgba(0,0,0,.15);z-index:101;width:260px">
  <div style="font-size:12px;font-weight:600;color:var(--muted);margin-bottom:8px">⚙️ Settings</div>
  <label style="font-size:11px">Gemini API Key</label>
  <input type="password" id="gemini-key" placeholder="AIza..." style="font-size:11px;padding:7px;margin-bottom:6px">
  <div style="display:flex;gap:6px">
    <button class="btn btn-blue btn-sm" style="flex:1;font-size:10px" onclick="saveGeminiKey()">Save</button>
    <button class="btn btn-outline btn-sm" style="flex:1;font-size:10px" onclick="testGemini()">Test</button>
  </div>
  <div id="gemini-status" style="font-size:10px;margin-top:6px;color:var(--muted)"></div>
  <div style="font-size:9px;color:#999;margin-top:8px">💡 Get key at: <a href="https://aistudio.google.com/apikey" target="_blank" style="color:var(--blue)">aistudio.google.com</a></div>
</div>

<div class="tabs">
  <div class="tab active" data-page="dashboard">📊 Home</div>
  <div class="tab" data-page="inquiries">📋 Inquiries <span class="badge" id="inq-count">0</span></div>
  <div class="tab" data-page="bulk">🚀 Bulk Send</div>
  <div class="tab" data-page="followups">📱 Follow-ups</div>
</div>

<!-- DASHBOARD -->
<div class="page active" id="page-dashboard">
  <div class="stats" id="stats-grid"></div>
  <div class="card">
    <h3>📂 By Category</h3>
    <div id="cat-breakdown"></div>
  </div>
  <div class="card">
    <h3>🕐 Recent Inquiries</h3>
    <div id="recent-list"></div>
  </div>
</div>

<!-- INQUIRIES -->
<div class="page" id="page-inquiries">
  <div class="search-bar">
    <input type="text" id="inq-search" placeholder="🔍 Search name, product, phone...">
  </div>
  <div class="filter-row">
    <select id="filter-status"><option value="">All Status</option><option value="new">New</option><option value="contacted">Contacted</option><option value="closed">Closed</option></select>
    <select id="filter-phone"><option value="">All</option><option value="yes">Has Phone</option><option value="no">No Phone</option></select>
    <select id="filter-cat"><option value="">All Categories</option><option>Vending Machines</option><option>Tea/Coffee Premix</option><option>Jaggery Products</option><option>Nescafe Premix</option><option>Bru Premix</option><option>Society Premix</option><option>Other</option></select>
  </div>
  <div id="inquiries-list"></div>
</div>

<!-- BULK SEND -->
<div class="page" id="page-bulk">
  <div class="card" style="background:linear-gradient(135deg,#e8f5e9,#c8e6c9)">
    <h3>🚀 WhatsApp Bulk Sender</h3>
    <p style="font-size:12px;color:var(--muted);margin-top:4px">Select category → Pick contacts → AI generates messages → Send via WhatsApp</p>
  </div>
  
  <!-- Step 1: Category -->
  <div class="card">
    <h3>Step 1️⃣ Select Category</h3>
    <div id="bulk-cats" style="margin-top:8px"></div>
  </div>
  
  <!-- Step 2: Template Type -->
  <div class="card">
    <h3>Step 2️⃣ Message Type</h3>
    <div style="display:flex;gap:6px;margin-top:8px;flex-wrap:wrap">
      <span class="cat-pill active" data-tpl="thank_you" onclick="selectTemplate(this)">👋 Thank You</span>
      <span class="cat-pill" data-tpl="offer" onclick="selectTemplate(this)">🎯 Special Offer</span>
      <span class="cat-pill" data-tpl="reengagement" onclick="selectTemplate(this)">🔄 Re-engagement</span>
    </div>
  </div>
  
  <!-- Step 3: Select Contacts -->
  <div class="card">
    <h3>Step 3️⃣ Select Contacts</h3>
    <div class="select-all-bar">
      <label><input type="checkbox" id="bulk-select-all" onchange="toggleSelectAll()" style="width:16px;height:16px;margin:0"> Select All</label>
      <span id="bulk-selected-count" style="color:var(--green);font-weight:600">0 selected</span>
    </div>
    <div id="bulk-contacts-list" style="max-height:300px;overflow-y:auto"></div>
  </div>
  
  <!-- Step 4: Generate & Send -->
  <div class="card">
    <h3>Step 4️⃣ Generate & Send</h3>
    <button class="btn btn-blue btn-block" onclick="generateBulkMessages()" style="margin-bottom:10px">🤖 AI Generate Messages</button>
    <div id="bulk-preview"></div>
  </div>
</div>

<!-- FOLLOW-UPS -->
<div class="page" id="page-followups">
  <div class="card" style="background:#e8f5e9">
    <h3>📱 Auto Follow-ups</h3>
    <p style="font-size:12px;color:var(--muted);margin-top:4px">Based on inquiry age — click to send via WhatsApp</p>
  </div>
  <div id="followup-list"></div>
</div>

<!-- DETAIL OVERLAY -->
<div class="detail-overlay" id="detail-overlay">
  <div class="detail-panel" id="detail-panel">
    <button class="close" onclick="closeDetail()">&times;</button>
    <div id="detail-content"></div>
  </div>
</div>

<!-- ADD MODAL -->
<div class="modal-bg" id="add-modal">
  <div class="modal">
    <h2>➕ Add New Inquiry</h2>
    <label>Name</label><input type="text" id="add-name" placeholder="Customer name">
    <label>Phone</label><input type="tel" id="add-phone" placeholder="+91XXXXXXXXXX">
    <label>Email</label><input type="email" id="add-email" placeholder="email@example.com">
    <label>Product Interest</label><input type="text" id="add-product" placeholder="e.g., Tea Vending Machine">
    <label>Category</label>
    <select id="add-category">
      <option>Vending Machines</option><option>Tea/Coffee Premix</option><option>Jaggery Products</option>
      <option>Nescafe Premix</option><option>Bru Premix</option><option>Society Premix</option><option>Other</option>
    </select>
    <label>Location</label><input type="text" id="add-location" placeholder="City">
    <label>Notes</label><textarea id="add-notes" placeholder="Requirement details..."></textarea>
    <div style="display:flex;gap:8px;margin-top:8px">
      <button class="btn btn-outline" style="flex:1" onclick="closeModal()">Cancel</button>
      <button class="btn btn-green" style="flex:1" onclick="saveNewInquiry()">Save</button>
    </div>
  </div>
</div>

<div class="toast" id="toast"></div>
<button class="fab" onclick="openAddModal()">+</button>

<div class="bottom-nav">
  <div class="nav-item active" data-page="dashboard">
    <svg viewBox="0 0 24 24" fill="currentColor"><path d="M3 13h8V3H3v10zm0 8h8v-6H3v6zm10 0h8V11h-8v10zm0-18v6h8V3h-8z"/></svg>Home
  </div>
  <div class="nav-item" data-page="inquiries">
    <svg viewBox="0 0 24 24" fill="currentColor"><path d="M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm-5 14H7v-2h7v2zm3-4H7v-2h10v2zm0-4H7V7h10v2z"/></svg>Inquiries
  </div>
  <div class="nav-item" data-page="bulk">
    <svg viewBox="0 0 24 24" fill="currentColor"><path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347z"/><path d="M12 2C6.477 2 2 6.477 2 12c0 1.89.525 3.66 1.438 5.168L2 22l4.832-1.438A9.955 9.955 0 0012 22c5.523 0 10-4.477 10-10S17.523 2 12 2z"/></svg>Bulk
  </div>
  <div class="nav-item" data-page="followups">
    <svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/></svg>Follow-up
  </div>
</div>

<script>
let allInquiries=[], followUps=[], bulkCategory='', bulkTemplate='thank_you', bulkSelected=new Set();

const COLORS=['#e91e63','#9c27b0','#673ab7','#3f51b5','#2196f3','#009688','#4caf50','#ff9800','#ff5722','#795548'];
function avColor(n){return COLORS[(n||'A').charCodeAt(0)%COLORS.length]}
function statusBadge(s){const c=s==='new'?'status-new':s==='contacted'?'status-contacted':'status-closed';return `<span class="status ${c}">${s}</span>`}
function catTags(c){if(!c)return'';try{c=JSON.parse(c)}catch{c=[c]}return c.map(x=>`<span class="cat-tag">${x}</span>`).join('')}
function fmtDate(d){if(!d)return'';try{const dt=new Date(d),now=new Date(),diff=Math.floor((now-dt)/86400000);if(diff===0)return'Today';if(diff===1)return'Yesterday';if(diff<7)return diff+'d ago';return dt.toLocaleDateString('en-IN',{day:'numeric',month:'short'})}catch{return d.substring(0,10)}}

async function api(path,opts={}){const r=await fetch('/api'+path,{headers:{'Content-Type':'application/json'},...opts,body:opts.body?JSON.stringify(opts.body):undefined});return r.json()}
function toast(m){const t=document.getElementById('toast');t.textContent=m;t.classList.add('show');setTimeout(()=>t.classList.remove('show'),2500)}
function debounce(fn,ms){let t;return(...a)=>{clearTimeout(t);t=setTimeout(()=>fn(...a),ms)}}

// Navigation
document.querySelectorAll('.tab,.nav-item').forEach(el=>{
  el.addEventListener('click',()=>{
    const p=el.dataset.page;
    document.querySelectorAll('.tab').forEach(t=>t.classList.toggle('active',t.dataset.page===p));
    document.querySelectorAll('.nav-item').forEach(n=>n.classList.toggle('active',n.dataset.page===p));
    document.querySelectorAll('.page').forEach(pg=>pg.classList.toggle('active',pg.id==='page-'+p));
    if(p==='bulk')loadBulkPage();
    if(p==='followups')loadFollowUps();
  });
});

// Dashboard
async function loadDashboard(){
  const s=await api('/stats');
  document.getElementById('inq-count').textContent=s.total;
  document.getElementById('stats-grid').innerHTML=`
    <div class="stat"><div class="num">${s.total}</div><div class="lbl">Total</div></div>
    <div class="stat green"><div class="num">${s.new}</div><div class="lbl">New</div></div>
    <div class="stat orange"><div class="num">${s.contacted}</div><div class="lbl">Contacted</div></div>
    <div class="stat"><div class="num">${s.with_phone}</div><div class="lbl">Has Phone</div></div>
    <div class="stat red"><div class="num">${s.without_phone}</div><div class="lbl">No Phone</div></div>
    <div class="stat"><div class="num">${s.closed}</div><div class="lbl">Closed</div></div>
  `;
  const cats=s.category_counts||{};
  document.getElementById('cat-breakdown').innerHTML=Object.entries(cats).sort((a,b)=>b[1]-a[1]).map(([cat,cnt])=>
    `<div style="display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid var(--border)"><span class="cat-tag">${cat}</span><strong>${cnt}</strong></div>`
  ).join('');
  document.getElementById('recent-list').innerHTML=(s.recent||[]).map(renderInquiryRow).join('');
}

// Inquiries
async function loadInquiries(){
  const p=new URLSearchParams();
  const s=document.getElementById('inq-search').value,st=document.getElementById('filter-status').value,ph=document.getElementById('filter-phone').value,cat=document.getElementById('filter-cat').value;
  if(s)p.set('search',s);if(st)p.set('status',st);if(ph)p.set('has_phone',ph);if(cat)p.set('category',cat);
  allInquiries=await api('/inquiries?'+p);
  document.getElementById('inq-count').textContent=allInquiries.length;
  document.getElementById('inquiries-list').innerHTML=allInquiries.length?allInquiries.map(renderInquiryRow).join(''):'<div class="card" style="text-align:center;padding:30px;color:var(--muted)">No inquiries found</div>';
}
function renderInquiryRow(inq){
  const n=inq.customer_name||'Unknown';
  return `<div class="inquiry" onclick="showDetail('${inq.id}')">
    <div class="avatar" style="background:${avColor(n)}">${n[0]}</div>
    <div class="info"><div class="name">${n}</div><div class="product">${(inq.product_interest||'').substring(0,55)}</div>${catTags(inq.categories)}</div>
    <div class="meta"><div class="date">${fmtDate(inq.inquiry_date)}</div>${statusBadge(inq.status)}</div>
  </div>`;
}
document.getElementById('inq-search').addEventListener('input',debounce(loadInquiries,300));
document.getElementById('filter-status').addEventListener('change',loadInquiries);
document.getElementById('filter-phone').addEventListener('change',loadInquiries);
document.getElementById('filter-cat').addEventListener('change',loadInquiries);

// Detail
async function showDetail(id){
  const inq=await api('/inquiries/'+id);if(!inq)return;
  const ph=inq.phone||'';
  const waLink=ph?`https://wa.me/${ph.replace(/[^0-9]/g,'')}?text=${encodeURIComponent('Hi '+(inq.customer_name||'')+' 👋')}`:'';
  document.getElementById('detail-content').innerHTML=`
    <div style="display:flex;align-items:center;gap:10px;margin-bottom:16px">
      <div class="avatar" style="background:${avColor(inq.customer_name)};width:44px;height:44px;font-size:18px">${(inq.customer_name||'?')[0]}</div>
      <div><div style="font-size:16px;font-weight:700">${inq.customer_name||'Unknown'}</div><div style="font-size:12px;color:var(--muted)">${(inq.product_interest||'').substring(0,50)}</div></div>
    </div>
    <div class="detail-field"><label>📞 Phone</label><div class="val">${ph||'<span style="color:var(--red)">Not available</span>'}</div></div>
    <div class="detail-field"><label>📧 Email</label><div class="val">${inq.email||'N/A'}</div></div>
    <div class="detail-field"><label>📍 Location</label><div class="val">${inq.location||'N/A'}</div></div>
    <div class="detail-field"><label>🏷️ Categories</label><div class="val">${catTags(inq.categories)}</div></div>
    <div class="detail-field"><label>📋 Requirement</label><div class="val" style="font-size:12px">${(inq.requirement||'N/A').substring(0,250)}</div></div>
    <div class="detail-field"><label>📅 Date</label><div class="val">${inq.inquiry_date||'N/A'}</div></div>
    <div class="detail-field"><label>🔄 Status</label><div class="val"><select onchange="updateStatus('${inq.id}',this.value)" style="margin-bottom:0"><option value="new" ${inq.status==='new'?'selected':''}>New</option><option value="contacted" ${inq.status==='contacted'?'selected':''}>Contacted</option><option value="closed" ${inq.status==='closed'?'selected':''}>Closed</option></select></div></div>
    <div class="detail-field"><label>📱 Update Phone</label><div style="display:flex;gap:6px"><input type="tel" id="edit-phone" value="${ph}" placeholder="+91XXXXXXXXXX" style="margin-bottom:0"><button class="btn btn-blue btn-sm" onclick="updatePhone('${inq.id}')">Save</button></div></div>
    ${waLink?`<a class="wa-link" href="${waLink}" target="_blank">💬 Open WhatsApp</a>`:''}
    <div style="display:flex;gap:6px;margin-top:12px;flex-wrap:wrap">
      <button class="btn btn-outline btn-sm" style="flex:1" onclick="genMsg('${inq.id}','thank_you')">👋 Thank You</button>
      <button class="btn btn-outline btn-sm" style="flex:1" onclick="genMsg('${inq.id}','offer')">🎯 Offer</button>
      <button class="btn btn-outline btn-sm" style="flex:1" onclick="genMsg('${inq.id}','reengagement')">🔄 Follow-up</button>
    </div>
    <div id="msg-p-${inq.id}"></div>
    <button class="btn btn-red btn-sm btn-block" style="margin-top:12px" onclick="deleteInq('${inq.id}')">🗑️ Delete</button>
  `;
  document.getElementById('detail-overlay').classList.add('show');
}
function closeDetail(){document.getElementById('detail-overlay').classList.remove('show')}
document.getElementById('detail-overlay').addEventListener('click',e=>{if(e.target===e.currentTarget)closeDetail()});

async function updateStatus(id,s){await api('/inquiries/'+id,{method:'PUT',body:{status:s}});toast('Updated');loadInquiries();loadDashboard()}
async function updatePhone(id){const ph=document.getElementById('edit-phone').value;await api('/inquiries/'+id,{method:'PUT',body:{phone:ph}});toast('Phone saved');showDetail(id)}
async function deleteInq(id){if(!confirm('Delete?'))return;await api('/inquiries/'+id,{method:'DELETE'});closeDetail();toast('Deleted');loadInquiries();loadDashboard()}

async function genMsg(id,tpl){
  const inq=await api('/inquiries/'+id);
  const cats=inq.categories_parsed||['Other'];
  document.getElementById(`msg-p-${id}`).innerHTML='<div style="text-align:center;padding:10px;color:var(--muted)">🤖 Generating...</div>';
  const msg=await ai_generate(cats[0],tpl,inq.customer_name||'there',(inq.product_interest||'').substring(0,60));
  const ph=(inq.phone||'').replace(/[^0-9]/g,'');
  const wa=ph?`https://wa.me/${ph}?text=${encodeURIComponent(msg)}`:'';
  document.getElementById(`msg-p-${id}`).innerHTML=`<div class="msg-preview">${msg}</div>${wa?`<a class="wa-link" href="${wa}" target="_blank" style="font-size:12px;padding:8px">💬 Send via WhatsApp</a>`:'<div style="color:var(--red);font-size:12px;margin-top:6px">⚠️ No phone</div>'}`;
}

// AI Message Generator (client-side)
const TPLS={
"Vending Machines":{
  thank_you:["Hi {name} 👋\\n\\nThank you for your interest in {product}! We\\'re one of India\\'s leading suppliers of automatic vending machines.\\n\\n🏭 What we offer:\\n• Tea/Coffee vending machines (2-lane to 8-lane)\\n• Free site visit & demo\\n• Installation + 1-year warranty\\n• AMC packages available\\n\\n📞 Call us: {phone}\\n— {company}"],
  offer:["Hi {name} 👋\\n\\nFollowing up on your vending machine inquiry.\\n\\n🎯 Exclusive Offer:\\n• ₹5,000 OFF on first order\\n• FREE installation (worth ₹3,000)\\n• 1-year warranty\\n• Free 100 cups premix to test\\n\\n⏰ Offer valid this week!\\n\\n📞 {phone}\\n— {company}"],
  reengagement:["Hi {name},\\n\\nStill looking for {product}?\\n\\nWe recently installed machines at 3 offices and feedback is amazing.\\n\\n💡 This week: Book now for 6 months FREE maintenance.\\n\\n📞 {phone}\\n— {company}"]
},
"Tea/Coffee Premix":{
  thank_you:["Hi {name} 👋\\n\\nThank you for your interest in our tea/coffee premix! We supply premium instant premixes to offices & canteens across India.\\n\\n☕ Our Range:\\n• Tea Premix (Regular & Masala)\\n• Coffee Premix (Strong & Mild)\\n• Kadak Chai Premix\\n\\n📦 Available in 500g, 1kg, 5kg\\n📞 {phone}\\n— {company}"],
  offer:["Hi {name} 👋\\n\\nSpecial offer on premix!\\n\\n🎯 Bulk Deal:\\n• 10% OFF on 10kg+ orders\\n• FREE sample pack (3 flavors)\\n• Free delivery on first order\\n• 6-month shelf life\\n\\nReply \\"SAMPLE\\" for free samples!\\n📞 {phone}\\n— {company}"],
  reengagement:["Hi {name},\\n\\nStill looking for quality premix?\\n\\nWe just launched Kadak Chai Premix — 90% say it tastes like fresh chai! ☕\\n\\n💡 Trial pack at special price.\\n\\n📞 {phone}\\n— {company}"]
},
"Jaggery Products":{
  thank_you:["Hi {name} 👋\\n\\nThank you for your interest in jaggery products! We\\'re a direct manufacturer of organic jaggery.\\n\\n🍯 Our Products:\\n• Organic Jaggery Powder\\n• Jaggery Blocks & Cubes\\n• Jaggery Syrup\\n\\n🌿 100% organic, FSSAI certified\\n📞 {phone}\\n— {company}"],
  offer:["Hi {name} 👋\\n\\nSpecial pricing on jaggery!\\n\\n🎯 Bulk Offer:\\n• 15% OFF on 50kg+ orders\\n• FREE sample kit\\n• Custom private labeling\\n• Export quality\\n\\nReply \\"CATALOG\\" for price list.\\n📞 {phone}\\n— {company}"],
  reengagement:["Hi {name},\\n\\nStill interested in jaggery supply?\\n\\nHarvest-season stock is fresh and prices are lowest now.\\n\\n💡 Order 100kg+ for free delivery anywhere in India.\\n\\n📞 {phone}\\n— {company}"]
},
"Nescafe Premix":{
  thank_you:["Hi {name} 👋\\n\\nThanks for your interest in Nescafé premix! We\\'re an authorized distributor.\\n\\n☕ Nescafé Range:\\n• Classic, Latte, Cappuccino\\n• Choco Mocha\\n\\n📦 Genuine Nestlé products\\n🚚 Bulk pricing available\\n📞 {phone}\\n— {company}"],
  offer:["Hi {name} 👋\\n\\nExclusive Nescafé deal!\\n\\n🎯 Office Pack:\\n• Buy 5kg, get 1kg FREE\\n• Free vending machine on 50kg+\\n• Installation included\\n\\nReply \\"ORDER\\" to avail!\\n📞 {phone}\\n— {company}"],
  reengagement:["Hi {name},\\n\\nStill looking for Nescafé premix?\\n\\nFresh stock with special pricing this month.\\n\\n💡 Clients save ₹2,000/month switching to premix.\\n\\n📞 {phone}\\n— {company}"]
},
"Bru Premix":{
  thank_you:["Hi {name} 👋\\n\\nThank you for interest in Bru premix! We supply authentic Bru coffee premix in bulk.\\n\\n☕ Bru Range:\\n• Instant, Gold, Cappuccino\\n\\n📦 Pack sizes: 1kg, 5kg, 25kg\\n🚚 Free delivery on bulk\\n📞 {phone}\\n— {company}"],
  offer:["Hi {name} 👋\\n\\nSpecial Bru pricing!\\n\\n🎯 Bulk Deal:\\n• 12% OFF on 25kg+\\n• Free 1kg sample\\n• Monthly contracts available\\n\\nReply \\"BULK\\" for wholesale pricing.\\n📞 {phone}\\n— {company}"],
  reengagement:["Hi {name},\\n\\nNeed Bru premix supply?\\n\\n💡 Auto-supply plan: 10% discount + free monthly delivery.\\n\\n📞 {phone}\\n— {company}"]
},
"Society Premix":{
  thank_you:["Hi {name} 👋\\n\\nThank you! We specialize in premix supply for housing societies.\\n\\n🏢 Society Packages:\\n• Tea/Coffee premix for common areas\\n• Vending machine + premix combo\\n• Bulk pricing for 50+ households\\n\\n📞 {phone}\\n— {company}"],
  offer:["Hi {name} 👋\\n\\nSpecial for housing societies!\\n\\n🎯 Society Combo:\\n• FREE vending machine install\\n• Premix at wholesale rates\\n• Maintenance included 1 year\\n\\n📞 {phone}\\n— {company}"],
  reengagement:["Hi {name},\\n\\nThinking about a vending solution for your society?\\n\\n💡 Society Special: First 10kg premix FREE with machine order.\\n\\n📞 {phone}\\n— {company}"]
},
"Other":{
  thank_you:["Hi {name} 👋\\n\\nThank you for reaching out about {product}!\\n\\nWe\\'d love to help.\\n\\n🏭 About Us:\\n• Leading supplier of vending machines & premixes\\n• 500+ clients across India\\n• Free consultation & demo\\n\\n📞 {phone}\\n— {company}"],
  offer:["Hi {name} 👋\\n\\nFollowing up on {product}.\\n\\n🎯 Special Offer:\\n• 10% early-bird discount\\n• Free consultation\\n• Pan-India delivery\\n\\n📞 {phone}\\n— {company}"],
  reengagement:["Hi {name},\\n\\nStill interested in {product}?\\n\\n💡 Call us anytime: {phone}\\n— {company}"]
}
};

function ai_gen(cat,tpl,name,product){
  const c=TPLS[cat]||TPLS["Other"];
  const t=c[tpl]||c.thank_you;
  const msg=t[Math.floor(Math.random()*t.length)];
  return msg.replace(/{name}/g,name).replace(/{product}/g,product).replace(/{phone}/g,"+917020134619").replace(/{company}/g,"Arihant Enterprises");
}

// Bulk Send Page
async function loadBulkPage(){
  const inqs=await api('/inquiries?has_phone=yes');
  const cats={};
  inqs.forEach(i=>{
    (i.categories_parsed||['Other']).forEach(c=>{
      if(!cats[c])cats[c]=[];
      cats[c].push(i);
    });
  });
  
  const allCats=Object.keys(cats).sort((a,b)=>cats[b].length-cats[a].length);
  document.getElementById('bulk-cats').innerHTML=allCats.map(c=>
    `<span class="cat-pill ${c===bulkCategory?'active':''}" onclick="selectBulkCat('${c}',this)">${c} (${cats[c].length})</span>`
  ).join('')+'<span class="cat-pill '+(bulkCategory===''?'active':'')+'" onclick="selectBulkCat(\'\',this)">All ('+inqs.length+')</span>';
  
  const filtered=bulkCategory?(cats[bulkCategory]||[]):inqs;
  bulkSelected.clear();
  document.getElementById('bulk-select-all').checked=false;
  document.getElementById('bulk-selected-count').textContent='0 selected';
  
  document.getElementById('bulk-contacts-list').innerHTML=filtered.map(i=>`
    <div class="checkbox-row">
      <input type="checkbox" data-id="${i.id}" onchange="updateBulkSelected()">
      <div class="avatar" style="background:${avColor(i.customer_name)};width:30px;height:30px;font-size:12px">${(i.customer_name||'?')[0]}</div>
      <div style="flex:1;min-width:0">
        <div style="font-size:12px;font-weight:600">${i.customer_name||'Unknown'}</div>
        <div style="font-size:10px;color:var(--muted)">${i.phone||''} • ${(i.product_interest||'').substring(0,35)}</div>
      </div>
      ${catTags(i.categories)}
    </div>
  `).join('') || '<div style="text-align:center;padding:20px;color:var(--muted)">No contacts with phone numbers</div>';
  
  window._bulkInqs=filtered;
}

function selectBulkCat(cat,el){
  bulkCategory=cat;
  document.querySelectorAll('#bulk-cats .cat-pill').forEach(p=>p.classList.remove('active'));
  el.classList.add('active');
  loadBulkPage();
}

function selectTemplate(el){
  document.querySelectorAll('[data-tpl]').forEach(p=>p.classList.remove('active'));
  el.classList.add('active');
  bulkTemplate=el.dataset.tpl;
}

function toggleSelectAll(){
  const checked=document.getElementById('bulk-select-all').checked;
  document.querySelectorAll('#bulk-contacts-list input[type=checkbox]').forEach(cb=>{cb.checked=checked});
  updateBulkSelected();
}

function updateBulkSelected(){
  bulkSelected.clear();
  document.querySelectorAll('#bulk-contacts-list input[type=checkbox]:checked').forEach(cb=>bulkSelected.add(cb.dataset.id));
  document.getElementById('bulk-selected-count').textContent=bulkSelected.size+' selected';
}

function generateBulkMessages(){
  if(!bulkSelected.size){toast('Select contacts first!');return}
  _generateBulkAI();
}

async function _generateBulkAI(){
  const inqs=(window._bulkInqs||[]).filter(i=>bulkSelected.has(i.id));
  document.getElementById('bulk-preview').innerHTML='<div class="send-progress"><strong>🤖 Generating AI messages...</strong><p style="font-size:11px;color:var(--muted);margin-top:4px">'+(getGeminiKey()?'Using Gemini AI':'Using templates')+'</p></div>';
  
  const msgs=[];
  for(const i of inqs){
    const cats=i.categories_parsed||['Other'];
    const msg=await ai_generate(cats[0],bulkTemplate,i.customer_name||'there',(i.product_interest||'').substring(0,60));
    const ph=(i.phone||'').replace(/[^0-9]/g,'');
    msgs.push({id:i.id,name:i.customer_name,phone:i.phone,message:msg,wa_link:ph?`https://wa.me/${ph}?text=${encodeURIComponent(msg)}`:''});
  }
  
  document.getElementById('bulk-preview').innerHTML=`
    <div class="send-progress">
      <strong>📨 ${msgs.length} messages ready</strong>
      <p style="font-size:11px;color:var(--muted);margin-top:4px">${getGeminiKey()?'🤖 Gemini AI generated':'📋 Template generated'} • Click to send</p>
    </div>
    <button class="btn btn-green btn-block" onclick="openAllWhatsApp()" style="margin-bottom:10px">📱 Open All in WhatsApp (${msgs.length})</button>
    <button class="btn btn-outline btn-block" onclick="markAllSent()" style="margin-bottom:10px">✅ Mark All as Sent</button>
    ${msgs.map((m,i)=>`
      <div class="card" style="padding:10px">
        <div style="display:flex;justify-content:space-between;align-items:center">
          <strong style="font-size:12px">${m.name}</strong>
          <span style="font-size:10px;color:var(--muted)">${m.phone||'No phone'}</span>
        </div>
        <div class="msg-template">${m.message}</div>
        <div class="msg-actions">
          ${m.wa_link?`<a class="btn btn-green btn-sm" href="${m.wa_link}" target="_blank" style="text-decoration:none;text-align:center">💬 Send</a>`:''}
          <button class="btn btn-outline btn-sm" onclick="copyMsg(this,${JSON.stringify(m.message).replace(/`/g,'\\`')})">📋 Copy</button>
          <button class="btn btn-outline btn-sm" onclick="markOneSent('${m.id}')">✓ Sent</button>
        </div>
      </div>
    `).join('')}
  `;
  window._bulkMsgs=msgs;
}

function openAllWhatsApp(){
  const msgs=window._bulkMsgs||[];
  let i=0;
  function openNext(){
    if(i>=msgs.length){toast('All opened!');return}
    const m=msgs[i];
    if(m.wa_link){window.open(m.wa_link,'_blank')}
    i++;
    setTimeout(openNext,2000);
  }
  openNext();
}

async function markAllSent(){
  const ids=Array.from(bulkSelected);
  await api('/bulk-status',{method:'POST',body:{ids,status:'contacted'}});
  toast(ids.length+' marked as contacted!');
  loadBulkPage();loadDashboard();
}

async function markOneSent(id){
  await api('/inquiries/'+id,{method:'PUT',body:{status:'contacted'}});
  toast('Marked as contacted');
}

function copyMsg(btn,msg){
  navigator.clipboard.writeText(msg).then(()=>{btn.textContent='✓ Copied';setTimeout(()=>btn.textContent='📋 Copy',1500)});
}

// Follow-ups
async function loadFollowUps(){
  const fs=await api('/followups');
  document.getElementById('followup-list').innerHTML=fs.length?fs.map(f=>`
    <div class="card">
      <div style="display:flex;justify-content:space-between;align-items:center">
        <div><strong>${f.inquiry.customer_name}</strong><div style="font-size:11px;color:var(--muted)">${(f.inquiry.product_interest||'').substring(0,40)}</div><span class="cat-tag">${f.template_label}</span></div>
        <span style="font-size:10px;color:var(--muted)">${f.days_since}d ago</span>
      </div>
      <div class="msg-template" style="font-size:11px">${f.message.substring(0,180)}...</div>
      <div style="display:flex;gap:6px;margin-top:6px">
        <a class="btn btn-green btn-sm" href="${f.wa_link}" target="_blank" style="flex:1;text-decoration:none;text-align:center;font-size:11px">💬 Send</a>
        <button class="btn btn-outline btn-sm" onclick="markFollowUp('${f.inquiry.id}','${f.template}')" style="font-size:11px">✓ Sent</button>
      </div>
    </div>
  `).join(''):'<div class="card" style="text-align:center;padding:30px;color:var(--muted)">No follow-ups due</div>';
}

async function markFollowUp(id,tpl){await api('/followups/mark',{method:'POST',body:{id,template:tpl}});toast('Marked');loadFollowUps();loadDashboard()}

// Add Modal
function openAddModal(){document.getElementById('add-modal').classList.add('show')}
function closeModal(){document.getElementById('add-modal').classList.remove('show')}
document.getElementById('add-modal').addEventListener('click',e=>{if(e.target===e.currentTarget)closeModal()});

async function saveNewInquiry(){
  const d={customer_name:document.getElementById('add-name').value||'Unknown',phone:document.getElementById('add-phone').value,email:document.getElementById('add-email').value,product_interest:document.getElementById('add-product').value,category:document.getElementById('add-category').value,location:document.getElementById('add-location').value,requirement:document.getElementById('add-notes').value};
  await api('/inquiries',{method:'POST',body:d});closeModal();toast('Added!');loadInquiries();loadDashboard();
  ['add-name','add-phone','add-email','add-product','add-location','add-notes'].forEach(id=>document.getElementById(id).value='');
}

// Init
loadDashboard();loadInquiries();

// Settings
function toggleSettings(){const p=document.getElementById('settings-panel');p.style.display=p.style.display==='none'?'block':'none'}
document.addEventListener('click',e=>{const p=document.getElementById('settings-panel');const g=e.target.closest('[title=Settings]');if(p&&!p.contains(e.target)&&!g)p.style.display='none'});

// Gemini
function getGeminiKey(){return localStorage.getItem('gemini_key')||''}
function saveGeminiKey(){const k=document.getElementById('gemini-key').value.trim();if(k){localStorage.setItem('gemini_key',k);document.getElementById('gemini-status').textContent='✅ Saved';document.getElementById('gemini-status').style.color='var(--green)'}else{localStorage.removeItem('gemini_key');document.getElementById('gemini-status').textContent='Removed'}}
async function testGemini(){
  const k=getGeminiKey();if(!k){document.getElementById('gemini-status').textContent='❌ Enter key first';return}
  document.getElementById('gemini-status').textContent='⏳ Testing...'
  try{const r=await fetch('/api/gemini',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({key:k,prompt:'Say hello in 5 words'})});const d=await r.json();if(d.result&&!d.result.includes('Error')){document.getElementById('gemini-status').textContent='✅ Connected!';document.getElementById('gemini-status').style.color='var(--green)'}else{document.getElementById('gemini-status').textContent='❌ '+d.result;document.getElementById('gemini-status').style.color='var(--red)'}}catch(e){document.getElementById('gemini-status').textContent='❌ Failed';document.getElementById('gemini-status').style.color='var(--red)'}}
document.addEventListener('DOMContentLoaded',()=>{const k=getGeminiKey();if(k)document.getElementById('gemini-key').value=k});

// AI Message with Gemini fallback
async function ai_generate(category,tpl,name,product){
  const key=getGeminiKey();
  if(key){
    const tplLabels={thank_you:'a warm thank-you message',offer:'a special offer/discount message',reengagement:'a re-engagement follow-up message'};
    const prompt=`You are a WhatsApp business message writer for ${COMPANY_NAME}. We sell vending machines, tea/coffee premix, jaggery products, and Nescafe/Bru premix.

Write ${tplLabels[tpl]||'a message'} for:
- Customer: ${name}
- Product interest: ${product}
- Category: ${category}
- Company: ${COMPANY_NAME}
- Phone: ${COMPANY_PHONE}

Rules:
- Keep it under 150 words
- Use emojis naturally (👋 ☕ 🎯 ✅ 💡)
- Include a clear call-to-action
- Be warm and professional, not pushy
- Format for WhatsApp (use *bold* for emphasis, line breaks)
- End with company name and phone
- Do NOT use markdown headers
- Just return the message text, nothing else`;

    try{
      const r=await fetch('/api/gemini',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({key,prompt})});
      const d=await r.json();
      if(d.result&&!d.result.includes('Error'))return d.result;
    }catch(e){}
  }
  // Fallback to templates
  return ai_gen(category,tpl,name,product);
}
</script>
</body>
</html>'''


# ── API Handler ──────────────────────────────────────────────────────────────

class CRMHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args): pass

    def send_json(self, data, status=200):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data, default=str).encode())

    def send_html(self, html):
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(html.encode())

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_GET(self):
        path = urlparse(self.path).path
        params = parse_qs(urlparse(self.path).query)

        if path == '/' or path == '/index.html':
            self.send_html(get_html())
        elif path == '/manifest.json':
            self.send_response(200)
            self.send_header('Content-Type', 'application/manifest+json')
            self.end_headers()
            self.wfile.write(json.dumps({
                "name": "Arihant Enterprises CRM", "short_name": "Arihant CRM",
                "start_url": "/", "display": "standalone",
                "background_color": "#1a1a2e", "theme_color": "#1a1a2e",
                "icons": [{"src": "/icon.svg", "sizes": "any", "type": "image/svg+xml"}],
            }).encode())
        elif path == '/icon.svg':
            self.send_response(200)
            self.send_header('Content-Type', 'image/svg+xml')
            self.end_headers()
            self.wfile.write(b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><rect width="100" height="100" rx="20" fill="#1a1a2e"/><text x="50" y="68" font-size="50" text-anchor="middle" fill="white">\xf0\x9f\x8f\xa2</text></svg>')
        elif path == '/sw.js':
            self.send_response(200)
            self.send_header('Content-Type', 'application/javascript')
            self.end_headers()
            self.wfile.write(b"self.addEventListener('install',e=>{self.skipWaiting()});self.addEventListener('activate',e=>{e.waitUntil(clients.claim())});self.addEventListener('fetch',e=>{if(e.request.url.includes('/api/'))return;e.respondWith(caches.match(e.request).then(r=>r||fetch(e.request).then(resp=>{const c=resp.clone();caches.open('crm-v1').then(c=>c.put(e.request,c));return resp})))});")
        elif path == '/api/stats':
            self.send_json(get_stats())
        elif path == '/api/inquiries':
            filters = {k: v[0] for k, v in params.items() if v}
            self.send_json(get_inquiries(filters))
        elif path.startswith('/api/inquiries/'):
            self.send_json(get_inquiry(path.split('/')[-1]))
        elif path == '/api/followups':
            self.send_json(get_due_follow_ups())
        elif path == '/api/export':
            self.send_response(200)
            self.send_header('Content-Type', 'text/csv')
            self.send_header('Content-Disposition', 'attachment; filename=inquiries.csv')
            self.end_headers()
            self.wfile.write(export_csv().encode())
        else:
            self.send_response(404)
            self.end_headers()

    def read_body(self):
        length = int(self.headers.get('Content-Length', 0))
        return json.loads(self.rfile.read(length)) if length else {}

    def do_POST(self):
        path = urlparse(self.path).path
        body = self.read_body()

        if path == '/api/inquiries':
            self.send_json({"id": add_inquiry(body), "ok": True})
        elif path == '/api/followups/mark':
            mark_sent(body.get('id'), body.get('template'))
            self.send_json({"ok": True})
        elif path == '/api/bulk-status':
            bulk_update_status(body.get('ids', []), body.get('status', 'contacted'))
            self.send_json({"ok": True})
        elif path == '/api/gemini':
            api_key = body.get('key', '')
            prompt = body.get('prompt', '')
            if not api_key or not prompt:
                self.send_json({"error": "Missing key or prompt"}, 400)
            else:
                result = call_gemini(api_key, prompt)
                self.send_json({"result": result})
        else:
            self.send_response(404)
            self.end_headers()

    def do_PUT(self):
        path = urlparse(self.path).path
        body = self.read_body()
        if path.startswith('/api/inquiries/'):
            update_inquiry(path.split('/')[-1], body)
            self.send_json({"ok": True})
        else:
            self.send_response(404)
            self.end_headers()

    def do_DELETE(self):
        path = urlparse(self.path).path
        if path.startswith('/api/inquiries/'):
            delete_inquiry(path.split('/')[-1])
            self.send_json({"ok": True})
        else:
            self.send_response(404)
            self.end_headers()


# ── Gemini API Proxy ──────────────────────────────────────────────────────────

def call_gemini(api_key, prompt):
    """Call Gemini API to generate AI messages."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"
    payload = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.8, "maxOutputTokens": 500}
    }).encode()
    
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    ctx = ssl.create_default_context()
    
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=15) as resp:
            result = json.loads(resp.read())
            return result["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        return f"Error: {str(e)}"


if __name__ == '__main__':
    print(f"\n🏢 Arihant Enterprises CRM")
    print(f"📍 http://localhost:{PORT}")
    print(f"📱 Install as PWA: Open on phone → Add to Home Screen")
    print(f"🚀 Features: Dashboard | Inquiries | Bulk WhatsApp | AI Messages\n")
    server = HTTPServer(('0.0.0.0', PORT), CRMHandler)
    server.serve_forever()
