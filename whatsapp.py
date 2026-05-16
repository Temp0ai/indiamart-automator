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
import email.utils
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
COMPANY_NAME = os.environ.get("COMPANY_NAME", "Arihant Enterprises")
COMPANY_PHONE = os.environ.get("COMPANY_PHONE", "+917020134619")


# ── Message Templates ────────────────────────────────────────────────────────

# Category-specific templates with tailored messaging
CATEGORY_TEMPLATES = {
    "Vending Machines": {
        "thank_you": (
            "Hi {name} 👋\n\n"
            "Thank you for your interest in our vending machines! "
            "We specialize in automatic tea/coffee vending solutions.\n\n"
            "🏭 *What we offer:*\n"
            "✅ Fully automatic machines (2-lane, 4-lane, 6-lane)\n"
            "✅ Free installation & demo\n"
            "✅ Compatible with Nescafe, Bru & all major premixes\n"
            "✅ AMC & service support across India\n\n"
            "I'll share our catalog with pricing shortly.\n"
            "Meanwhile, call us at {phone} for a quick quote!\n\n"
            "— {company}"
        ),
        "offer": (
            "Hi {name} 👋\n\n"
            "Following up on your vending machine inquiry.\n\n"
            "🎯 *Special offer for you:*\n"
            "• ₹2,000 OFF on any machine this month\n"
            "• FREE first-year maintenance\n"
            "• 500 free premix sachets with first order\n\n"
            "Popular models:\n"
            "☕ 2-Lane: ₹18,999 | 4-Lane: ₹28,999 | 6-Lane: ₹42,999\n\n"
            "Want to see a demo? Reply:\n"
            "📹 \"DEMO\" — video walkthrough\n"
            "📞 \"CALL\" — we'll call you\n"
            "❌ \"STOP\" — unsubscribe"
        ),
        "reengagement": (
            "Hi {name},\n\n"
            "Still looking for a vending machine? 🤔\n\n"
            "We just delivered 5 machines to a tech park in {city} — "
            "they're loving the hassle-free coffee experience!\n\n"
            "💡 *Limited deal:* Order this week → free installation + 6-month AMC.\n\n"
            "Shall I reserve a unit for you?"
        ),
    },
    "Tea/Coffee Premix": {
        "thank_you": (
            "Hi {name} 👋\n\n"
            "Thanks for reaching out about our tea/coffee premixes! "
            "We supply premium quality instant mixes for offices, cafés & events.\n\n"
            "☕ *Our range:*\n"
            "✅ Classic Tea Premix — ₹350/kg\n"
            "✅ Strong Coffee Premix — ₹420/kg\n"
            "✅ Masala Chai Premix — ₹380/kg\n"
            "✅ Cardamom Tea Premix — ₹400/kg\n\n"
            "Bulk pricing available for 10kg+ orders.\n"
            "Call {phone} for samples!\n\n"
            "— {company}"
        ),
        "offer": (
            "Hi {name} 👋\n\n"
            "Special deal on premixes — just for you! 🎉\n\n"
            "📦 *Bulk offers:*\n"
            "• 10kg+ → 5% off\n"
            "• 25kg+ → 10% off + free delivery\n"
            "• 50kg+ → 15% off + free dispenser trial\n\n"
            "All premixes: 6-month shelf life | FSSAI certified\n\n"
            "Reply:\n"
            "📦 \"ORDER\" — place order\n"
            "🧪 \"SAMPLE\" — get free samples\n"
            "❌ \"STOP\" — unsubscribe"
        ),
        "reengagement": (
            "Hi {name},\n\n"
            "Still searching for the perfect premix? ☕\n\n"
            "We recently supplied 200kg to a corporate office in {city} — "
            "their employees rated it 4.8/5!\n\n"
            "🎁 *Come-back offer:* 20% off your next order + free sample kit.\n\n"
            "Shall I send over the catalog?"
        ),
    },
    "Jaggery Products": {
        "thank_you": (
            "Hi {name} 👋\n\n"
            "Thank you for your interest in our jaggery products! "
            "We supply organic, chemical-free jaggery in various forms.\n\n"
            "🍯 *Product range:*\n"
            "✅ Jaggery Powder — ₹80/kg\n"
            "✅ Jaggery Blocks — ₹90/kg\n"
            "✅ Liquid Jaggery — ₹100/kg\n"
            "✅ Organic Certified — ₹120/kg\n\n"
            "FSSAI certified | No chemicals | 12-month shelf life\n\n"
            "Samples available — call {phone}!\n\n"
            "— {company}"
        ),
        "offer": (
            "Hi {name} 👋\n\n"
            "Great news — jaggery prices just dropped! 🎉\n\n"
            "🏷️ *Bulk pricing:*\n"
            "• 100kg+ → ₹75/kg\n"
            "• 500kg+ → ₹68/kg\n"
            "• 1 ton+ → ₹62/kg (free delivery)\n\n"
            "Export quality packing available (1kg, 5kg, 25kg bags)\n\n"
            "Reply:\n"
            "📦 \"ORDER\" — place order\n"
            "🧪 \"SAMPLE\" — free sample\n"
            "❌ \"STOP\" — unsubscribe"
        ),
        "reengagement": (
            "Hi {name},\n\n"
            "Still looking for quality jaggery? 🍯\n\n"
            "We just shipped 2 tons to a food manufacturer in {city} — "
            "they've been our repeat customer for 3 years!\n\n"
            "💡 *This week only:* Order 500kg+ and get free delivery + quality certificate.\n\n"
            "Interested?"
        ),
    },
    "Nescafe Premix": {
        "thank_you": (
            "Hi {name} 👋\n\n"
            "Thanks for your interest in Nescafe premix! "
            "We're authorized distributors of Nescafe professional range.\n\n"
            "☕ *Nescafe range:*\n"
            "✅ Nescafe Classic Premix — ₹550/kg\n"
            "✅ Nescafe Cappuccino — ₹620/kg\n"
            "✅ Nescafe Latte — ₹600/kg\n"
            "✅ Nescafe Hot Chocolate — ₹680/kg\n\n"
            "Genuine products | Direct from Nestle | Bulk rates\n\n"
            "Call {phone} for pricing!\n\n"
            "— {company}"
        ),
        "offer": (
            "Hi {name} 👋\n\n"
            "Nescafe premix deals — just for you! 🎯\n\n"
            "🏷️ *Offers:*\n"
            "• 10kg+ → Free dispenser trial\n"
            "• 25kg+ → 8% off + free delivery\n"
            "• 50kg+ → 12% off + dedicated account manager\n\n"
            "All products: Nestle seal | 9-month shelf life\n\n"
            "Reply:\n"
            "📦 \"ORDER\" — place order\n"
            "📞 \"CALL\" — we'll call you\n"
            "❌ \"STOP\" — unsubscribe"
        ),
        "reengagement": (
            "Hi {name},\n\n"
            "Still interested in Nescafe premix? ☕\n\n"
            "We supply to 50+ offices in {city} — "
            "Nescafe is the #1 choice for corporate coffee!\n\n"
            "🎁 *Special:* First order 10% off + free cappuccino sample.\n\n"
            "Shall I book your order?"
        ),
    },
    "Bru Premix": {
        "thank_you": (
            "Hi {name} 👋\n\n"
            "Thank you for inquiring about Bru premix! "
            "We stock the complete Bru professional range.\n\n"
            "☕ *Bru products:*\n"
            "✅ Bru Gold Premix — ₹480/kg\n"
            "✅ Bru Instant Premix — ₹420/kg\n"
            "Bru Café Style — ₹520/kg\n"
            "✅ Bru Strong — ₹450/kg\n\n"
            "Best prices in the market | Same-day dispatch\n\n"
            "Call {phone} for bulk rates!\n\n"
            "— {company}"
        ),
        "offer": (
            "Hi {name} 👋\n\n"
            "Exclusive Bru premix offer! 🎉\n\n"
            "🏷️ *Deals:*\n"
            "• 5kg+ → Free Bru mug\n"
            "• 15kg+ → 7% off + free delivery\n"
            "• 30kg+ → 12% off + free dispenser cleaning kit\n\n"
            "HUL authorized distributor | Genuine products only\n\n"
            "Reply:\n"
            "📦 \"ORDER\" — place order\n"
            "🧪 \"SAMPLE\" — taste first\n"
            "❌ \"STOP\" — unsubscribe"
        ),
        "reengagement": (
            "Hi {name},\n\n"
            "Still thinking about Bru premix? ☕\n\n"
            "A café owner in {city} switched to Bru Gold last month — "
            "his customers love it!\n\n"
            "💡 *Come-back deal:* 15% off first 10kg + free shipping.\n\n"
            "Want to try?"
        ),
    },
    "Society Premix": {
        "thank_you": (
            "Hi {name} 👋\n\n"
            "Thanks for reaching out about society/housing premix solutions! "
            "We specialize in bulk supply for apartments & communities.\n\n"
            "🏢 *Society packages:*\n"
            "✅ Starter Kit: Machine + 10kg premix — ₹22,999\n"
            "✅ Monthly Pack: 25kg premix — ₹8,500\n"
            "✅ Annual Plan: 300kg — ₹90,000 (save 15%)\n\n"
            "We handle installation, training & monthly restocking.\n\n"
            "Call {phone} for a site visit!\n\n"
            "— {company}"
        ),
        "offer": (
            "Hi {name} 👋\n\n"
            "Special society bulk offer! 🏘️\n\n"
            "🎯 *Community deals:*\n"
            "• 50 flats+ → Dedicated vending setup\n"
            "• 100 flats+ → 10% off + free machine on 6-month plan\n"
            "• 200 flats+ → Custom pricing + 24/7 support\n\n"
            "We handle everything: install, maintain, restock.\n\n"
            "Reply:\n"
            "📞 \"VISIT\" — schedule site visit\n"
            "📋 \"PLAN\" — see all plans\n"
            "❌ \"STOP\" — unsubscribe"
        ),
        "reengagement": (
            "Hi {name},\n\n"
            "Still planning a vending setup for your society? 🏢\n\n"
            "We recently installed at a 300-flat society in {city} — "
            "residents love the 24/7 coffee access!\n\n"
            "🎁 *Limited:* First month premix FREE with any annual plan.\n\n"
            "Shall we schedule a visit?"
        ),
    },
    "Other": {
        "thank_you": (
            "Hi {name} 👋\n\n"
            "Thank you for your inquiry! We received your message and "
            "our team will get back to you shortly.\n\n"
            "We deal in:\n"
            "☕ Vending Machines\n"
            "☕ Tea/Coffee Premixes\n"
            "🍯 Jaggery Products\n"
            "🏢 Society Solutions\n\n"
            "Call us at {phone} for quick assistance.\n\n"
            "— {company}"
        ),
        "offer": (
            "Hi {name} 👋\n\n"
            "Following up on your inquiry.\n\n"
            "We'd love to help you with your requirements. "
            "Could you share more details about what you're looking for?\n\n"
            "📞 \"CALL\" — we'll call you\n"
            "📋 \"CATALOG\" — full product list\n"
            "❌ \"STOP\" — unsubscribe"
        ),
        "reengagement": (
            "Hi {name},\n\n"
            "Just checking in — do you still need help with your requirement?\n\n"
            "We're here whenever you're ready. Just reply to this message "
            "or call us at {phone}.\n\n"
            "— {company}"
        ),
    },
}


def get_category_template(category: str, template_type: str, name: str,
                          product: str, city: str = "your area") -> str:
    """Get a category-specific message template."""
    templates = CATEGORY_TEMPLATES.get(category, CATEGORY_TEMPLATES["Other"])
    template = templates.get(template_type, templates["thank_you"])
    return template.format(
        name=name,
        product=product,
        city=city,
        phone=COMPANY_PHONE,
        company=COMPANY_NAME,
    )


def render_thank_you(name: str, product: str, category: str = "Other",
                      city: str = "your area") -> str:
    return get_category_template(category, "thank_you", name, product, city)


def render_follow_up_offer(name: str, product: str, category: str = "Other",
                           city: str = "your area") -> str:
    return get_category_template(category, "offer", name, product, city)


def render_reengagement(name: str, product: str, category: str = "Other",
                        city: str = "your area") -> str:
    return get_category_template(category, "reengagement", name, product, city)


# ── Follow-up Schedule ───────────────────────────────────────────────────────

FOLLOW_UP_SCHEDULE = [
    {"day": 0,  "label": "Thank You",      "renderer": render_thank_you},
    {"day": 2,  "label": "Offer",           "renderer": render_follow_up_offer},
    {"day": 10, "label": "Re-engagement",   "renderer": render_reengagement},
]


# ── Database Helpers ─────────────────────────────────────────────────────────

def get_due_inquiries(categories: list[str] = None, has_phone: bool = False,
                      has_email: bool = False, has_name: bool = False,
                      real_only: bool = False) -> list[dict]:
    """Get inquiries with optional filters."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT * FROM inquiries
        WHERE status != 'closed'
        ORDER BY inquiry_date ASC
    """).fetchall()
    conn.close()

    results = [dict(r) for r in rows]

    # Filter by categories if specified
    if categories:
        categories_lower = [c.lower() for c in categories]
        filtered = []
        for inq in results:
            inq_cats = json.loads(inq.get("categories", "[]"))
            inq_cats_lower = [c.lower() for c in inq_cats]
            if any(c in inq_cats_lower for c in categories_lower):
                filtered.append(inq)
        results = filtered

    # Filter: must have phone number
    if has_phone:
        results = [r for r in results if r.get("phone")]

    # Filter: must have email (not just the sender's email)
    if has_email:
        results = [r for r in results if r.get("email") and "indiamart" not in (r.get("email") or "").lower()]

    # Filter: must have a real customer name (not system/generic)
    if has_name:
        junk_names = {"care", "details", "on", "enquiries", "below", "shelp",
                      "indiamart", "indiamart.com", "service number", "number",
                      "becoming", "plate", "requirement", "filled details",
                      "actual requirement", "the account under"}
        filtered = []
        for r in results:
            name = (r.get("customer_name") or "").strip().lower()
            # Must have a name, not be junk, and not be just a fragment
            if name and name not in junk_names and len(name) > 2:
                # Skip names that are clearly fragments from email templates
                if not any(name.startswith(j) for j in ["below to", "has viewed", "has sent",
                                                         "tried connecting", "disconnected"]):
                    filtered.append(r)
        results = filtered

    # Filter: real inquiries only (exclude system notifications, reminders, etc.)
    if real_only:
        system_keywords = ["allocated successfully", "catalog performance", "payment invoice",
                           "feedback", "advantage", "reminder for your", "buyleads allocated",
                           "alert mailer", "pns-emailer", "performance report",
                           "contact details updated", "registration for", "write a review",
                           "greetings from indiamart", "tenders for you"]
        filtered = []
        for r in results:
            interest = (r.get("product_interest") or "").lower()
            req = (r.get("requirement") or "").lower()[:200]
            # Skip if subject matches system patterns
            if any(kw in interest for kw in system_keywords):
                continue
            # Skip if body is mostly system content
            if any(kw in req for kw in ["buyers have viewed your catalog", "buyleads have been allocated",
                                         "greetings from indiamart", "catalog performance"]):
                continue
            filtered.append(r)
        results = filtered

    return results


def get_primary_category(inquiry: dict) -> str:
    """Get the primary category for an inquiry."""
    cats = json.loads(inquiry.get("categories", "[]"))
    return cats[0] if cats else "Other"


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


def process_follow_ups(dry_run: bool = True, categories: list[str] = None,
                       has_phone: bool = False, has_email: bool = False,
                       has_name: bool = False, real_only: bool = False):
    """Process all due follow-ups with optional filters."""
    if not dry_run and not is_within_send_window():
        print(f"⏰ Outside send window ({SEND_WINDOW_START}–{SEND_WINDOW_END}). Use --dry-run to preview anyway.")
        return

    inquiries = get_due_inquiries(categories=categories, has_phone=has_phone,
                                  has_email=has_email, has_name=has_name,
                                  real_only=real_only)
    today = datetime.now().date()
    sent_count = 0
    results = []

    cat_label = ", ".join(categories) if categories else "All"
    filters = []
    if has_phone: filters.append("📱 phone")
    if has_email: filters.append("📧 email")
    if has_name: filters.append("👤 name")
    if real_only: filters.append("✅ real")
    filter_label = f" | Filters: {', '.join(filters)}" if filters else ""

    print(f"📋 {len(inquiries)} inquiries [Categories: {cat_label}{filter_label}]\n")

    for inq in inquiries:
        if sent_count >= DAILY_LIMIT:
            print(f"⚠️  Daily limit ({DAILY_LIMIT}) reached.")
            break

        # Parse inquiry date
        try:
            # Try email date format: "Fri, 01 Mar 2026 10:36:16 +0000 (UTC)"
            date_str = inq["inquiry_date"]
            # Remove parenthetical timezone info
            clean_date = re.sub(r'\s*\([^)]*\)\s*$', '', date_str).strip()
            inq_date = email.utils.parsedate_to_datetime(clean_date).date()
        except Exception:
            try:
                inq_date = datetime.fromisoformat(inq["inquiry_date"].split(" +")[0]).date()
            except (ValueError, AttributeError):
                try:
                    inq_date = datetime.strptime(inq["inquiry_date"][:10], "%Y-%m-%d").date()
                except Exception:
                    continue

        days_since = (today - inq_date).days
        name = inq["customer_name"] if inq["customer_name"] != "Unknown" else "there"
        product = inq["product_interest"][:80]
        category = get_primary_category(inq)
        city = inq.get("location") or "your area"

        # Find the right follow-up step
        for step in reversed(FOLLOW_UP_SCHEDULE):
            if days_since >= step["day"] and inq["follow_up_day"] < step["day"]:
                message = step["renderer"](name, product, category, city)
                phone = inq["phone"]

                print(f"📱 {inq['id']} | {phone} | {step['label']} (day {step['day']}) | [{category}]")

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

def export_for_bulk(output: str = "./data/whatsapp_bulk.csv", categories: list[str] = None,
                    has_phone: bool = False, has_email: bool = False,
                    has_name: bool = False, real_only: bool = False):
    """Export contacts as CSV with wa.me links for manual bulk sending."""
    inquiries = get_due_inquiries(categories=categories, has_phone=has_phone,
                                  has_email=has_email, has_name=has_name,
                                  real_only=real_only)
    Path(output).parent.mkdir(parents=True, exist_ok=True)

    cat_label = ", ".join(categories) if categories else "All"
    filters = []
    if has_phone: filters.append("📱 phone")
    if has_email: filters.append("📧 email")
    if has_name: filters.append("👤 name")
    if real_only: filters.append("✅ real")
    filter_label = f" | Filters: {', '.join(filters)}" if filters else ""

    with open(output, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(["phone", "name", "email", "product", "category", "city", "wa_me_link"])
        for inq in inquiries:
            cats = json.loads(inq["categories"])[0] if inq["categories"] else "Other"
            clean = (inq["phone"] or "").replace("+", "")
            writer.writerow([
                clean,
                inq["customer_name"],
                inq.get("email") or "",
                inq["product_interest"][:50],
                cats,
                inq["location"] or "",
                f"https://wa.me/{clean}" if clean else "",
            ])

    print(f"✅ Exported {len(inquiries)} contacts to {output} [Categories: {cat_label}{filter_label}]")
    print(f"   Each row has a wa.me link you can click to send manually.")
    return output


def list_categories():
    """Show all categories with inquiry counts."""
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("""
        SELECT categories, COUNT(*) as cnt FROM inquiries
        WHERE phone IS NOT NULL AND status != 'closed'
        GROUP BY categories
    """).fetchall()
    conn.close()

    cat_counts = {}
    for cats_json, cnt in rows:
        cats = json.loads(cats_json) if cats_json else ["Other"]
        for c in cats:
            cat_counts[c] = cat_counts.get(c, 0) + cnt

    print("\n📂 Available Categories:")
    print("-" * 40)
    for cat, count in sorted(cat_counts.items(), key=lambda x: -x[1]):
        print(f"  {cat:<25} {count:>3} inquiries")
    print("-" * 40)
    print(f"  {'TOTAL':<25} {sum(cat_counts.values()):>3}")
    return cat_counts


# ── CLI ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Indiamart WhatsApp Follow-up (No API)")
    parser.add_argument("--dry-run", action="store_true", default=True, help="Preview without sending")
    parser.add_argument("--send", action="store_true", help="Actually send via WhatsApp Web")
    parser.add_argument("--export", action="store_true", help="Export CSV with wa.me links")
    parser.add_argument("--db", default=DB_PATH, help="Database path")
    parser.add_argument("--category", "-c", nargs="+",
                        help="Filter by category (e.g. --category 'Vending Machines' 'Bru Premix')")
    parser.add_argument("--list-categories", action="store_true", help="Show all categories with counts")
    parser.add_argument("--output", "-o", default="./data/whatsapp_bulk.csv",
                        help="Output CSV path for --export")

    # Quality filters
    parser.add_argument("--has-phone", action="store_true",
                        help="Only inquiries with phone numbers")
    parser.add_argument("--has-email", action="store_true",
                        help="Only inquiries with email addresses")
    parser.add_argument("--has-name", action="store_true",
                        help="Only inquiries with real customer names (filters out 'care', 'details', etc.)")
    parser.add_argument("--real-only", action="store_true",
                        help="Only real customer inquiries (filters out system notifications, reminders, etc.)")
    parser.add_argument("--ready", action="store_true",
                        help="Shorthand for --has-phone --has-name --real-only (ready to contact)")

    args = parser.parse_args()

    if not Path(args.db).exists():
        print(f"❌ Database not found at {args.db}")
        print("   Run extract.py first to fetch inquiries.")
        exit(1)

    # --ready is shorthand for --has-phone --has-name --real-only
    if args.ready:
        args.has_phone = True
        args.has_name = True
        args.real_only = True

    if args.list_categories:
        list_categories()
    elif args.export:
        export_for_bulk(output=args.output, categories=args.category,
                        has_phone=args.has_phone, has_email=args.has_email,
                        has_name=args.has_name, real_only=args.real_only)
    else:
        dry = not args.send
        if dry:
            print("🔍 DRY RUN — No messages will be sent\n")
        else:
            print("🚀 LIVE MODE — Messages will be sent via WhatsApp Web\n")
        process_follow_ups(dry_run=dry, categories=args.category,
                           has_phone=args.has_phone, has_email=args.has_email,
                           has_name=args.has_name, real_only=args.real_only)
