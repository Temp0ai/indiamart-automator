#!/usr/bin/env python3
"""
WhatsApp Messenger — Uses pywhatkit to send via WhatsApp Web.
No API token needed. Just needs a browser logged into WhatsApp Web.

Install:  pip install pywhatkit
Usage:    python whatsapp.py --dry-run
          python whatsapp.py --send
          python whatsapp.py --export
"""

import os
import re
import json
import csv
import time
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

# ── pywhatkit import with fallback ───────────────────────────────────────────

PYWHATKIT_AVAILABLE = False
try:
    import pywhatkit as kit
    PYWHATKIT_AVAILABLE = True
except Exception:
    # pywhatkit fails on headless servers (needs X11 display)
    pass

if not PYWHATKIT_AVAILABLE:
    print("ℹ️  No display or pywhatkit unavailable — using wa.me link mode.")


# ── Config ───────────────────────────────────────────────────────────────────

DB_PATH = "./data/inquiries.db"
DAILY_LIMIT = int(os.environ.get("WA_DAILY_LIMIT", "50"))
SEND_WINDOW_START = "09:00"
SEND_WINDOW_END = "21:00"
COMPANY_NAME = os.environ.get("COMPANY_NAME", "Our Company")
COMPANY_PHONE = os.environ.get("COMPANY_PHONE", "+91-XXXXXXXXXX")


# ── Message Templates ────────────────────────────────────────────────────────

def render_thank_you(name: str, product: str) -> str:
    return (
        f"Hi {name} 👋\n\n"
        f"Thank you for your interest in {product}! "
        f"We received your inquiry and our team is already on it.\n\n"
        f"Here's what we offer:\n"
        f"✅ Premium quality products\n"
        f"✅ Pan-India delivery\n"
        f"✅ Competitive bulk pricing\n\n"
        f"Feel free to call us at {COMPANY_PHONE}.\n\n"
        f"— {COMPANY_NAME}"
    )


def render_follow_up_offer(name: str, product: str) -> str:
    return (
        f"Hi {name} 👋\n\n"
        f"Following up on your inquiry about {product}.\n\n"
        f"🎯 *Special for you:*\n"
        f"• 10% off on first order\n"
        f"• Free installation support\n"
        f"• 1-year warranty included\n\n"
        f"Would you like to schedule a quick call?\n\n"
        f"Reply with:\n"
        f"📞 \"CALL\" — we'll call you\n"
        f"📋 \"CATALOG\" — get full pricing\n"
        f"❌ \"STOP\" — unsubscribe"
    )


def render_reengagement(name: str, product: str, city: str = "your city") -> str:
    return (
        f"Hi {name},\n\n"
        f"Just checking in — are you still looking for {product}?\n\n"
        f"We recently supplied similar setups to clients in {city} "
        f"and they loved the results.\n\n"
        f"💡 *Limited offer:* Order this week and get free maintenance for 6 months.\n\n"
        f"Shall I reserve units for you?"
    )


# ── Follow-up Schedule ───────────────────────────────────────────────────────

FOLLOW_UP_SCHEDULE = [
    {"day": 0,  "label": "Thank You",      "renderer": render_thank_you},
    {"day": 2,  "label": "Offer",           "renderer": render_follow_up_offer},
    {"day": 10, "label": "Re-engagement",   "renderer": render_reengagement},
]


# ── Database Helpers ─────────────────────────────────────────────────────────

def get_due_inquiries() -> list[dict]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT * FROM inquiries
        WHERE status != 'closed' AND phone IS NOT NULL
        ORDER BY inquiry_date ASC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_follow_up_day(inquiry_id: str, new_day: int):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("UPDATE inquiries SET follow_up_day = ? WHERE id = ?", (new_day, inquiry_id))
    conn.commit()
    conn.close()


def mark_contacted(inquiry_id: str):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("UPDATE inquiries SET status = 'contacted' WHERE id = ?", (inquiry_id,))
    conn.commit()
    conn.close()


# ── WhatsApp Senders ─────────────────────────────────────────────────────────

def send_via_pywhatkit(phone: str, message: str, wait: int = 20) -> bool:
    """Send message via WhatsApp Web using pywhatkit."""
    if not PYWHATKIT_AVAILABLE:
        return False
    try:
        # pywhatkit expects phone with country code, no +
        clean_phone = phone.replace("+", "").replace("-", "").replace(" ", "")
        # Send with a small delay (pywhatkit opens browser tab)
        kit.sendwhatmsg_instantly(
            phone_no=clean_phone,
            message=message,
            wait_time=wait,       # seconds to wait before sending
            tab_close=True,
            close_time=3,         # seconds after sending before closing tab
        )
        return True
    except Exception as e:
        print(f"  ❌ pywhatkit error: {e}")
        return False


def generate_wa_me_link(phone: str, message: str) -> str:
    """Generate a wa.me click-to-chat link as fallback."""
    clean = phone.replace("+", "").replace("-", "").replace(" ", "")
    from urllib.parse import quote
    return f"https://wa.me/{clean}?text={quote(message)}"


def send_message(phone: str, message: str, dry_run: bool = False) -> dict:
    """Send a WhatsApp message. Returns status dict."""
    if dry_run:
        wa_link = generate_wa_me_link(phone, message)
        return {
            "status": "dry_run",
            "phone": phone,
            "link": wa_link,
            "preview": message[:150] + "..." if len(message) > 150 else message,
        }

    # Try pywhatkit first
    if PYWHATKIT_AVAILABLE:
        success = send_via_pywhatkit(phone, message)
        if success:
            return {"status": "sent", "phone": phone, "method": "pywhatkit"}
        # If pywhatkit fails, fall through to wa.me link

    # Fallback: generate wa.me link for manual sending
    wa_link = generate_wa_me_link(phone, message)
    return {
        "status": "link_generated",
        "phone": phone,
        "link": wa_link,
        "note": "Open this link to send manually",
    }


# ── Scheduler ────────────────────────────────────────────────────────────────

def is_within_send_window() -> bool:
    now = datetime.now().strftime("%H:%M")
    return SEND_WINDOW_START <= now <= SEND_WINDOW_END


def process_follow_ups(dry_run: bool = True):
    """Process all due follow-ups."""
    if not dry_run and not is_within_send_window():
        print(f"⏰ Outside send window ({SEND_WINDOW_START}–{SEND_WINDOW_END}). Use --dry-run to preview anyway.")
        return

    inquiries = get_due_inquiries()
    today = datetime.now().date()
    sent_count = 0
    results = []

    print(f"📋 {len(inquiries)} inquiries to process\n")

    for inq in inquiries:
        if sent_count >= DAILY_LIMIT:
            print(f"⚠️  Daily limit ({DAILY_LIMIT}) reached.")
            break

        # Parse inquiry date
        try:
            inq_date = datetime.fromisoformat(inq["inquiry_date"].split(" +")[0].split(" +")[0]).date()
        except (ValueError, AttributeError):
            try:
                inq_date = datetime.strptime(inq["inquiry_date"][:10], "%Y-%m-%d").date()
            except Exception:
                continue

        days_since = (today - inq_date).days
        name = inq["customer_name"] if inq["customer_name"] != "Unknown" else "there"
        product = inq["product_interest"][:80]

        # Find the right follow-up step
        for step in reversed(FOLLOW_UP_SCHEDULE):
            if days_since >= step["day"] and inq["follow_up_day"] < step["day"]:
                message = step["renderer"](name, product)
                phone = inq["phone"]

                print(f"📱 {inq['id']} | {phone} | {step['label']} (day {step['day']})")

                result = send_message(phone, message, dry_run=dry_run)
                results.append(result)

                if result["status"] == "dry_run":
                    print(f"   [DRY RUN] Would send:")
                    for line in message.split("\n")[:5]:
                        print(f"     {line}")
                    print(f"     ...")
                    print(f"   🔗 wa.me link: {result['link']}")
                elif result["status"] == "sent":
                    update_follow_up_day(inq["id"], step["day"])
                    if step["day"] == 0:
                        mark_contacted(inq["id"])
                    sent_count += 1
                    print(f"   ✅ Sent via {result.get('method', 'unknown')}")
                    time.sleep(5)  # Avoid spamming
                else:
                    print(f"   ⚠️  {result.get('note', 'Failed')}")

                print()
                break  # One follow-up per inquiry per run

    print(f"\n{'=' * 40}")
    print(f"Processed: {len(results)} | Sent: {sent_count}")
    return results


# ── Bulk Export ───────────────────────────────────────────────────────────────

def export_for_bulk(output: str = "./data/whatsapp_bulk.csv"):
    """Export contacts as CSV with wa.me links for manual bulk sending."""
    inquiries = get_due_inquiries()
    Path(output).parent.mkdir(parents=True, exist_ok=True)

    with open(output, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(["phone", "name", "product", "category", "city", "wa_me_link"])
        for inq in inquiries:
            if inq["phone"]:
                cats = json.loads(inq["categories"])[0] if inq["categories"] else "Other"
                clean = inq["phone"].replace("+", "")
                writer.writerow([
                    clean,
                    inq["customer_name"],
                    inq["product_interest"][:50],
                    cats,
                    inq["location"] or "",
                    f"https://wa.me/{clean}",
                ])

    print(f"✅ Exported {len(inquiries)} contacts to {output}")
    print(f"   Each row has a wa.me link you can click to send manually.")
    return output


# ── CLI ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Indiamart WhatsApp Follow-up (No API)")
    parser.add_argument("--dry-run", action="store_true", default=True, help="Preview without sending")
    parser.add_argument("--send", action="store_true", help="Actually send via WhatsApp Web")
    parser.add_argument("--export", action="store_true", help="Export CSV with wa.me links")
    parser.add_argument("--db", default=DB_PATH, help="Database path")

    args = parser.parse_args()

    if not Path(args.db).exists():
        print(f"❌ Database not found at {args.db}")
        print("   Run extract.py first to fetch inquiries.")
        exit(1)

    if args.export:
        export_for_bulk()
    else:
        dry = not args.send
        if dry:
            print("🔍 DRY RUN — No messages will be sent\n")
        else:
            print("🚀 LIVE MODE — Messages will be sent via WhatsApp Web\n")
        process_follow_ups(dry_run=dry)
