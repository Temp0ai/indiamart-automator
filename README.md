# Indiamart Inquiry Automator

Automated system for extracting, classifying, and following up on Indiamart business inquiries from Gmail — with WhatsApp Web automation. **No Google Cloud, no WhatsApp API tokens.**

## How It Works

```
Gmail (IMAP)  →  Extract & Classify  →  SQLite  →  Dashboard / WhatsApp Web
                                              ↓
                                        wa.me links + pywhatkit
```

## Quick Start

```bash
# 1. Install
pip install pywhatkit python-dotenv

# 2. Configure — create .env from template
cp .env.example .env
# Edit .env with your Gmail + app password

# 3. Generate Gmail App Password (one-time)
#    → https://myaccount.google.com/apppasswords
#    → Select "Mail" → Generate → Copy to .env

# 4. Fetch inquiries from Gmail
python extract.py

# 5. Preview follow-up messages (dry run)
python whatsapp.py --dry-run

# 6. Send via WhatsApp Web (opens browser tabs)
python whatsapp.py --send

# 7. Export contacts with wa.me click links
python whatsapp.py --export

# 8. Quick contact (call/SMS/WhatsApp for a specific inquiry)
python contact.py --list
python contact.py --id IND-20260517-abc12345 --action whatsapp

# 9. Launch web dashboard
python dashboard.py
# → http://localhost:8080
```

## Files

| File | What it does |
|---|---|
| `extract.py` | Fetch Gmail via IMAP, parse Indiamart emails, classify, store in SQLite |
| `whatsapp.py` | Send follow-ups via `pywhatkit` (WhatsApp Web) or generate `wa.me` links |
| `contact.py` | Quick contact helper — call/SMS/WhatsApp links for individual inquiries |
| `dashboard.py` | Web dashboard — stats, filters, one-click contact actions |
| `.env.example` | Environment config template |
| `PROMPT.md` | Master AI prompt with full system specification |

## Setup: Gmail IMAP

No Google Cloud project needed. Just an app password:

1. Go to [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
2. Select **Mail** and your device
3. Copy the 16-character password
4. Add to `.env`:
   ```
   GMAIL_USER=your.email@gmail.com
   GMAIL_APP_PASSWORD=xxxx-xxxx-xxxx-xxxx
   ```

## WhatsApp: No API Token Needed

Two modes available:

### Mode 1: pywhatkit (automated)
- Opens WhatsApp Web in your browser, types and sends the message
- You must be logged into WhatsApp Web in Chrome/Brave/Edge
- Runs with `--send` flag
- Respects 9 AM – 9 PM send window

### Mode 2: wa.me links (manual)
- Generates click-to-chat links for each contact
- Export to CSV with `--export`
- Click any link to open WhatsApp with pre-filled message
- Works on phone or desktop

### Contact helper
```bash
# List all inquiries with phone numbers
python contact.py --list

# Get call/SMS/WhatsApp links for one inquiry
python contact.py --id IND-20260517-abc12345

# Auto-open WhatsApp in browser
python contact.py --id IND-20260517-abc12345 --action whatsapp

# Log a completed call
python contact.py --log IND-20260517-abc12345

# Update status
python contact.py --status IND-20260517-abc12345 contacted
```

## Categories

Auto-classified by keyword matching:
- Vending Machines
- Tea/Coffee Premix
- Jaggery Products
- Nescafe Premix
- Bru Premix
- Society Premix
- Other (fallback)

## Safety & Compliance

- **Send window**: Messages only 9 AM – 9 PM
- **Daily limit**: 50/day default (configurable)
- **Dry run**: Preview everything before sending
- **wa.me links**: Click-to-chat is user-initiated, no ban risk
- **pywhatkit**: Uses WhatsApp Web, not unofficial API — lower risk but use responsibly
- **Opt-out**: Track "STOP" replies in call log
