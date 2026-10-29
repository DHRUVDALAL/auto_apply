# 🚀 SAP BTP HR Cold Email Outreach Automation Engine

A high-deliverability, smart cold email automation platform built specifically for **Dhruv Dalal** to reach HR leaders, talent acquisition heads, and engineering directors for **SAP BTP, SAP CAP, and Cloud Application** roles.

---

## 🌟 Key Capabilities

1. **Intelligent Targeting & Filtering**:
   - Master Database: **1,842 contacts** across India and global IT employers.
   - **229 High-Priority SAP & SAP BTP Targets**: Filtered to companies with active SAP practices (Tata Digital, NTT DATA, LTIMindtree, Hitachi Solutions, Dassault Systems, Crave InfoTech, Incture, etc.).
   - Prevents domain burning by avoiding irrelevant non-SAP startups.

2. **Enterprise Anti-Spam & Deliverability Guardrails**:
   - **Daily Volume Pacing**: Capped at **35 emails/day** during business hours.
   - **Human-like Jitter Intervals**: Randomized 45s–90s delays between dispatches to prevent rate-limit triggering.
   - **Spintax Subject Lines**: Rotates subject greetings (`{Inquiry|Application}`) and phrasing so Bayesian spam filters cannot fingerprint identical content.
   - **Pre-flight DNS MX Record Validation**: Verifies recipient mail server existence before dispatching.

3. **Active Resume Integration**:
   - Loaded with **Dhruv Dalal's 1-page Resume** (`uploads/Dhruv_Dalal_Resume.pdf`, 93 KB).
   - Under 250 KB to pass corporate firewall attachment size filters.

4. **Zero-Duplicate State Machine**:
   - Backed by SQLite (`data/email_automation.db`).
   - Tracks `PENDING`, `SENT`, `FAILED`, and `REPLIED` with timestamps so no HR ever receives duplicate emails.

5. **Simulated Dry Run vs. Live SMTP**:
   - Test full batch execution with zero real emails dispatched.
   - One-click **"Quick Test Email"** sends a sample to your personal inbox first.

---

## 🛠️ How to Run Locally

### 1. Start the Automation Server
Open your terminal in this directory and run:
```bash
python3 -m uvicorn app:app --host 127.0.0.1 --port 8000 --reload
```

### 2. Access the Dashboard
Open your browser and navigate to:
```
http://127.0.0.1:8000
```

---

## 🔐 How to Connect Your Gmail Account

1. Go to your [Google Account Security Settings](https://myaccount.google.com/security).
2. Ensure **2-Step Verification** is turned ON.
3. Under *2-Step Verification*, click on **App passwords**.
4. Create a new app password named `Outreach Engine`.
5. Copy the 16-character code (e.g., `xxxx xxxx xxxx xxxx`).
6. In the Outreach Dashboard, go to **Sender Settings**, paste the 16-character code into **Google App Password**, and click **Save SMTP Credentials**.
7. Click **🔌 Test Handshake** to confirm live connectivity!

---

## 📂 Project Structure

```
email_automation/
├── app.py                     # FastAPI server with background batch runner & SSE stream
├── database.py                # SQLite schema, SAP lead filtering, and transactional queries
├── mailer.py                  # SMTP handler, MIME multipart builder, attachment & spintax engine
├── validator.py               # Email syntax, disposable domain detection & DNS MX verification
├── static/
│   ├── css/style.css          # Glassmorphic dark theme design system
│   └── js/app.js              # Client-side state controller & real-time SSE listener
├── templates/
│   └── index.html             # Single-page executive outreach dashboard
├── uploads/
│   └── Dhruv_Dalal_Resume.pdf # Active 93 KB 1-page PDF resume
├── data/
│   ├── email_automation.db    # SQLite database with all 1,842 contacts
│   └── Updated_HR_List_2026.csv
└── requirements.txt
```
