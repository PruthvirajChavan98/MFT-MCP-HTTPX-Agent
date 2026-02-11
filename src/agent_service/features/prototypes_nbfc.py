from typing import Dict, List

# =============================================================================
# Sentiment Prototypes (Reference Vectors)
# =============================================================================

SENTIMENT_PROTOTYPES: Dict[str, List[str]] = {
    "positive": [
        "thank you so much",
        "thanks for the help",
        "great service",
        "app is working perfectly",
        "love the quick approval",
        "received the money instantly, thanks",
        "good experience",
        "support was helpful",
        "excellent app",
        "mast hai",
        "badiya hai",
        "super smooth process",
    ],
    "negative": [
        "this is a scam",
        "fake app",
        "fraud company",
        "stop harassing me",
        "i will complain to rbi",
        "worst experience ever",
        "customer care is useless",
        "why did you deduct money",
        "cheaters",
        "bakwaas app",
        "gandu",
        "madarchod",
        "bhenchod",
        "bloody scammers",
        "i want to close my loan immediately",
        "stop calling my relatives",
    ],
    "neutral": [
        "what is my outstanding balance?",
        "how to pay emi?",
        "change my mobile number",
        "i want to foreclose",
        "what are the charges?",
        "when is the due date?",
        "is this app safe?",
        "how to apply for top up?",
        "need noc",
        "update my kyc",
        "payment not reflecting",
        "login issue",
        "otp not coming",
    ]
}

# =============================================================================
# Reason Prototypes (Intent Classification)
# =============================================================================

REASON_PROTOTYPES: Dict[str, List[str]] = {
    "lead_intent_new_loan": [
        "I want a loan",
        "apply for personal loan",
        "how to get money?",
        "need urgent cash",
        "loan limit increase",
        "top up loan available?",
        "eligibility check",
    ],
    "application_status_approval": [
        "check my application status",
        "why is it rejected?",
        "pending since yesterday",
        "when will it be approved?",
        "under review for long time",
        "kyc verified but no approval",
    ],
    "disbursal": [
        "money not credited",
        "loan approved but not received",
        "when will money come to bank?",
        "disbursement pending",
        "amount deducted but not credited",
    ],
    "emi_payment_reflecting": [
        "paid emi but not updated",
        "payment failed",
        "money cut from bank but showing due",
        "how to pay manually?",
        "paytm not working",
        "upi link for payment",
        "already paid",
    ],
    "foreclosure_partpayment": [
        "i want to close my loan",
        "foreclosure charges",
        "prepayment option",
        "close account permanently",
        "noc letter request",
        "pay full amount now",
    ],
    "charges_fees_penalty": [
        "why extra charges?",
        "processing fee is too high",
        "penalty charges explanation",
        "hidden charges",
        "why insurance fee deducted?",
        "bounce charges refund",
    ],
    "nach_autodebit_bounce": [
        "stop auto debit",
        "nach failed",
        "change bank for auto debit",
        "bounce charge why?",
        "cancel enach",
        "disable autopay",
    ],
    "kyc_verification": [
        "kyc rejected",
        "video kyc not working",
        "pan card upload error",
        "aadhaar verification failed",
        "selfie not uploading",
        "documents required",
    ],
    "otp_login_app_tech": [
        "otp not received",
        "cannot login",
        "app crashing",
        "invalid pin",
        "change mobile number",
        "login error",
        "forgot password",
    ],
    "statement_receipt": [
        "send loan statement",
        "need payment receipt",
        "repayment schedule",
        "send noc to email",
        "download statement",
    ],
    "collections_harassment": [
        "stop calling me",
        "agent is abusive",
        "harassment complaint",
        "calling my parents",
        "recovery agent threat",
        "do not call contact list",
    ],
    "fraud_security": [
        "this is fraud",
        "unauthorized transaction",
        "someone took loan in my name",
        "fake profile",
        "report scam",
        "account hacked",
    ],
    "customer_support": [
        "call me",
        "customer care number",
        "talk to human",
        "chat with agent",
        "support team email",
        "raise a ticket",
    ]
}
