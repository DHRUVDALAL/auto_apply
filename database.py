import sqlite3
import os
import csv
import re
from datetime import datetime
from typing import List, Dict, Any, Optional

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "email_automation.db")
MASTER_CSV_PATH = os.path.join(os.path.dirname(__file__), "data", "Updated_HR_List_2026.csv")

def get_connection():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=30.0)
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    conn.execute("PRAGMA busy_timeout = 30000;")
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    # Contacts table with SAP intelligence
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS contacts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sno INTEGER,
        first_name TEXT,
        last_name TEXT,
        full_name TEXT,
        email TEXT UNIQUE NOT NULL,
        company_name TEXT NOT NULL,
        designation TEXT,
        has_sap_roles TEXT DEFAULT 'No',
        sap_category TEXT,
        sap_details TEXT,
        app_recommendation TEXT,
        target_role TEXT DEFAULT 'SAP BTP Developer',
        verification_status TEXT DEFAULT 'UNVERIFIED',
        verification_details TEXT,
        sending_status TEXT DEFAULT 'PENDING',
        sent_at DATETIME,
        last_error TEXT,
        notes TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Templates table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS templates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        subject TEXT NOT NULL,
        body TEXT NOT NULL,
        is_active INTEGER DEFAULT 0,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Settings table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )
    """)

    # Send logs table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS send_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        contact_id INTEGER,
        email TEXT,
        company TEXT,
        subject TEXT,
        status TEXT,
        message TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Insert default settings tailored to Dhruv Dalal
    default_settings = {
        "smtp_host": "smtp.gmail.com",
        "smtp_port": "587",
        "smtp_user": "dhruvadalal.2004@gmail.com",
        "smtp_pass": "",
        "sender_name": "Dhruv Dalal",
        "sender_email": "dhruvadalal.2004@gmail.com",
        "daily_limit": "35",
        "delay_min_seconds": "45",
        "delay_max_seconds": "90",
        "dry_run_mode": "true",
        "active_resume_filename": "Dhruv_Dalal_Resume.pdf",
        "my_phone": "+91 7391919546",
        "my_linkedin": "https://linkedin.com/in/dhruvdalal1513",
        "my_portfolio": "https://github.com/DHRUVDALAL",
        "my_target_role": "SAP BTP Developer / AI Engineer",
        "batch_size": "35",
        "sap_only_filter": "true"
    }

    for k, v in default_settings.items():
        cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, v))

    # Insert default high-conversion templates for SAP BTP
    cursor.execute("SELECT COUNT(*) as count FROM templates")
    if cursor.fetchone()["count"] == 0:
        # Template 1: Dhruv Dalal - Official SAP BTP Outreach
        cursor.execute("""
        INSERT INTO templates (name, subject, body, is_active)
        VALUES (
            'Dhruv Dalal - Official SAP BTP Outreach',
            'Exploring SAP BTP Developer Opportunities - Dhruv Dalal',
            'Dear (first_name),\n\nI hope you’re doing well.\n\nI’m reaching out to explore potential opportunities in SAP BTP development within your organisation. I’m currently working as a BTP AI Engineer Intern at Abhiyanta India Solutions, where I contribute to enterprise application development using SAP BTP, SAP CAP, Node.js, and SAP S/4HANA Cloud integration.\n\nMy experience includes working on solutions for automated vendor reconciliation, production order execution, and cloud observability and cost governance. These projects have given me practical exposure to SAP technologies and enterprise business processes. I was also recognised with a Star Award for my technical contributions.\n\nI’m keen to continue growing in the SAP BTP ecosystem and would appreciate being considered for any suitable openings, including SAP BTP Developer or Associate SAP BTP Consultant roles.\n\nI’ve attached my resume for your reference. I would welcome the opportunity to discuss how my skills and experience could contribute to your team.\n\nThank you for your time and consideration.\n\nBest regards,\nDhruv Dalal\nBTP AI Engineer\nPhn no: +91 7391919546',
            1
        )
        """)

        # Template 2: Enterprise GCC / Client Target
        cursor.execute("""
        INSERT INTO templates (name, subject, body, is_active)
        VALUES (
            'Enterprise Digital Transformation & SAP GCC Pitch',
            '{{first_name}} - Quick question regarding SAP BTP / Cloud engineering at {{company_name}}',
            'Hi {{first_name}},\n\nI hope this email finds you well.\n\nI noticed {{company_name}}''s enterprise advancements in digital cloud architecture and supply chain operations. I wanted to reach out directly regarding potential openings for {{target_role}}.\n\nI bring specialized experience developing enterprise applications on SAP BTP, utilizing SAP CAP, SAP HANA Cloud, and automated Document AI workflows. Recently, I built automated shop-floor tracking platforms integrating S/4HANA Cloud with real-time WebSocket telemetry.\n\nI have attached my resume for your review. My LinkedIn profile ({{my_linkedin}}) and projects are also available for reference.\n\nIf {{company_name}} has open positions or if you could kindly guide me toward the engineering talent team, I would be deeply grateful.\n\nWarm regards,\n{{my_name}}\n{{my_phone}}',
            0
        )
        """)

        # Template 3: Gentle Follow-up
        cursor.execute("""
        INSERT INTO templates (name, subject, body, is_active)
        VALUES (
            'Polite Follow-up (4 Days Later)',
            'Following up on {{target_role}} opportunities at {{company_name}}',
            'Hi {{first_name}},\n\nHope you are having a great week.\n\nI wanted to follow up briefly on my previous email regarding {{target_role}} opportunities at {{company_name}}. I completely understand how demanding talent acquisition cycles are, so I just wanted to gently bring this to the top of your inbox.\n\nI remain very enthusiastic about {{company_name}}''s technical roadmap and would appreciate 5 minutes to connect at your convenience.\n\nBest regards,\n{{my_name}}\n{{my_phone}} | {{my_linkedin}}',
            0
        )
        """)

    conn.commit()

    # Check if contacts exist; if not, auto-import from MASTER_CSV_PATH
    cursor.execute("SELECT COUNT(*) as count FROM contacts")
    if cursor.fetchone()["count"] == 0 and os.path.exists(MASTER_CSV_PATH):
        import_master_csv(conn)

    conn.close()

def import_master_csv(conn):
    cursor = conn.cursor()
    with open(MASTER_CSV_PATH, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            raw_name = (row.get("Name") or "").strip()
            email = (row.get("Email") or "").strip().lower()
            company = (row.get("Company") or "").strip()
            job_title = (row.get("Job Title") or "").strip()
            has_sap = (row.get("Has SAP / SAP BTP Roles") or "No").strip()
            sap_cat = (row.get("SAP Practice & Category") or "").strip()
            sap_details = (row.get("SAP Relevance Details") or "").strip()
            recommendation = (row.get("Application Recommendation") or "").strip()
            sno_str = row.get("SNo") or "0"

            if not email or "@" not in email:
                continue

            # Parse First / Last Name
            name_parts = raw_name.split()
            first_name = name_parts[0].title() if name_parts else ""
            last_name = " ".join(name_parts[1:]).title() if len(name_parts) > 1 else ""

            # Target role tailored to SAP relevance
            target_role = "SAP BTP Developer / AI Engineer"
            if "SAP BTP Developer" in recommendation:
                target_role = "SAP BTP Developer"
            elif "SAP Consultant" in recommendation:
                target_role = "SAP Cloud / BTP Consultant"

            try:
                cursor.execute("""
                INSERT OR IGNORE INTO contacts (
                    sno, first_name, last_name, full_name, email, company_name, designation,
                    has_sap_roles, sap_category, sap_details, app_recommendation, target_role
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    int(sno_str) if sno_str.isdigit() else 0,
                    first_name,
                    last_name,
                    raw_name.title(),
                    email,
                    company,
                    job_title,
                    has_sap,
                    sap_cat,
                    sap_details,
                    recommendation,
                    target_role
                ))
            except Exception:
                pass
    conn.commit()

# Contacts queries
def get_contacts(
    search: str = "",
    status_filter: str = "ALL",
    sap_filter: str = "ALL",
    limit: int = 100,
    offset: int = 0
) -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    query = "SELECT * FROM contacts WHERE 1=1"
    params = []

    if search:
        query += " AND (full_name LIKE ? OR email LIKE ? OR company_name LIKE ? OR designation LIKE ? OR sap_category LIKE ?)"
        s = f"%{search}%"
        params.extend([s, s, s, s, s])

    if status_filter != "ALL":
        if status_filter in ["VALID", "INVALID", "RISKY", "UNVERIFIED"]:
            query += " AND verification_status = ?"
            params.append(status_filter)
        else:
            query += " AND sending_status = ?"
            params.append(status_filter)

    if sap_filter == "SAP_ONLY":
        query += " AND has_sap_roles = 'Yes'"
    elif sap_filter == "NON_SAP":
        query += " AND has_sap_roles = 'No'"
    elif sap_filter != "ALL":
        query += " AND sap_category = ?"
        params.append(sap_filter)

    # Sort high priority SAP first, then by ID
    query += " ORDER BY CASE WHEN has_sap_roles = 'Yes' THEN 0 ELSE 1 END, id ASC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    cursor.execute(query, params)
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows

def count_contacts(search: str = "", status_filter: str = "ALL", sap_filter: str = "ALL") -> int:
    conn = get_connection()
    cursor = conn.cursor()
    query = "SELECT COUNT(*) as count FROM contacts WHERE 1=1"
    params = []

    if search:
        query += " AND (full_name LIKE ? OR email LIKE ? OR company_name LIKE ? OR designation LIKE ? OR sap_category LIKE ?)"
        s = f"%{search}%"
        params.extend([s, s, s, s, s])

    if status_filter != "ALL":
        if status_filter in ["VALID", "INVALID", "RISKY", "UNVERIFIED"]:
            query += " AND verification_status = ?"
            params.append(status_filter)
        else:
            query += " AND sending_status = ?"
            params.append(status_filter)

    if sap_filter == "SAP_ONLY":
        query += " AND has_sap_roles = 'Yes'"
    elif sap_filter == "NON_SAP":
        query += " AND has_sap_roles = 'No'"
    elif sap_filter != "ALL":
        query += " AND sap_category = ?"
        params.append(sap_filter)

    cursor.execute(query, params)
    count = cursor.fetchone()["count"]
    conn.close()
    return count

def get_stats() -> Dict[str, Any]:
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) as total FROM contacts")
    total = cursor.fetchone()["total"]

    cursor.execute("SELECT COUNT(*) as sap_total FROM contacts WHERE has_sap_roles = 'Yes'")
    sap_total = cursor.fetchone()["sap_total"]

    cursor.execute("SELECT COUNT(*) as verified FROM contacts WHERE verification_status = 'VALID'")
    verified = cursor.fetchone()["verified"]

    cursor.execute("SELECT COUNT(*) as invalid FROM contacts WHERE verification_status = 'INVALID'")
    invalid = cursor.fetchone()["invalid"]

    cursor.execute("SELECT COUNT(*) as pending FROM contacts WHERE sending_status = 'PENDING'")
    pending = cursor.fetchone()["pending"]

    cursor.execute("SELECT COUNT(*) as pending_sap FROM contacts WHERE sending_status = 'PENDING' AND has_sap_roles = 'Yes'")
    pending_sap = cursor.fetchone()["pending_sap"]

    cursor.execute("SELECT COUNT(*) as sent FROM contacts WHERE sending_status = 'SENT'")
    sent = cursor.fetchone()["sent"]

    cursor.execute("SELECT COUNT(*) as failed FROM contacts WHERE sending_status = 'FAILED'")
    failed = cursor.fetchone()["failed"]

    cursor.execute("SELECT COUNT(*) as replied FROM contacts WHERE sending_status = 'REPLIED'")
    replied = cursor.fetchone()["replied"]

    # Sent today
    cursor.execute("SELECT COUNT(*) as sent_today FROM contacts WHERE sending_status = 'SENT' AND date(sent_at) = date('now')")
    sent_today = cursor.fetchone()["sent_today"]

    conn.close()

    return {
        "total": total,
        "sap_total": sap_total,
        "verified": verified,
        "invalid": invalid,
        "pending": pending,
        "pending_sap": pending_sap,
        "sent": sent,
        "failed": failed,
        "replied": replied,
        "sent_today": sent_today
    }

def get_pending_contacts_for_batch(batch_size: int = 35, sap_only: bool = True) -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    query = """
    SELECT * FROM contacts 
    WHERE sending_status = 'PENDING' AND verification_status != 'INVALID'
    """
    if sap_only:
        query += " AND has_sap_roles = 'Yes'"

    query += """
    ORDER BY CASE WHEN verification_status = 'VALID' THEN 0 ELSE 1 END, id ASC
    LIMIT ?
    """
    cursor.execute(query, (batch_size,))
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows

def update_contact_status(contact_id: int, sending_status: str, error_message: str = None):
    conn = get_connection()
    cursor = conn.cursor()
    if sending_status == "SENT":
        cursor.execute("UPDATE contacts SET sending_status = ?, sent_at = CURRENT_TIMESTAMP, last_error = NULL WHERE id = ?", (sending_status, contact_id))
    else:
        cursor.execute("UPDATE contacts SET sending_status = ?, last_error = ? WHERE id = ?", (sending_status, error_message, contact_id))
    conn.commit()
    conn.close()

def update_verification_status(contact_id: int, status: str, details: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE contacts SET verification_status = ?, verification_details = ? WHERE id = ?", (status, details, contact_id))
    conn.commit()
    conn.close()

def insert_contact(contact: Dict[str, Any]) -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
        INSERT INTO contacts (first_name, last_name, full_name, email, company_name, designation, target_role, has_sap_roles, sap_category, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            contact.get("first_name"),
            contact.get("last_name"),
            contact.get("full_name"),
            contact.get("email").strip().lower(),
            contact.get("company_name", "").strip(),
            contact.get("designation", "").strip(),
            contact.get("target_role", "SAP BTP Developer").strip(),
            contact.get("has_sap_roles", "Yes"),
            contact.get("sap_category", "Core SAP Partner"),
            contact.get("notes", "")
        ))
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        conn.close()
        return False

def delete_contact(contact_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM contacts WHERE id = ?", (contact_id,))
    conn.commit()
    conn.close()

def reset_all_contacts_status():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE contacts SET sending_status = 'PENDING', sent_at = NULL, last_error = NULL")
    conn.commit()
    conn.close()

def clear_all_contacts():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM contacts")
    cursor.execute("DELETE FROM send_logs")
    conn.commit()
    conn.close()

# Settings queries
def get_settings() -> Dict[str, str]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT key, value FROM settings")
    settings = {r["key"]: r["value"] for r in cursor.fetchall()}
    conn.close()
    return settings

def update_settings(settings_dict: Dict[str, str]):
    conn = get_connection()
    cursor = conn.cursor()
    for k, v in settings_dict.items():
        cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (k, str(v)))
    conn.commit()
    conn.close()

# Templates queries
def get_templates() -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM templates ORDER BY id ASC")
    templates = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return templates

def get_active_template() -> Optional[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM templates WHERE is_active = 1 LIMIT 1")
    row = cursor.fetchone()
    if not row:
        cursor.execute("SELECT * FROM templates ORDER BY id ASC LIMIT 1")
        row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def set_active_template(template_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE templates SET is_active = 0")
    cursor.execute("UPDATE templates SET is_active = 1 WHERE id = ?", (template_id,))
    conn.commit()
    conn.close()

def save_template(template_id: Optional[int], name: str, subject: str, body: str) -> int:
    conn = get_connection()
    cursor = conn.cursor()
    if template_id:
        cursor.execute("UPDATE templates SET name = ?, subject = ?, body = ? WHERE id = ?", (name, subject, body, template_id))
        tid = template_id
    else:
        cursor.execute("INSERT INTO templates (name, subject, body, is_active) VALUES (?, ?, ?, 0)", (name, subject, body))
        tid = cursor.lastrowid
    conn.commit()
    conn.close()
    return tid

def delete_template(template_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM templates WHERE id = ?", (template_id,))
    conn.commit()
    conn.close()

# Logs queries
def add_send_log(contact_id: int, email: str, company: str, subject: str, status: str, message: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO send_logs (contact_id, email, company, subject, status, message)
    VALUES (?, ?, ?, ?, ?, ?)
    """, (contact_id, email, company, subject, status, message))
    conn.commit()
    conn.close()

def get_recent_logs(limit: int = 50) -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM send_logs ORDER BY id DESC LIMIT ?", (limit,))
    logs = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return logs
