# Indiamart Inquiry Automator — System Prompt & Design

## Master AI Prompt (200–500 words)

---

**ROLE:** You are an Indiamart Inquiry Processing Agent. Your job is to automate the full lifecycle of business inquiries — from Gmail extraction to WhatsApp follow-up.

**STEP 1 — EMAIL EXTRACTION.** Connect to Gmail via OAuth2 API. Filter emails where `from:` contains `indiamart.com` OR subject matches patterns like `"Enquiry for"`, `"Product Inquiry"`, `"Buyer Lead"`. For each matching email, extract:
- **Customer Name** — from email body or sender display name
- **Phone Number** — regex for Indian mobile formats (`+91XXXXXXXXXX`, `0XXXXXXXXXX`, `XXXXXXXXXX`)
- **Email ID** — from `reply-to` or body extraction
- **Product/Requirement** — parse subject line + first paragraph of body
- **Inquiry Date** — email timestamp
- **City/Location** — if mentioned in body
- **Quantity/Specs** — any numeric values near product keywords

Validate: phone must be 10 digits (with or without +91). Reject malformed entries. Store extracted data in a structured JSON/CSV record.

**STEP 2 — CLASSIFICATION.** Tag each inquiry into one or more categories based on keyword matching:
| Category | Keywords |
|---|---|
| Vending Machines | vending, coffee machine, automatic machine |
| Tea/Coffee Premix | premix, tea premix, coffee premix |
| Jaggery Products | jaggery, gur, organic sweetener |
| Nescafe Premix | nescafe, nescafe premix |
| Bru Premix | bru, bru premix |
| Society Premix | society, housing society, bulk premix |
| Other | fallback category |

Allow user-defined categories via a config file.

**STEP 3 — COMMUNICATION OPTIONS.** For each inquiry, present actionable options:
- 📞 **Call** — generate a `tel:` link and log the attempt
- 💬 **SMS** — draft a templated SMS and trigger via API (Twilio/MSG91)
- 📱 **WhatsApp** — send via WhatsApp Business API
- 📧 **Email Reply** — draft a professional response

**STEP 4 — BULK WHATSAPP COMPILATION.** Aggregate inquiries by category. For each group, generate a CSV with columns: `name, phone, email, product, category, inquiry_date, city`. This CSV is formatted for WhatsApp Business API bulk import or tools like WATI/AiSensy.

**STEP 5 — AI FOLLOW-UP GENERATION.** For each inquiry, generate contextual follow-up messages:
- **Immediate (Day 0):** Thank-you + product catalog link
- **Day 2:** Personalized offer based on their product interest
- **Day 5:** Case study or testimonial for their industry
- **Day 10:** Limited-time discount or bundle offer
- **Day 15:** "Still interested?" re-engagement

Each message must: be under 1024 characters, include the customer's first name, reference their specific product interest, and end with a clear CTA.

**STEP 6 — PROMOTIONAL CONTENT.** When user uploads product photos or promotional material, auto-generate:
- WhatsApp caption with emoji formatting
- Product highlights (3 bullet points max)
- Price indication (if configured)
- Contact/CTA footer

**CONSTRAINTS:**
- Never send WhatsApp messages outside 9 AM – 9 PM (recipient timezone)
- Rate-limit: max 250 unique messages/day on WhatsApp Business API
- All phone numbers stored encrypted at rest
- Opt-out mechanism: track "STOP" replies and blacklist those numbers
- Professional tone only — no spam language, ALL CAPS, or excessive punctuation

---

## Architecture Overview

```
┌─────────────┐     ┌──────────────┐     ┌─────────────────┐
│  Gmail API   │────▶│  Extraction  │────▶│  Classification  │
│  (OAuth2)    │     │  Engine      │     │  & Tagging       │
└─────────────┘     └──────────────┘     └────────┬────────┘
                                                   │
                    ┌──────────────┐                ▼
                    │  Dashboard   │◀────── ┌──────────────┐
                    │  (Web UI)    │        │  Data Store   │
                    └──────┬───────┘        │  (SQLite/CSV) │
                           │                └──────────────┘
           ┌───────────────┼───────────────┐
           ▼               ▼               ▼
    ┌────────────┐  ┌────────────┐  ┌────────────┐
    │  Call/SMS   │  │  WhatsApp  │  │  Follow-up  │
    │  Gateway    │  │  Biz API   │  │  Scheduler  │
    └────────────┘  └────────────┘  └────────────┘
```

## Sample Extracted Data

```json
{
  "id": "IND-2026-0042",
  "customer_name": "Rajesh Kumar",
  "phone": "+919876543210",
  "email": "rajesh.kumar@example.com",
  "product_interest": "Automatic Tea Coffee Vending Machine",
  "category": "Vending Machines",
  "requirement": "Looking for 3 machines for office in Bangalore, need Nescafe and Bru premix compatible",
  "quantity": "3 units",
  "location": "Bangalore",
  "inquiry_date": "2026-05-16T14:30:00+05:30",
  "status": "new",
  "follow_up_day": 0
}
```

## WhatsApp Message Templates

### Template 1 — Immediate Thank You
```
Hi {{1}} 👋

Thank you for your interest in {{2}}! We received your inquiry and our team is already on it.

Here's what we offer:
✅ Premium quality products
✅ Pan-India delivery
✅ Competitive bulk pricing

I'll share our catalog shortly. Meanwhile, feel free to call us at +91-XXXXXXXXXX.

— {{3}} | [Company Name]
```

### Template 2 — Follow-up Offer (Day 2)
```
Hi {{1}} 👋

Following up on your inquiry about {{2}}.

🎯 *Special for you:*
• 10% off on first order
• Free installation support
• 1-year warranty included

Would you like to schedule a quick call to discuss your requirements?

Reply with:
📞 "CALL" — we'll call you
📋 "CATALOG" — get full pricing
❌ "STOP" — unsubscribe
```

### Template 3 — Re-engagement (Day 10)
```
Hi {{1}},

Just checking in — are you still looking for {{2}}?

We recently supplied similar setups to [Client Name] in {{3}} and they loved the results.

💡 *Limited offer:* Order this week and get free maintenance for 6 months.

Shall I reserve units for you?

— [Company Name]
```

## Gmail API Integration Notes

1. **OAuth2 Setup:** Create a Google Cloud project → enable Gmail API → generate OAuth2 credentials → store `credentials.json` securely
2. **Scopes Required:** `https://www.googleapis.com/auth/gmail.readonly`
3. **Polling Strategy:** Use Gmail push notifications (Google Pub/Sub) for real-time processing, or poll every 5 minutes
4. **Query Filter:** `from:(indiamart.com) subject:(enquiry OR inquiry OR "product enquiry") newer_than:1d`
5. **Rate Limits:** Gmail API allows 250 quota units/second — batch requests where possible

## WhatsApp Business API Integration Notes

1. **Official API:** Register at [business.whatsapp.com](https://business.whatsapp.com) — requires Meta Business verification
2. **Alternative Providers:** WATI, AiSensy, Twilio WhatsApp, Gupshup — for simplified integration
3. **Template Pre-approval:** All outbound templates must be pre-approved by Meta
4. **Session Messaging:** Within 24h of customer's last message, free-form messages are allowed
5. **Compliance:** Maintain opt-out list, respect rate limits, no unsolicited marketing to non-opted-in numbers

## Configuration File

```yaml
# config.yaml
gmail:
  credentials_path: "./credentials.json"
  poll_interval_minutes: 5
  query_filter: "from:(indiamart.com) subject:(enquiry OR inquiry)"

categories:
  - name: "Vending Machines"
    keywords: ["vending", "coffee machine", "automatic machine", "dispenser"]
  - name: "Tea/Coffee Premix"
    keywords: ["premix", "tea premix", "coffee premix", "instant mix"]
  - name: "Jaggery Products"
    keywords: ["jaggery", "gur", "organic sweetener"]
  - name: "Nescafe Premix"
    keywords: ["nescafe", "nestle premix"]
  - name: "Bru Premix"
    keywords: ["bru", "bru premix", "hcc premix"]
  - name: "Society Premix"
    keywords: ["society", "housing society", "apartment", "bulk"]

whatsapp:
  provider: "wati"  # or "twilio", "aisensy", "gupshup"
  api_key: "${WHATSAPP_API_KEY}"
  phone_number_id: "${WHATSAPP_PHONE_ID}"
  daily_limit: 250
  send_window_start: "09:00"
  send_window_end: "21:00"

follow_up:
  schedule:
    - day: 0
      template: "thank_you"
    - day: 2
      template: "offer"
    - day: 5
      template: "testimonial"
    - day: 10
      template: "discount"
    - day: 15
      template: "reengagement"

storage:
  database: "./data/inquiries.db"
  export_format: "csv"
```

## Security & Privacy Checklist

- [ ] Gmail OAuth2 tokens stored encrypted, refreshed automatically
- [ ] Phone numbers encrypted at rest (AES-256)
- [ ] No PII logged to console or external services
- [ ] Opt-out list maintained and checked before every send
- [ ] API keys stored in environment variables, never in code
- [ ] All outbound messages logged with timestamp and status
- [ ] Data retention policy: purge inquiries older than 90 days unless marked "active"
- [ ] HTTPS-only for all API communications
