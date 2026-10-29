import re
import dns.resolver
from typing import Tuple, Dict
from concurrent.futures import ThreadPoolExecutor
import database

EMAIL_REGEX = re.compile(
    r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
)

DISPOSABLE_DOMAINS = {
    "mailinator.com", "10minutemail.com", "guerrillamail.com", "tempmail.com",
    "throwawaymail.com", "yopmail.com", "trashmail.com", "getairmail.com"
}

# Cache domain -> (is_valid, reason)
DOMAIN_MX_CACHE: Dict[str, Tuple[bool, str]] = {}

def check_email_syntax(email: str) -> bool:
    if not email or len(email) > 254:
        return False
    return bool(EMAIL_REGEX.match(email.strip()))

def check_domain_mx(domain: str) -> Tuple[bool, str]:
    domain = domain.lower().strip()
    if domain in DOMAIN_MX_CACHE:
        return DOMAIN_MX_CACHE[domain]

    if domain in DISPOSABLE_DOMAINS:
        res = (False, "Disposable/temporary email provider")
        DOMAIN_MX_CACHE[domain] = res
        return res

    try:
        resolver = dns.resolver.Resolver()
        resolver.timeout = 3.0
        resolver.lifetime = 3.0
        records = resolver.resolve(domain, "MX")
        if len(records) > 0:
            res = (True, f"MX verified ({len(records)} mail servers found)")
        else:
            res = (False, "No MX records found")
    except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN):
        res = (False, "Domain does not exist or has no mail exchanger")
    except dns.resolver.Timeout:
        res = (True, "DNS timeout - domain likely exists, marked safe")
    except Exception as e:
        res = (False, f"DNS error: {str(e)[:50]}")

    DOMAIN_MX_CACHE[domain] = res
    return res

def validate_single_email(email: str) -> Tuple[str, str]:
    """
    Returns (status, details)
    status: 'VALID', 'INVALID', 'RISKY'
    """
    if not email or not check_email_syntax(email):
        return ("INVALID", "Invalid email syntax or format")

    parts = email.strip().split("@")
    if len(parts) != 2:
        return ("INVALID", "Malformed email address")

    domain = parts[1]
    is_valid_mx, reason = check_domain_mx(domain)

    if not is_valid_mx:
        return ("INVALID", reason)

    return ("VALID", reason)

def validate_all_contacts_batch(on_progress=None) -> Dict[str, int]:
    """
    Validates all UNVERIFIED contacts in the database.
    """
    conn = database.get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, email FROM contacts WHERE verification_status = 'UNVERIFIED'")
    contacts = [dict(r) for r in cursor.fetchall()]
    conn.close()

    total = len(contacts)
    if total == 0:
        return {"total": 0, "valid": 0, "invalid": 0}

    valid_count = 0
    invalid_count = 0

    def process_contact(c):
        nonlocal valid_count, invalid_count
        cid = c["id"]
        email = c["email"]
        status, details = validate_single_email(email)
        database.update_verification_status(cid, status, details)
        if status == "VALID":
            valid_count += 1
        else:
            invalid_count += 1

    # Multi-threaded validation for speed
    with ThreadPoolExecutor(max_workers=10) as executor:
        for idx, _ in enumerate(executor.map(process_contact, contacts)):
            if on_progress:
                on_progress(idx + 1, total)

    return {"total": total, "valid": valid_count, "invalid": invalid_count}
