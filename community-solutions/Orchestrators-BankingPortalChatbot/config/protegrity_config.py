"""
Centralized Protegrity configuration and entity/data-element mappings.
🔑 SINGLE SOURCE OF TRUTH — no other file should define mappings or endpoints.
"""
from __future__ import annotations
import os

# ── Protegrity API endpoints ────────────────────────────────────────
CLASSIFY_URL = os.environ.get("CLASSIFY_URL", "http://localhost:8580/pty/data-discovery/v1.1/classify")
SGR_URL = os.environ.get("SGR_URL", "http://localhost:8581/pty/semantic-guardrail/v1.1/conversations/messages/scan")
SGR_PROCESSOR = os.environ.get("SGR_PROCESSOR", "financial")

# ── Entity mappings ─────────────────────────────────────────────────

ENTITY_TO_DATA_ELEMENT: dict[str, str] = {
    "PERSON": "string",
    "EMAIL_ADDRESS": "email",
    "PHONE_NUMBER": "phone",
    "SOCIAL_SECURITY_ID": "ssn",
    "SOCIAL_SECURITY_NUMBER": "ssn",
    "CREDIT_CARD": "ccn",
    "LOCATION": "address",
    "IP_ADDRESS": "address",
    "ORGANIZATION": "string",
    "URL": "address",
    "USERNAME": "string",
    "DATETIME": "datetime",
    "DOB": "datetime",
    "HEALTH_CARE_ID": "string",
    "BANK_ACCOUNT": "number",
    "ACCOUNT_NUMBER": "string",
    "TAX_ID": "ssn",
    "NATIONAL_ID": "ssn",
}

NAMED_ENTITY_MAP: dict[str, str] = {
    "EMAIL_ADDRESS": "email",
    "PERSON": "string",
    "PHONE_NUMBER": "phone",
    "SOCIAL_SECURITY_ID": "ssn",
    "SOCIAL_SECURITY_NUMBER": "ssn",
    "CREDIT_CARD": "ccn",
    "LOCATION": "address",
    "IP_ADDRESS": "address",
    "ORGANIZATION": "string",
    "URL": "address",
    "USERNAME": "string",
    "HEALTH_CARE_ID": "string",
    "DATETIME": "datetime",
    "BANK_ACCOUNT": "number",
    "TAX_ID": "ssn",
    "NATIONAL_ID": "ssn",
}

COMBINED_ENTITY_MAPPINGS: dict[str, str] = {
    "URL|EMAIL_ADDRESS": "email",
    "URL|EMAIL_ADDRESS|USERNAME": "email",
    "EMAIL_ADDRESS|URL": "email",
    "EMAIL_ADDRESS|USERNAME": "email",
    "URL|EMAIL_ADDRESS|EMAIL_ADDRESS": "email",
    "EMAIL_ADDRESS|URL|EMAIL_ADDRESS|EMAIL_ADDRESS": "email",
    "URL|EMAIL_ADDRESS|EMAIL_ADDRESS|EMAIL_ADDRESS": "email",
    "PERSON|LOCATION": "string",
    "CREDIT_CARD|PERSON": "ccn",
    "DATETIME|SOCIAL_SECURITY_ID": "ssn",
    "SOCIAL_SECURITY_ID|DATETIME": "ssn",
}

FIELD_PROTECTION_MAP: dict[str, tuple[str, str]] = {
    "name": ("PERSON", "string"),
    "email": ("EMAIL_ADDRESS", "email"),
    "phone": ("PHONE_NUMBER", "phone"),
    "ssn": ("SOCIAL_SECURITY_ID", "ssn"),
    "dob": ("DATETIME", "datetime"),
    "date_of_birth": ("DATETIME", "datetime"),
}

ACCOUNT_NUMBER_TAG = "ACCOUNT_NUMBER"
ACCOUNT_NUMBER_DE = "string"
CREDIT_CARD_TAG = "CREDIT_CARD"
CREDIT_CARD_DE = "ccn"


def get_data_element(entity_tag: str) -> str:
    return (
        ENTITY_TO_DATA_ELEMENT.get(entity_tag)
        or COMBINED_ENTITY_MAPPINGS.get(entity_tag)
        or "string"
    )
