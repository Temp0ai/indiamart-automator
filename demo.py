#!/usr/bin/env python3
"""
Demo script — Populates sample Indiamart inquiries for testing.
Run this to see the dashboard and WhatsApp flow without live Gmail.
"""

import json
import sqlite3
import random
from datetime import datetime, timedelta
from pathlib import Path

DB_PATH = "./data/inquiries.db"

SAMPLE_INQUIRIES = [
    {
        "customer_name": "Rajesh Kumar",
        "phone": "+919876543210",
        "email": "rajesh.kumar@techcorp.in",
        "product_interest": "Automatic Tea Coffee Vending Machine for Office",
        "categories": ["Vending Machines", "Nescafe Premix"],
        "requirement": "Looking for 3 automatic vending machines for our Bangalore office. Need Nescafe and Bru premix compatible. Around 200 employees.",
        "quantity": "3",
        "location": "Bangalore",
    },
    {
        "customer_name": "Priya Sharma",
        "phone": "+919123456789",
        "email": "priya.sharma@greenfoods.com",
        "product_interest": "Organic Jaggery Powder Bulk Order",
        "categories": ["Jaggery Products"],
        "requirement": "Need organic jaggery powder in bulk for our food manufacturing unit. Monthly requirement of 500kg. Must have FSSAI certification.",
        "quantity": "500",
        "location": "Pune",
    },
    {
        "customer_name": "Amit Patel",
        "phone": "+919988776655",
        "email": "amit.patel@hospitalityplus.in",
        "product_interest": "Coffee Premix for Hotel Chain",
        "categories": ["Tea/Coffee Premix", "Nescafe Premix"],
        "requirement": "We run a chain of 12 budget hotels across Gujarat. Need coffee premix sachets for room service. Looking for competitive pricing on bulk order.",
        "quantity": "12000",
        "location": "Ahmedabad",
    },
    {
        "customer_name": "Sunita Devi",
        "phone": "+919765432100",
        "email": "sunita@societymgmt.com",
        "product_interest": "Premix Supply for Housing Society",
        "categories": ["Society Premix", "Tea/Coffee Premix"],
        "requirement": "Managing a large housing society with 400 flats. Want to set up a tea/coffee vending machine in the community hall. Need premix supply every month.",
        "quantity": "400",
        "location": "Mumbai",
    },
    {
        "customer_name": "Vikram Singh",
        "phone": "+919555666777",
        "email": "vikram@cafedaylight.com",
        "product_interest": "Bru Premix for Café",
        "categories": ["Bru Premix", "Tea/Coffee Premix"],
        "requirement": "Opening a new café in Jaipur. Need Bru coffee premix and tea premix. Want to start with 100 packs each and reorder monthly.",
        "quantity": "100",
        "location": "Jaipur",
    },
    {
        "customer_name": "Meera Krishnan",
        "phone": "+919444333222",
        "email": "meera.k@itpark.co.in",
        "product_interest": "Vending Machine with Multiple Premix Options",
        "categories": ["Vending Machines", "Nescafe Premix", "Bru Premix"],
        "requirement": "IT park with 2000+ employees. Need 5 vending machines with options for Nescafe, Bru, and tea. Interested in rental or purchase model.",
        "quantity": "5",
        "location": "Chennai",
    },
    {
        "customer_name": "Deepak Joshi",
        "phone": "+919333222111",
        "email": "deepak.j@organictrade.in",
        "product_interest": "Jaggery Blocks for Export",
        "categories": ["Jaggery Products"],
        "requirement": "Export house looking for premium quality jaggery blocks. Need 2 tons per month. Must meet export quality standards. Packing in 1kg and 5kg.",
        "quantity": "2000",
        "location": "Kolkata",
    },
    {
        "customer_name": "Ananya Reddy",
        "phone": "+919222111000",
        "email": "ananya@startuphub.tech",
        "product_interest": "Coffee Machine for Co-working Space",
        "categories": ["Vending Machines", "Tea/Coffee Premix"],
        "requirement": "Co-working space with 3 floors. Need a compact vending machine on each floor. Prefer contactless payment option if available.",
        "quantity": "3",
        "location": "Hyderabad",
    },
    {
        "customer_name": "Rohan Mehta",
        "phone": "+919111000999",
        "email": "rohan@factoryoutlet.com",
        "product_interest": "Nescafe Premix 1kg Packs",
        "categories": ["Nescafe Premix"],
        "requirement": "Retail chain looking to stock Nescafe premix. Need 1kg packs. Initial order of 200 packs. Regular monthly supply.",
        "quantity": "200",
        "location": "Delhi",
    },
    {
        "customer_name": "Kavitha Nair",
        "phone": "+919000999888",
        "email": "kavitha@ayurvedicwellness.in",
        "product_interest": "Organic Jaggery for Ayurvedic Products",
        "categories": ["Jaggery Products"],
        "requirement": "Ayurvedic wellness brand. Need organic certified jaggery as ingredient. Monthly 300kg. Must be free from chemicals and additives.",
        "quantity": "300",
        "location": "Kochi",
    },
    {
        "customer_name": "Suresh Agarwal",
        "phone": "+918899776655",
        "email": "suresh@panindiaretail.in",
        "product_interest": "Bulk Tea Premix for Canteen",
        "categories": ["Tea/Coffee Premix", "Society Premix"],
        "requirement": "Running canteens in 8 corporate offices across India. Need standardized tea premix supply. Looking for a single vendor for all locations.",
        "quantity": "8000",
        "location": "Mumbai",
    },
    {
        "customer_name": "Neha Gupta",
        "phone": "+918765432109",
        "email": "neha@eventmanagers.co",
        "product_interest": "Portable Vending Machine for Events",
        "categories": ["Vending Machines"],
        "requirement": "Event management company. Need portable vending machines for corporate events and weddings. Rental model preferred. Need 10 units.",
        "quantity": "10",
        "location": "Lucknow",
    },
]


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


def populate():
    conn = init_db()
    now = datetime.now()

    # Clear existing
    conn.execute("DELETE FROM inquiries")
    conn.commit()

    statuses = ["new", "new", "new", "contacted", "contacted", "qualified"]

    for i, sample in enumerate(SAMPLE_INQUIRIES):
        # Stagger dates over last 15 days
        days_ago = random.randint(0, 15)
        inquiry_date = (now - timedelta(days=days_ago)).isoformat()
        msg_id = f"demo-{random.randint(100000, 999999)}"
        inq_id = f"IND-{now.strftime('%Y%m%d')}-{msg_id[:8]}"

        conn.execute("""
            INSERT INTO inquiries
            (id, customer_name, phone, all_phones, email, product_interest,
             categories, requirement, quantity, location, inquiry_date,
             status, follow_up_day, source_message_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            inq_id,
            sample["customer_name"],
            sample["phone"],
            json.dumps([sample["phone"]]),
            sample["email"],
            sample["product_interest"],
            json.dumps(sample["categories"]),
            sample["requirement"],
            sample["quantity"],
            sample["location"],
            inquiry_date,
            random.choice(statuses),
            0,
            msg_id,
        ))

    conn.commit()
    conn.close()
    print(f"✅ Populated {len(SAMPLE_INQUIRIES)} sample inquiries into {DB_PATH}")
    print(f"   Run: python dashboard.py")


if __name__ == "__main__":
    populate()
