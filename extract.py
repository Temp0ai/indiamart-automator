#!/usr/bin/env python3
"""
Indiamart Inquiry Extractor — Gmail IMAP version.
No Google Cloud project needed. Uses IMAP with app password.

Setup:
  1. Go to https://myaccount.google.com/apppasswords
  2. Generate an app password for "Mail"
  3. Set GMAIL_USER and GMAIL_APP_PASSWORD in .env or environment
"""

import imaplib
import email
from email.header import decode_header
import re
import json
import csv
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv
import os

load_dotenv()

# ── Config ───────────────────────────────────────────────────────────────────

GMAIL_USER = os.environ.get("GMAIL_USER", "")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "")
IMAP_SERVER = "imap.gmail.com"
IMAP_PORT = 993

CATEGORIES = {
    "Vending Machines":    ["vending", "coffee machine", "automatic machine", "dispenser"],
    "Tea/Coffee Premix":   ["premix", "tea premix", "coffee premix", "instant mix"],
    "Jaggery Products":    ["jaggery", "gur", "organic sweetener"],
    "Nescafe Premix":      ["nescafe", "nestle premix"],
    "Bru Premix":          ["bru", "bru premix", "hcc premix"],
    "Society Premix":      ["society", "housing society", "apartment", "bulk"],
}


# ── Helpers ──────────────────────────────────────────────────────────────────

def decode_mime_header(header_val):
    """Decode MIME-encoded header to plain string."""
    if not header_val:
        return ""
    parts = decode_header(header_val)
    decoded = []
    for part, charset in parts:
        if isinstance(part, bytes):
            decoded.append(part.decode(charset or "utf-8", errors="replace"))
        else:
            decoded.append(str(part))
    return " ".join(decoded)


def get_email_body(msg) -> str:
    """Extract plain text body from email message."""
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            ct = part.get_content_type()
            cd = str(part.get("Content-Disposition", ""))
            if ct == "text/plain" and "attachment" not in cd:
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    body = payload.decode(charset, errors="replace")
                    break
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            charset = msg.get_content_charset() or "utf-8"
            body = payload.decode(charset, errors="replace")
    return body


# ── Extraction ───────────────────────────────────────────────────────────────

PHONE_RE = re.compile(r'(?:\+91[\s-]?)?[6-9]\d{9}')
EMAIL_RE = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')
QUANTITY_RE = re.compile(r'(\d+)\s*(?:units?|pieces?|pcs?|nos?|machines?|sets?)', re.IGNORECASE)

CITIES = [
    "Mumbai", "Delhi", "Bangalore", "Bengaluru", "Hyderabad", "Ahmedabad",
    "Chennai", "Kolkata", "Pune", "Jaipur", "Lucknow", "Kanpur", "Nagpur",
    "Indore", "Thane", "Bhopal", "Visakhapatnam", "Patna", "Vadodara",
    "Ghaziabad", "Ludhiana", "Agra", "Nashik", "Faridabad", "Meerut",
    "Rajkot", "Varanasi", "Srinagar", "Aurangabad", "Amritsar", "Coimbatore",
    "Jabalpur", "Gwalior", "Vijayawada", "Jodhpur", "Madurai", "Raipur",
    "Kochi", "Chandigarh", "Mysore", "Thiruvananthapuram", "Surat",
]


def classify(text: str) -> list[str]:
    text_lower = text.lower()
    matched = [cat for cat, kw in CATEGORIES.items() if any(k in text_lower for k in kw)]
    return matched if matched else ["Other"]


def extract_phones(text: str) -> list[str]:
    raw = PHONE_RE.findall(text)
    cleaned = []
    for p in raw:
        digits = re.sub(r'\D', '', p)
        if len(digits) == 12 and digits.startswith('91'):
            digits = digits[2:]
        if len(digits) == 10 and digits[0] in '6789':
            cleaned.append(f"+91{digits}")
    return list(set(cleaned))


def extract_emails_from_body(text: str, sender_email: str) -> list[str]:
    found = EMAIL_RE.findall(text)
    return [e for e in found if 'indiamart' not in e.lower() and e != sender_email]


def extract_quantity(text: str) -> str | None:
    m = QUANTITY_RE.search(text)
    return m.group(1) if m else None


def extract_location(text: str) -> str | None:
    for city in CITIES:
        if re.search(rf'\b{city}\b', text, re.IGNORECASE):
            return city
    return None


def parse_inquiry(sender_email: str, sender_name: str, subject: str,
                  body: str, date_str: str, msg_id: str) -> dict:
    combined = f"{subject}\n{body}"

    # Try to extract customer name from body
    name = sender_name
    name_match = re.search(r'(?:from|name|contact person)[:\s]+([A-Z][a-z]+(?:\s[A-Z][a-z]+)*)', body, re.IGNORECASE)
    if name_match:
        name = name_match.group(1).strip()

    phones = extract_phones(combined)
    emails = extract_emails_from_body(combined, sender_email)
    categories = classify(combined)

    return {
        "id": f"IND-{datetime.now().strftime('%Y%m%d')}-{msg_id[:8]}",
        "customer_name": name or "Unknown",
        "phone": phones[0] if phones else None,
        "all_phones": phones,
        "email": emails[0] if emails else sender_email,
        "product_interest": subject,
        "categories": categories,
        "requirement": body[:500].strip(),
        "quantity": extract_quantity(combined),
        "location": extract_location(combined),
        "inquiry_date": date_str,
        "status": "new",
        "follow_up_day": 0,
        "source_message_id": msg_id,
    }


# ── Database ─────────────────────────────────────────────────────────────────

DB_PATH = "./data/inquiries.db"


def init_db():
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS inquiries (
            id TEXT PRIMARY KEY,
            customer_name TEXT,
            phone TEXT,
            all_phones TEXT,
            email TEXT,
            product_interest TEXT,
            categories TEXT,
            requirement TEXT,
            quantity TEXT,
            location TEXT,
            inquiry_date TEXT,
            status TEXT DEFAULT 'new',
            follow_up_day INTEGER DEFAULT 0,
            source_message_id TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    return conn


def save_inquiry(conn, inquiry):
    conn.execute("""
        INSERT OR REPLACE INTO inquiries
        (id, customer_name, phone, all_phones, email, product_interest,
         categories, requirement, quantity, location, inquiry_date,
         status, follow_up_day, source_message_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        inquiry["id"], inquiry["customer_name"], inquiry["phone"],
        json.dumps(inquiry["all_phones"]), inquiry["email"],
        inquiry["product_interest"], json.dumps(inquiry["categories"]),
        inquiry["requirement"], inquiry["quantity"], inquiry["location"],
        inquiry["inquiry_date"], inquiry["status"], inquiry["follow_up_day"],
        inquiry["source_message_id"],
    ))
    conn.commit()


# ── IMAP Fetcher ─────────────────────────────────────────────────────────────

def fetch_indiamart_emails(days_back: int = 7, max_results: int = 100) -> list[dict]:
    """Connect to Gmail via IMAP and fetch Indiamart inquiry emails."""
    if not GMAIL_USER or not GMAIL_APP_PASSWORD:
        raise ValueError(
            "Set GMAIL_USER and GMAIL_APP_PASSWORD in .env or environment.\n"
            "Generate app password at: https://myaccount.google.com/apppasswords"
        )

    print(f"📬 Connecting to Gmail as {GMAIL_USER}...")

    # Connect
    mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
    mail.login(GMAIL_USER, GMAIL_APP_PASSWORD)
    mail.select("INBOX")

    # Search for Indiamart emails
    since_date = (datetime.now() - timedelta(days=days_back)).strftime("%d-%b-%Y")
    search_criteria = f'(FROM "indiamart.com" SINCE {since_date})'
    print(f"🔍 Searching: {search_criteria}")

    status, message_ids = mail.search(None, search_criteria)
    if status != "OK":
        print("❌ Search failed")
        mail.logout()
        return []

    ids = message_ids[0].split()
    if not ids:
        print("📭 No Indiamart emails found.")
        mail.logout()
        return []

    # Limit results
    ids = ids[-max_results:]
    print(f"📨 Found {len(ids)} emails. Processing...\n")

    inquiries = []
    for mid in ids:
        status, msg_data = mail.fetch(mid, "(RFC822)")
        if status != "OK":
            continue

        raw_email = msg_data[0][1]
        msg = email.message_from_bytes(raw_email)

        # Decode headers
        subject = decode_mime_header(msg.get("Subject", ""))
        sender = decode_mime_header(msg.get("From", ""))
        date_str = msg.get("Date", "")
        message_id = msg.get("Message-ID", mid.decode())

        # Parse sender
        sender_name = ""
        sender_email = ""
        if "<" in sender and ">" in sender:
            sender_name = sender.split("<")[0].strip().strip('"')
            sender_email = sender.split("<")[1].split(">")[0]
        else:
            sender_email = sender

        # Get body
        body = get_email_body(msg)

        inquiry = parse_inquiry(
            sender_email=sender_email,
            sender_name=sender_name,
            subject=subject,
            body=body,
            date_str=date_str,
            msg_id=message_id,
        )
        inquiries.append(inquiry)

        print(f"  📋 {inquiry['id']}")
        print(f"     Name:  {inquiry['customer_name']}")
        print(f"     Phone: {inquiry['phone'] or 'N/A'}")
        print(f"     Cat:   {', '.join(inquiry['categories'])}")
        print()

    mail.logout()
    return inquiries


# ── CSV Export ───────────────────────────────────────────────────────────────

def export_to_csv(inquiries, output_path="./data/inquiries_export.csv"):
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "id", "customer_name", "phone", "email", "product_interest",
        "categories", "requirement", "quantity", "location", "inquiry_date", "status"
    ]
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        for inq in inquiries:
            row = dict(inq)
            if isinstance(row.get('categories'), list):
                row['categories'] = "; ".join(row['categories'])
            writer.writerow(row)
    return output_path


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("  Indiamart Inquiry Extractor — IMAP (No Cloud)")
    print("=" * 60)

    db = init_db()
    inquiries = fetch_indiamart_emails()

    for inq in inquiries:
        save_inquiry(db, inq)

    if inquiries:
        csv_path = export_to_csv(inquiries)
        print(f"✅ Saved {len(inquiries)} inquiries to DB")
        print(f"✅ Exported to {csv_path}")
    else:
        print("No new inquiries found.")

    db.close()
    print("\nDone.")


if __name__ == "__main__":
    main()
