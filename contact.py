#!/usr/bin/env python3
"""
Phone & SMS handler — Generate tel: links, SMS links, and call logs.
No external API needed. Opens native phone/SMS apps via URL schemes.
"""

import sqlite3
import csv
import json
from datetime import datetime
from pathlib import Path

DB_PATH = "./data/inquiries.db"
CALL_LOG_PATH = "./data/call_log.csv"


def log_call(inquiry_id: str, phone: str, action: str, notes: str = ""):
    """Log a call or SMS attempt."""
    Path(CALL_LOG_PATH).parent.mkdir(parents=True, exist_ok=True)
    is_new = not Path(CALL_LOG_PATH).exists()
    with open(CALL_LOG_PATH, 'a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        if is_new:
            writer.writerow(["timestamp", "inquiry_id", "phone", "action", "notes"])
        writer.writerow([datetime.now().isoformat(), inquiry_id, phone, action, notes])


def update_status(inquiry_id: str, status: str):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("UPDATE inquiries SET status = ? WHERE id = ?", (status, inquiry_id))
    conn.commit()
    conn.close()


def get_inquiry(inquiry_id: str) -> dict | None:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM inquiries WHERE id = ?", (inquiry_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def generate_call_link(phone: str) -> str:
    """Generate tel: link for phone calls."""
    clean = phone.replace("+", "").replace("-", "").replace(" ", "")
    return f"tel:+{clean}"


def generate_sms_link(phone: str, message: str = "") -> str:
    """Generate sms: link with optional pre-filled message."""
    clean = phone.replace("+", "").replace("-", "").replace(" ", "")
    from urllib.parse import quote
    if message:
        return f"sms:+{clean}?body={quote(message)}"
    return f"sms:+{clean}"


def generate_whatsapp_link(phone: str, message: str = "") -> str:
    """Generate wa.me click-to-chat link."""
    clean = phone.replace("+", "").replace("-", "").replace(" ", "")
    from urllib.parse import quote
    if message:
        return f"https://wa.me/{clean}?text={quote(message)}"
    return f"https://wa.me/{clean}"


def quick_contact(inquiry_id: str):
    """Print all contact options for an inquiry."""
    inq = get_inquiry(inquiry_id)
    if not inq:
        print(f"❌ Inquiry {inquiry_id} not found.")
        return

    phone = inq.get("phone")
    if not phone:
        print(f"❌ No phone number for {inquiry_id}.")
        return

    name = inq["customer_name"]
    product = inq["product_interest"][:60]

    print(f"\n{'=' * 50}")
    print(f"  Contact: {name}")
    print(f"  Product: {product}")
    print(f"  Phone:   {phone}")
    print(f"{'=' * 50}\n")

    # Pre-built messages
    thank_you = (
        f"Hi {name}, thank you for your interest in {product}. "
        f"We'd love to help you. When would be a good time to discuss?"
    )

    print(f"📞 Call:      {generate_call_link(phone)}")
    print(f"💬 SMS:       {generate_sms_link(phone, thank_you)}")
    print(f"📱 WhatsApp:  {generate_whatsapp_link(phone, thank_you)}")
    print(f"\n💡 To use: copy the link above and paste in your browser.")
    print(f"   Or run with --action call/sms/whatsapp to auto-open.\n")

    return {
        "call": generate_call_link(phone),
        "sms": generate_sms_link(phone, thank_you),
        "whatsapp": generate_whatsapp_link(phone, thank_you),
    }


# ── CLI ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    import webbrowser

    parser = argparse.ArgumentParser(description="Quick contact for Indiamart inquiries")
    parser.add_argument("--id", help="Inquiry ID to contact")
    parser.add_argument("--action", choices=["call", "sms", "whatsapp"], default="whatsapp")
    parser.add_argument("--list", action="store_true", help="List all inquiries with phones")
    parser.add_argument("--log", help="Log a completed call/SMS for inquiry ID")
    parser.add_argument("--status", nargs=2, metavar=("ID", "STATUS"),
                        help="Update inquiry status (new/contacted/qualified/closed)")

    args = parser.parse_args()

    if args.list:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        rows = conn.execute("""
            SELECT id, customer_name, phone, categories, location, status
            FROM inquiries WHERE phone IS NOT NULL ORDER BY created_at DESC
        """).fetchall()
        conn.close()
        print(f"\n{'ID':<20} {'Name':<20} {'Phone':<16} {'Category':<20} {'Status':<10}")
        print("-" * 90)
        for r in rows:
            cats = json.loads(r["categories"])[0] if r["categories"] else "Other"
            print(f"{r['id']:<20} {r['customer_name']:<20} {r['phone']:<16} {cats:<20} {r['status']:<10}")
        print(f"\nTotal: {len(rows)} inquiries with phone numbers\n")

    elif args.id:
        links = quick_contact(args.id)
        if links and args.action:
            url = links.get(args.action)
            if url:
                print(f"Opening: {url}")
                webbrowser.open(url)
                log_call(args.id, "", args.action)
                print(f"✅ Logged {args.action} attempt.")

    elif args.log:
        log_call(args.log, "", "manual", "Completed manually")
        print(f"✅ Logged contact for {args.log}")

    elif args.status:
        update_status(args.status[0], args.status[1])
        print(f"✅ Updated {args.status[0]} → {args.status[1]}")

    else:
        parser.print_help()
