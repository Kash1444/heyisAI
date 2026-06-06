# app/services/sms_enricher.py
#
# Hybrid SMS enrichment engine.
# Layer 1: Regex — fast, free, deterministic. Covers ~70% of Indian SMS.
# Layer 2: LLM  — Gemini Flash with native JSON schema. Handles ambiguous cases.
#
# Called as a FastAPI BackgroundTask after every /sync/sms — never blocks the response.

import re
import json
from typing import Optional
from pydantic import BaseModel, Field

from app.core.database import SessionLocal
from app.models.sms_log import SmsLog


# ===========================================================================
# OUTPUT SCHEMA  (used by both regex and LLM paths)
# ===========================================================================

class SmsEnrichment(BaseModel):
    category: str = Field(
        description=(
            "One of: bank | ecommerce | travel | food | entertainment | otp | promo | personal | unknown"
        )
    )
    platform: Optional[str] = Field(
        default=None,
        description="Platform/brand name e.g. HDFC, Amazon, Swiggy, IRCTC. null if unknown."
    )
    amount: Optional[float] = Field(
        default=None,
        description="Monetary amount extracted from the SMS body in INR. null if none."
    )
    transaction_type: Optional[str] = Field(
        default=None,
        description="One of: debit | credit | refund. null if not a financial SMS."
    )
    entity_ref: Optional[str] = Field(
        default=None,
        description="Primary reference: order ID, PNR, UPI ref, ticket number. null if none."
    )
    status: Optional[str] = Field(
        default=None,
        description="One of: confirmed | shipped | delivered | cancelled | otp | failed. null if not applicable."
    )


# ===========================================================================
# REGEX LAYER
# ===========================================================================

# ── Sender/body keyword maps ─────────────────────────────────────────────────

_PLATFORM_MAP = {
    # Banks
    "HDFCBK": "HDFC", "HDFCBANK": "HDFC",
    "ICICIB": "ICICI", "ICICIBANK": "ICICI",
    "SBIINB": "SBI", "SBIBANK": "SBI",
    "AXISBK": "Axis Bank", "AXISBANK": "Axis Bank",
    "KOTAKB": "Kotak", "KOTAKBANK": "Kotak",
    "PNBSMS": "PNB", "PUNJABN": "PNB",
    "BOIIND": "BOI", "BOBIMT": "BOB",
    "INDUSB": "IndusInd",
    "PAYTMB": "Paytm Bank",
    # Payments
    "PAYTM": "Paytm", "PHONEPE": "PhonePe",
    "GPAY": "Google Pay", "GOOGLEPAY": "Google Pay",
    "AMAZONPAY": "Amazon Pay",
    # Ecommerce
    "AMAZON": "Amazon", "AMZNIN": "Amazon",
    "FKRTBZ": "Flipkart", "FLIPKRT": "Flipkart", "FLIPKART": "Flipkart",
    "MYNTRA": "Myntra", "MEESHO": "Meesho",
    "NYKAA": "Nykaa", "AJIO": "AJIO",
    "SNAPDL": "Snapdeal",
    # Travel
    "IRCTC": "IRCTC", "IRTCIN": "IRCTC",
    "INDIGO": "IndiGo", "6EAIRS": "IndiGo",
    "AIRINDIA": "Air India", "VISTARA": "Vistara",
    "MAKEMYTRIP": "MakeMyTrip", "MMTOUR": "MakeMyTrip",
    "GOIBIBO": "Goibibo", "REDBUS": "RedBus",
    "RAPIDO": "Rapido", "OLACABS": "Ola", "UBERIND": "Uber",
    # Food
    "SWIGGY": "Swiggy", "ZOMATO": "Zomato",
    "DOMINOS": "Domino's", "PIZZAHUT": "Pizza Hut",
    # Entertainment
    "BOOKMYSHOW": "BookMyShow", "BMSIND": "BookMyShow",
    "NETFLIX": "Netflix", "HOTSTAR": "Hotstar",
}

_BODY_PLATFORM_RE = re.compile(
    r"\b(HDFC|ICICI|SBI|Axis Bank|Kotak|PNB|IndusInd|Paytm|PhonePe|Google Pay|"
    r"Amazon|Flipkart|Myntra|Meesho|Nykaa|AJIO|Snapdeal|IRCTC|IndiGo|Air India|Vistara|"
    r"MakeMyTrip|Goibibo|RedBus|Rapido|Ola|Uber|Swiggy|Zomato|Domino|BookMyShow|Netflix|Hotstar)\b",
    re.IGNORECASE
)

_OTP_RE = re.compile(
    r"\b(OTP|One.Time.Password|verification code|passcode|PIN|Ref No\.?)\b"
    r".*?\b(\d{4,8})\b",
    re.IGNORECASE | re.DOTALL
)
_OTP_KEYWORD_RE = re.compile(
    r"\b(OTP|One.Time.Password|verification code|passcode)\b",
    re.IGNORECASE
)

_BANK_KEYWORD_RE = re.compile(
    r"\b(debited|credited|debit|credit|balance|A/c|Acct|account|UPI|NEFT|IMPS|RTGS|"
    r"transaction|transfer|INR|Rs\.?|₹|withdraw|deposit)\b",
    re.IGNORECASE
)
_AMOUNT_RE = re.compile(
    r"(?:INR|Rs\.?|₹)\s*([\d,]+(?:\.\d{1,2})?)",
    re.IGNORECASE
)
_DEBIT_RE = re.compile(r"\b(debited|debit|withdrawn|spent|paid)\b", re.IGNORECASE)
_CREDIT_RE = re.compile(r"\b(credited|credit|received|refunded|cashback)\b", re.IGNORECASE)
_REFUND_RE = re.compile(r"\b(refund|reversal|reversed)\b", re.IGNORECASE)

_ECOMMERCE_KEYWORD_RE = re.compile(
    r"\b(order|ordered|purchase|shipped|out for delivery|delivered|dispatch|tracking|invoice|shipment)\b",
    re.IGNORECASE
)
_ORDER_REF_RE = re.compile(
    r"\b(?:order(?:\s*id)?(?:\s*no)?|ORD)[:\s#]*([A-Z0-9\-]{6,20})\b",
    re.IGNORECASE
)
_ORDER_STATUS_RE = re.compile(
    r"\b(placed|confirmed|shipped|dispatched|out for delivery|delivered|cancelled|returned)\b",
    re.IGNORECASE
)

_TRAVEL_KEYWORD_RE = re.compile(
    r"\b(PNR|booking|ticket|flight|train|journey|travel|departure|arrival|seat|berth|passenger)\b",
    re.IGNORECASE
)
_PNR_RE = re.compile(
    r"\b(?:PNR|booking(?:\s*(?:id|no|ref))?)[:\s#]*([A-Z0-9]{6,12})\b",
    re.IGNORECASE
)
_TRAVEL_STATUS_RE = re.compile(
    r"\b(confirmed|CNF|waitlisted|RAC|cancelled|booked)\b",
    re.IGNORECASE
)

_FOOD_KEYWORD_RE = re.compile(
    r"\b(order|food|restaurant|meal|delivery|rider|arriving)\b",
    re.IGNORECASE
)

_ENTERTAINMENT_KEYWORD_RE = re.compile(
    r"\b(movie|show|ticket|cinema|theatre|multiplex|screen|seat)\b",
    re.IGNORECASE
)
_TICKET_REF_RE = re.compile(
    r"\b(?:ticket|booking)[:\s#]*([A-Z0-9\-]{6,16})\b",
    re.IGNORECASE
)

_PROMO_KEYWORD_RE = re.compile(
    r"\b(offer|sale|discount|cashback|% off|coupon|deal|win|prize|free|limited|hurry|exclusive)\b",
    re.IGNORECASE
)

_UPI_REF_RE = re.compile(
    r"\b(?:UPI\s*Ref(?:erence)?(?:\s*No)?)[:\s]*(\d{10,20})\b",
    re.IGNORECASE
)
_TXN_REF_RE = re.compile(
    r"\b(?:Ref(?:erence)?(?:\s*(?:id|no))?|Txn(?:\s*id)?)[:\s#]*([A-Z0-9]{8,20})\b",
    re.IGNORECASE
)


def _resolve_platform(sender: str, body: str) -> Optional[str]:
    """Check sender ID against known platform codes, then fall back to body scan."""
    sender_upper = sender.upper().replace("-", "").replace(".", "")
    for code, name in _PLATFORM_MAP.items():
        if code in sender_upper:
            return name
    match = _BODY_PLATFORM_RE.search(body)
    return match.group(1).title() if match else None


def _extract_amount(body: str) -> Optional[float]:
    match = _AMOUNT_RE.search(body)
    if match:
        try:
            return float(match.group(1).replace(",", ""))
        except ValueError:
            return None
    return None


def _extract_transaction_type(body: str) -> Optional[str]:
    if _REFUND_RE.search(body):
        return "refund"
    if _DEBIT_RE.search(body):
        return "debit"
    if _CREDIT_RE.search(body):
        return "credit"
    return None


def _extract_entity_ref(body: str) -> Optional[str]:
    for pattern in (_UPI_REF_RE, _ORDER_REF_RE, _PNR_RE, _TICKET_REF_RE, _TXN_REF_RE):
        m = pattern.search(body)
        if m:
            return m.group(1)
    return None


def regex_enrich(sender: str, body: str) -> Optional[SmsEnrichment]:
    """
    Fast regex-based enrichment.
    Returns SmsEnrichment if category is determined confidently, else None.
    """
    body_upper = body.upper()
    platform = _resolve_platform(sender, body)

    # ── OTP (highest priority — detect before anything else) ─────────────────
    if _OTP_KEYWORD_RE.search(body):
        otp_match = _OTP_RE.search(body)
        return SmsEnrichment(
            category="otp",
            platform=platform,
            status="otp",
            entity_ref=otp_match.group(2) if otp_match else None,
        )

    # ── Bank / Financial ──────────────────────────────────────────────────────
    is_bank_sender = any(code in sender.upper().replace("-", "") for code in
                         ["HDFCBK", "ICICIB", "SBIINB", "AXISBK", "KOTAKB", "INDUSB",
                          "PNBSMS", "BOIIND", "BOBIMT"])
    if is_bank_sender or (platform and platform in
                          ["HDFC", "ICICI", "SBI", "Axis Bank", "Kotak", "PNB", "IndusInd",
                           "Paytm", "PhonePe", "Google Pay", "Amazon Pay"]):
        if _BANK_KEYWORD_RE.search(body):
            return SmsEnrichment(
                category="bank",
                platform=platform,
                amount=_extract_amount(body),
                transaction_type=_extract_transaction_type(body),
                entity_ref=_extract_entity_ref(body),
            )

    # ── Ecommerce ─────────────────────────────────────────────────────────────
    if platform and platform in ["Amazon", "Flipkart", "Myntra", "Meesho", "Nykaa", "AJIO", "Snapdeal"]:
        status_match = _ORDER_STATUS_RE.search(body)
        return SmsEnrichment(
            category="ecommerce",
            platform=platform,
            amount=_extract_amount(body),
            entity_ref=_extract_entity_ref(body),
            status=status_match.group(1).lower() if status_match else None,
        )
    if _ECOMMERCE_KEYWORD_RE.search(body) and not _FOOD_KEYWORD_RE.search(body):
        status_match = _ORDER_STATUS_RE.search(body)
        if status_match or _ORDER_REF_RE.search(body):
            return SmsEnrichment(
                category="ecommerce",
                platform=platform,
                amount=_extract_amount(body),
                entity_ref=_extract_entity_ref(body),
                status=status_match.group(1).lower() if status_match else None,
            )

    # ── Travel ────────────────────────────────────────────────────────────────
    if platform and platform in ["IRCTC", "IndiGo", "Air India", "Vistara", "MakeMyTrip",
                                  "Goibibo", "RedBus", "Rapido", "Ola", "Uber"]:
        status_match = _TRAVEL_STATUS_RE.search(body)
        return SmsEnrichment(
            category="travel",
            platform=platform,
            amount=_extract_amount(body),
            entity_ref=_extract_entity_ref(body),
            status=status_match.group(1).lower() if status_match else None,
        )
    if _TRAVEL_KEYWORD_RE.search(body):
        status_match = _TRAVEL_STATUS_RE.search(body)
        return SmsEnrichment(
            category="travel",
            platform=platform,
            amount=_extract_amount(body),
            entity_ref=_extract_entity_ref(body),
            status=status_match.group(1).lower() if status_match else None,
        )

    # ── Food Delivery ─────────────────────────────────────────────────────────
    if platform and platform in ["Swiggy", "Zomato", "Domino's", "Pizza Hut"]:
        return SmsEnrichment(
            category="food",
            platform=platform,
            amount=_extract_amount(body),
            entity_ref=_extract_entity_ref(body),
            status="delivered" if "delivered" in body_upper else None,
        )

    # ── Entertainment ─────────────────────────────────────────────────────────
    if platform and platform in ["BookMyShow", "Netflix", "Hotstar"]:
        return SmsEnrichment(
            category="entertainment",
            platform=platform,
            amount=_extract_amount(body),
            entity_ref=_extract_entity_ref(body),
        )

    # ── Promo ─────────────────────────────────────────────────────────────────
    if _PROMO_KEYWORD_RE.search(body) and not _BANK_KEYWORD_RE.search(body):
        return SmsEnrichment(
            category="promo",
            platform=platform,
        )

    # ── Generic bank transaction (no known sender but clear keywords) ─────────
    if _BANK_KEYWORD_RE.search(body) and _AMOUNT_RE.search(body):
        return SmsEnrichment(
            category="bank",
            platform=platform,
            amount=_extract_amount(body),
            transaction_type=_extract_transaction_type(body),
            entity_ref=_extract_entity_ref(body),
        )

    # Unknown — escalate to LLM
    return None


# ===========================================================================
# LLM LAYER (called only when regex returns None)
# ===========================================================================

_LLM_PROMPT = """\
You are an SMS classifier and entity extractor for an Indian personal assistant app.
Classify the following SMS and extract structured data from it.

SMS body:
\"\"\"{body}\"\"\"

Sender ID: {sender}

Rules:
- category must be one of: bank | ecommerce | travel | food | entertainment | otp | promo | personal | unknown
- platform: brand/bank name (HDFC, Amazon, Swiggy, IRCTC, etc.) or null
- amount: numeric INR amount if present, else null
- transaction_type: debit | credit | refund | null
- entity_ref: order ID, PNR, UPI ref, ticket number, or null
- status: confirmed | shipped | delivered | cancelled | otp | failed | null
- Be conservative: if unsure, use "unknown" for category and null for optional fields.
"""


def llm_enrich(sender: str, body: str) -> SmsEnrichment:
    """
    LLM-based enrichment using Gemini Flash with native JSON schema enforcement.
    Only called when regex_enrich() returns None.
    """
    try:
        from app.services.llm.factory import get_structured_llm
        llm = get_structured_llm()
        prompt = _LLM_PROMPT.format(body=body[:500], sender=sender)
        result = llm.generate(prompt, schema=SmsEnrichment, temperature=0.0)
        print(f"[sms_enricher/llm] Enriched via LLM: category={result.category}, platform={result.platform}")
        return result
    except Exception as e:
        print(f"[sms_enricher/llm] LLM enrichment failed: {e}. Falling back to 'unknown'.")
        return SmsEnrichment(category="unknown")


# ===========================================================================
# HYBRID ENRICHMENT
# ===========================================================================

def hybrid_enrich(sender: str, body: str) -> SmsEnrichment:
    """
    Try regex first. If it returns None (category unknown), call the LLM.
    """
    result = regex_enrich(sender, body)
    if result is not None:
        return result
    print(f"[sms_enricher] Regex inconclusive for sender='{sender}' — delegating to LLM.")
    return llm_enrich(sender, body)


# ===========================================================================
# BACKGROUND TASK — runs after /sync/sms response is sent
# ===========================================================================

def enrich_pending_sms_task():
    """
    Background task that enriches newly-synced (enriched=False) SMS messages.
    Creates its own DB session — safe to call from FastAPI BackgroundTasks.
    Processes in batches of 50 to avoid overwhelming the LLM API.
    """
    db = SessionLocal()
    try:
        batch = (
            db.query(SmsLog)
            .filter(SmsLog.enriched == False)   # noqa: E712
            .order_by(SmsLog.timestamp_ms.desc())
            .limit(50)
            .all()
        )

        if not batch:
            return

        print(f"[sms_enricher] Processing {len(batch)} unenriched SMS messages...")

        for sms in batch:
            try:
                enrichment = hybrid_enrich(sms.number, sms.body)
                sms.category         = enrichment.category
                sms.platform         = enrichment.platform
                sms.amount           = enrichment.amount
                sms.transaction_type = enrichment.transaction_type
                sms.entity_ref       = enrichment.entity_ref
                sms.status           = enrichment.status
                sms.enriched         = True
            except Exception as e:
                print(f"[sms_enricher] Failed to enrich SMS id={sms.id}: {e}")
                sms.enriched = True   # mark done anyway to avoid infinite retry

        db.commit()
        print(f"[sms_enricher] Done. Enriched {len(batch)} SMS messages.")

    except Exception as e:
        db.rollback()
        print(f"[sms_enricher] Batch enrichment error: {e}")
    finally:
        db.close()
