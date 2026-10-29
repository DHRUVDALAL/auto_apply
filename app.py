import os
import time
import json
import random
import threading
import asyncio
from typing import Dict, Any, Optional
from fastapi import FastAPI, Request, UploadFile, File, Form, Query, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

import database
import validator
import mailer

app = FastAPI(title="HR Email Automation Engine - SAP BTP Outreach")

BASE_DIR = os.path.dirname(__file__)
STATIC_DIR = os.path.join(BASE_DIR, "static")
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
UPLOADS_DIR = os.path.join(BASE_DIR, "uploads")

os.makedirs(STATIC_DIR, exist_ok=True)
os.makedirs(TEMPLATES_DIR, exist_ok=True)
os.makedirs(UPLOADS_DIR, exist_ok=True)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=TEMPLATES_DIR)

# Initialize Database on startup
database.init_db()

# ----------------- CAMPAIGN RUNNER STATE -----------------
class CampaignRunner:
    def __init__(self):
        self.is_running = False
        self.is_paused = False
        self.should_stop = False
        self.thread: Optional[threading.Thread] = None

        self.total_in_batch = 0
        self.current_index = 0
        self.sent_count = 0
        self.failed_count = 0
        self.current_contact: Optional[Dict[str, Any]] = None
        self.countdown_seconds = 0
        self.is_dry_run = False
        self.sap_only = True
        self.delay_seconds = 15
        self.live_logs = []

    def log(self, level: str, message: str):
        entry = {
            "time": time.strftime("%H:%M:%S"),
            "level": level,
            "message": message
        }
        self.live_logs.append(entry)
        if len(self.live_logs) > 100:
            self.live_logs = self.live_logs[-100:]

    def get_status(self) -> Dict[str, Any]:
        progress = 0
        if self.total_in_batch > 0:
            progress = int((self.current_index / self.total_in_batch) * 100)
        return {
            "is_running": self.is_running,
            "is_paused": self.is_paused,
            "total_in_batch": self.total_in_batch,
            "current_index": self.current_index,
            "sent_count": self.sent_count,
            "failed_count": self.failed_count,
            "current_contact": self.current_contact,
            "countdown_seconds": self.countdown_seconds,
            "progress_percent": progress,
            "is_dry_run": self.is_dry_run,
            "sap_only": self.sap_only,
            "recent_logs": self.live_logs[-20:]
        }

    def start_batch(self, batch_size: int = 35, is_dry_run: bool = False, sap_only: bool = True, delay_seconds: int = 15) -> bool:
        if self.is_running:
            return False

        self.is_running = True
        self.is_paused = False
        self.should_stop = False
        self.total_in_batch = 0
        self.current_index = 0
        self.sent_count = 0
        self.failed_count = 0
        self.current_contact = None
        self.countdown_seconds = 0
        self.is_dry_run = is_dry_run
        self.sap_only = sap_only
        self.delay_seconds = delay_seconds

        self.thread = threading.Thread(
            target=self._run_campaign,
            args=(batch_size, delay_seconds),
            daemon=True
        )
        self.thread.start()
        return True

    def pause(self):
        if self.is_running and not self.is_paused:
            self.is_paused = True
            self.log("INFO", "⏸️ Campaign paused by user.")

    def resume(self):
        if self.is_running and self.is_paused:
            self.is_paused = False
            self.log("INFO", "▶️ Campaign resumed.")

    def stop(self):
        if self.is_running:
            self.should_stop = True
            self.is_paused = False
            self.log("WARNING", "⏹️ Campaign stop requested by user.")

    def _run_campaign(self, batch_size: int, delay_seconds: int = 15):
        try:
            self.log("INFO", f"🚀 Starting campaign batch of {batch_size} (Mode: {'SIMULATED DRY RUN' if self.is_dry_run else 'LIVE SMTP'}, Filter: {'SAP Targets Only' if self.sap_only else 'All Contacts'}, Pace: {delay_seconds}s)")

            # 1. Fetch pending contacts
            contacts = database.get_pending_contacts_for_batch(batch_size=batch_size, sap_only=self.sap_only)
            self.total_in_batch = len(contacts)

            if self.total_in_batch == 0:
                self.log("WARNING", "No pending contacts found matching criteria.")
                return

            settings = database.get_settings()
            template = database.get_active_template()

            if not template:
                self.log("ERROR", "No active email template found! Aborting.")
                return

            for idx, contact in enumerate(contacts):
                # Check stop
                if self.should_stop:
                    self.log("WARNING", "🛑 Campaign stopped by user.")
                    break

                # Handle pause
                while self.is_paused:
                    if self.should_stop:
                        break
                    time.sleep(0.5)

                if self.should_stop:
                    break

                self.current_index = idx + 1
                self.current_contact = contact

                hr_name = contact.get("full_name") or contact.get("first_name")
                company = contact.get("company_name")
                email = contact.get("email")

                # Strict duplicate prevention: check DB state before dispatching
                conn = database.get_connection()
                c_check = conn.cursor()
                c_check.execute("SELECT sending_status, sent_at FROM contacts WHERE id = ?", (contact["id"],))
                row = c_check.fetchone()
                conn.close()
                if row and row["sending_status"] == "SENT":
                    self.log("WARNING", f"⏭️ Skipping {email} - already sent previously.")
                    continue

                self.log("INFO", f"[{self.current_index}/{self.total_in_batch}] Sending to {hr_name} ({company}) - {email}")

                # Send or Simulate
                success, msg = mailer.send_email_message(
                    contact=contact,
                    template=template,
                    settings=settings,
                    is_dry_run=self.is_dry_run
                )

                status_str = "SUCCESS" if success else "FAILED"
                db_status = "SENT" if success else "FAILED"

                if success:
                    self.sent_count += 1
                    self.log("SUCCESS", f"✅ Delivered to {hr_name} at {company}")
                else:
                    self.failed_count += 1
                    self.log("ERROR", f"❌ Failed delivering to {email}: {msg}")

                # Record in DB & Log
                database.update_contact_status(contact["id"], db_status, None if success else msg)
                database.add_send_log(
                    contact_id=contact["id"],
                    email=email,
                    company=company,
                    subject=mailer.render_template(template["subject"], contact, settings),
                    status=status_str,
                    message=msg
                )

                # Pacing interval before next send (unless it's the last one)
                if idx < self.total_in_batch - 1 and not self.should_stop:
                    wait_time = 2 if self.is_dry_run else max(2, delay_seconds)
                    self.log("INFO", f"⏳ Pacing next email in {wait_time}s...")
                    
                    for s in range(wait_time, 0, -1):
                        if self.should_stop:
                            break
                        while self.is_paused:
                            if self.should_stop:
                                break
                            time.sleep(0.5)
                        self.countdown_seconds = s
                        time.sleep(1)

                    self.countdown_seconds = 0

            self.log("SUCCESS", f"🏁 Batch completed! Sent: {self.sent_count}, Failed: {self.failed_count}")
        except Exception as e:
            self.log("ERROR", f"Unexpected batch exception: {str(e)}")
        finally:
            self.is_running = False
            self.current_contact = None
            self.countdown_seconds = 0

runner = CampaignRunner()

# ----------------- VALIDATOR WORKER -----------------
validator_running = False
validator_progress = {"current": 0, "total": 0, "status": "idle"}

def run_validator_background():
    global validator_running, validator_progress
    validator_running = True
    validator_progress["status"] = "running"

    def progress_callback(cur, tot):
        validator_progress["current"] = cur
        validator_progress["total"] = tot

    try:
        res = validator.validate_all_contacts_batch(on_progress=progress_callback)
        validator_progress["status"] = "finished"
        validator_progress["result"] = res
    except Exception as e:
        validator_progress["status"] = f"error: {str(e)}"
    finally:
        validator_running = False

# ----------------- ROUTES -----------------
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/api/stats")
def api_stats():
    stats = database.get_stats()
    settings = database.get_settings()
    stats["daily_limit"] = int(settings.get("daily_limit", 35))
    stats["dry_run_mode"] = settings.get("dry_run_mode", "false") == "true"
    stats["active_resume"] = settings.get("active_resume_filename", "")
    return stats

@app.get("/api/contacts")
def api_contacts(
    search: str = "",
    status_filter: str = "ALL",
    sap_filter: str = "ALL",
    page: int = 1,
    limit: int = 50
):
    offset = (page - 1) * limit
    total = database.count_contacts(search=search, status_filter=status_filter, sap_filter=sap_filter)
    contacts = database.get_contacts(
        search=search,
        status_filter=status_filter,
        sap_filter=sap_filter,
        limit=limit,
        offset=offset
    )
    return {
        "contacts": contacts,
        "total": total,
        "page": page,
        "total_pages": (total + limit - 1) // limit if limit > 0 else 1
    }

@app.post("/api/contacts")
def api_add_contact(contact: Dict[str, Any]):
    ok = database.insert_contact(contact)
    if not ok:
        raise HTTPException(status_code=400, detail="Contact with this email already exists.")
    return {"success": True}

@app.delete("/api/contacts/{contact_id}")
def api_delete_contact(contact_id: int):
    database.delete_contact(contact_id)
    return {"success": True}

@app.post("/api/contacts/reset")
def api_reset_contacts():
    database.reset_all_contacts_status()
    runner.log("INFO", "Reset all contact sending statuses to PENDING.")
    return {"success": True}

@app.post("/api/validator/start")
def api_start_validator():
    global validator_running
    if validator_running:
        return {"status": "already_running"}
    threading.Thread(target=run_validator_background, daemon=True).start()
    return {"status": "started"}

@app.get("/api/validator/status")
def api_validator_status():
    global validator_running, validator_progress
    return {
        "is_running": validator_running,
        **validator_progress
    }

# Campaign Controller
@app.get("/api/campaign/status")
def api_campaign_status():
    return runner.get_status()

@app.get("/api/campaign/next-batch-preview")
def api_next_batch_preview(batch_size: int = 35, sap_only: bool = True):
    contacts = database.get_pending_contacts_for_batch(batch_size=batch_size, sap_only=sap_only)
    stats = database.get_stats()
    sent_count = stats["sent_today"]
    current_set_number = (sent_count // max(1, batch_size)) + 1
    return {
        "set_number": current_set_number,
        "contacts": contacts,
        "count": len(contacts),
        "pending_total": stats["pending_sap"] if sap_only else stats["pending"],
        "sent_today": sent_count
    }

@app.post("/api/campaign/start")
def api_campaign_start(payload: Dict[str, Any] = None):
    payload = payload or {}
    batch_size = int(payload.get("batch_size", 35))
    is_dry_run = bool(payload.get("dry_run", False))
    sap_only = bool(payload.get("sap_only", True))
    delay_seconds = int(payload.get("delay_seconds", 15))

    ok = runner.start_batch(batch_size=batch_size, is_dry_run=is_dry_run, sap_only=sap_only, delay_seconds=delay_seconds)
    if not ok:
        raise HTTPException(status_code=400, detail="A campaign is already currently running.")
    return {"success": True}

@app.post("/api/campaign/pause")
def api_campaign_pause():
    runner.pause()
    return {"success": True}

@app.post("/api/campaign/resume")
def api_campaign_resume():
    runner.resume()
    return {"success": True}

@app.post("/api/campaign/stop")
def api_campaign_stop():
    runner.stop()
    return {"success": True}

@app.get("/api/campaign/stream")
async def api_campaign_stream(request: Request):
    async def event_generator():
        while True:
            if await request.is_disconnected():
                break
            try:
                status = runner.get_status()
                yield f"data: {json.dumps(status)}\n\n"
            except Exception:
                break
            await asyncio.sleep(1.0)

    return StreamingResponse(event_generator(), media_type="text/event-stream")

# Templates
@app.get("/api/templates")
def api_get_templates():
    return database.get_templates()

@app.post("/api/templates")
def api_save_template(payload: Dict[str, Any]):
    tid = payload.get("id")
    name = payload.get("name", "").strip()
    subject = payload.get("subject", "").strip()
    body = payload.get("body", "").strip()

    if not name or not subject or not body:
        raise HTTPException(status_code=400, detail="Template name, subject, and body are required.")

    saved_id = database.save_template(tid, name, subject, body)
    return {"success": True, "id": saved_id}

@app.post("/api/templates/{template_id}/activate")
def api_activate_template(template_id: int):
    database.set_active_template(template_id)
    return {"success": True}

@app.delete("/api/templates/{template_id}")
def api_delete_template(template_id: int):
    database.delete_template(template_id)
    return {"success": True}

@app.post("/api/templates/preview")
def api_preview_template(payload: Dict[str, Any]):
    template_str_subject = payload.get("subject", "")
    template_str_body = payload.get("body", "")
    contact_id = payload.get("contact_id")

    settings = database.get_settings()
    contact = None
    if contact_id:
        conn = database.get_connection()
        c = conn.cursor()
        c.execute("SELECT * FROM contacts WHERE id = ?", (contact_id,))
        row = c.fetchone()
        conn.close()
        if row:
            contact = dict(row)

    if not contact:
        contact = {
            "first_name": "Roshan",
            "last_name": "Nair",
            "full_name": "Roshan Nair",
            "company_name": "Tata Digital",
            "designation": "Associate Director HR",
            "target_role": "SAP BTP Developer",
            "email": "nair.roshan@tcs.com"
        }

    rendered_subject = mailer.render_template(template_str_subject, contact, settings)
    rendered_plain = mailer.render_template(template_str_body, contact, settings)
    rendered_html = mailer.build_html_body(rendered_plain)

    return {
        "subject": rendered_subject,
        "body_plain": rendered_plain,
        "body_html": rendered_html,
        "contact": contact
    }

# Settings
@app.get("/api/settings")
def api_get_settings():
    s = database.get_settings()
    masked = s.copy()
    if masked.get("smtp_pass"):
        masked["smtp_pass_masked"] = "••••••••••••••••"
    return masked

@app.post("/api/settings")
def api_update_settings(payload: Dict[str, Any]):
    current = database.get_settings()
    if not payload.get("smtp_pass") and current.get("smtp_pass"):
        payload["smtp_pass"] = current["smtp_pass"]

    database.update_settings(payload)
    return {"success": True}

@app.post("/api/settings/test-connection")
def api_test_smtp(payload: Dict[str, Any] = None):
    settings = database.get_settings()
    if payload:
        for k, v in payload.items():
            if v:
                settings[k] = str(v)

    ok, msg = mailer.test_smtp_connection(settings)
    return {"success": ok, "message": msg}

@app.post("/api/settings/send-test")
def api_send_test_email(payload: Dict[str, Any]):
    recipient = payload.get("recipient", "").strip()
    if not recipient or "@" not in recipient:
        raise HTTPException(status_code=400, detail="Valid recipient email required.")

    settings = database.get_settings()
    template = database.get_active_template()
    if not template:
        raise HTTPException(status_code=400, detail="No active template found.")

    test_contact = {
        "first_name": "Dhruv",
        "last_name": "Dalal",
        "full_name": "Dhruv Dalal",
        "company_name": "Enterprise Cloud Test",
        "designation": "Talent Acquisition Leader",
        "target_role": "SAP BTP Developer / AI Engineer",
        "email": recipient
    }

    ok, msg = mailer.send_email_message(
        contact=test_contact,
        template=template,
        settings=settings,
        is_dry_run=False
    )

    return {"success": ok, "message": msg}

@app.post("/api/settings/upload-resume")
async def api_upload_resume(resume_file: UploadFile = File(...)):
    if not resume_file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF resumes are supported.")

    file_path = os.path.join(UPLOADS_DIR, resume_file.filename)
    with open(file_path, "wb") as f:
        f.write(await resume_file.read())

    size_kb = os.path.getsize(file_path) / 1024
    database.update_settings({"active_resume_filename": resume_file.filename})

    return {
        "success": True,
        "filename": resume_file.filename,
        "size_kb": round(size_kb, 1),
        "warning": "Size is over 300KB - consider compressing for maximum email deliverability" if size_kb > 300 else None
    }

@app.get("/api/logs")
def api_get_logs(limit: int = 50):
    return database.get_recent_logs(limit=limit)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=False)
