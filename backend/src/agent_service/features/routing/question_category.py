from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

BUSINESS_CATEGORIES: tuple[str, ...] = (
    "loan_products_and_eligibility",
    "application_status_and_approval",
    "theft_claim_and_non_seizure",
    "disbursal_and_bank_credit",
    "profile_kyc_and_access",
    "credit_report_and_bureau",
    "foreclosure_and_closure",
    "emi_payments_and_charges",
    "collections_and_recovery",
    "fraud_and_security",
    "customer_support_channels",
    "other",
)

ROUTER_REASON_TO_CATEGORY: dict[str, str] = {
    "lead_intent_new_loan": "loan_products_and_eligibility",
    "eligibility_offer": "loan_products_and_eligibility",
    "loan_terms_rates": "loan_products_and_eligibility",
    "application_status_approval": "application_status_and_approval",
    "disbursal": "disbursal_and_bank_credit",
    "kyc_verification": "profile_kyc_and_access",
    "otp_login_app_tech": "profile_kyc_and_access",
    "emi_payment_reflecting": "emi_payments_and_charges",
    "nach_autodebit_bounce": "emi_payments_and_charges",
    "charges_fees_penalty": "emi_payments_and_charges",
    "statement_receipt": "emi_payments_and_charges",
    "foreclosure_partpayment": "foreclosure_and_closure",
    "collections_harassment": "collections_and_recovery",
    "fraud_security": "fraud_and_security",
    "customer_support": "customer_support_channels",
    "unknown": "other",
}

# Ordered from most specific/high-signal to broader buckets.
KEYWORD_CATEGORY_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "theft_claim_and_non_seizure",
        re.compile(
            r"\b(stolen|theft|theft/loss|insurance\s+claim|non[-\s]?repossession|non[-\s]?seizure)\b",
            re.I,
        ),
    ),
    (
        "fraud_and_security",
        re.compile(
            r"\b(fraud|scam|unauthorized|hack(?:ed|ing)?|loan\s+in\s+my\s+name|security\s+issue)\b",
            re.I,
        ),
    ),
    (
        "collections_and_recovery",
        re.compile(
            r"\b(collections?|recovery\s+agent|harass|stop\s+calls?|calling\s+me|calling\s+relatives?)\b",
            re.I,
        ),
    ),
    (
        "credit_report_and_bureau",
        re.compile(
            r"\b(credit\s+report|credit\s+score|bureau|cibil|dpd|write[-\s]?off|settled\s+remark)\b",
            re.I,
        ),
    ),
    (
        "foreclosure_and_closure",
        re.compile(
            r"\b(foreclos|prepay|part\s*payment|close\s+my\s+loan|closure\s+amount|noc)\b",
            re.I,
        ),
    ),
    (
        "disbursal_and_bank_credit",
        re.compile(
            r"\b(disburs|disbursement|approved\s+but\s+not\s+received|not\s+credited|money\s+not\s+received)\b",
            re.I,
        ),
    ),
    (
        "profile_kyc_and_access",
        re.compile(
            r"\b(kyc|otp|login|address\s+update|email\s+id|mobile\s+number|profile\s+update|contact\s+details)\b",
            re.I,
        ),
    ),
    (
        "emi_payments_and_charges",
        re.compile(
            r"\b(emi|payment\s+not\s+reflect|bounce\s+charge|nach|auto\s*debit|charges?|penalt|refund|due\s+date)\b",
            re.I,
        ),
    ),
    (
        "application_status_and_approval",
        re.compile(
            r"\b(application\s+status|status\s+check|approved|approval|rejected|pending\s+application)\b",
            re.I,
        ),
    ),
    (
        "loan_products_and_eligibility",
        re.compile(
            r"\b(apply\s+for\s+(a\s+)?(loan|personal\s+loan|home\s+loan|business\s+loan|vehicle\s+loan)|eligib|loan\s+products?)\b",
            re.I,
        ),
    ),
    (
        "customer_support_channels",
        re.compile(
            r"\b(callback|call\s+me|customer\s+care|toll[-\s]?free|whatsapp|support\s+number|help\s+desk)\b",
            re.I,
        ),
    ),
)


@dataclass(slots=True)
class QuestionCategoryResult:
    category: str
    confidence: float
    source: str


def map_router_reason_to_category(router_reason: Optional[str]) -> Optional[str]:
    if not router_reason:
        return None
    normalized = router_reason.strip().lower()
    return ROUTER_REASON_TO_CATEGORY.get(normalized)


def classify_question_category(
    question: Optional[str],
    router_reason: Optional[str] = None,
) -> QuestionCategoryResult:
    text = (question or "").strip()

    if text:
        for category, pattern in KEYWORD_CATEGORY_RULES:
            if pattern.search(text):
                return QuestionCategoryResult(
                    category=category,
                    confidence=0.9,
                    source="keyword",
                )

    mapped_router = map_router_reason_to_category(router_reason)
    if mapped_router and mapped_router != "other":
        return QuestionCategoryResult(
            category=mapped_router,
            confidence=0.75,
            source="router_reason",
        )

    if mapped_router == "other":
        return QuestionCategoryResult(
            category="other",
            confidence=0.35,
            source="router_reason",
        )

    return QuestionCategoryResult(
        category="other",
        confidence=0.0,
        source="fallback",
    )
