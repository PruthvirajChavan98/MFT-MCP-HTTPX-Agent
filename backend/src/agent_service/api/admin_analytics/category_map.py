"""Shared router_reason → category slug mapping for admin SQL queries.

Used by:
- ``admin_analytics/repo.py::fetch_traces_page`` — to filter by ``category``
  when the UI clicks "View Traces" on a QuestionCategories row.
- ``eval_read.py::question_types`` — to aggregate traces by category.

The mapping is an SQL ``CASE router_reason`` expression (not a Python dict)
because both consumers embed it directly in PostgreSQL queries. Keeping both
copies in sync by hand drifts — this module is the one-place-to-change.
"""

from __future__ import annotations

from typing import Final

# SQL expression that resolves to a canonical category slug given a
# ``router_reason`` value. Wrap in ``COALESCE(question_category, ...)`` at
# the callsite so an explicitly-set ``question_category`` wins when present.
#
# Slugs here must match the values emitted by the question-types aggregator
# and consumed by the QuestionCategories frontend link.
ROUTER_REASON_TO_CATEGORY_CASE: Final[str] = """
CASE router_reason
    WHEN 'lead_intent_new_loan'         THEN 'loan_products_and_eligibility'
    WHEN 'eligibility_offer'            THEN 'loan_products_and_eligibility'
    WHEN 'loan_terms_rates'             THEN 'loan_products_and_eligibility'
    WHEN 'application_status_approval'  THEN 'application_status_and_approval'
    WHEN 'disbursal'                    THEN 'disbursal_and_bank_credit'
    WHEN 'kyc_verification'             THEN 'profile_kyc_and_access'
    WHEN 'otp_login_app_tech'           THEN 'profile_kyc_and_access'
    WHEN 'emi_payment_reflecting'       THEN 'emi_payments_and_charges'
    WHEN 'nach_autodebit_bounce'        THEN 'emi_payments_and_charges'
    WHEN 'charges_fees_penalty'         THEN 'emi_payments_and_charges'
    WHEN 'statement_receipt'            THEN 'emi_payments_and_charges'
    WHEN 'foreclosure_partpayment'      THEN 'foreclosure_and_closure'
    WHEN 'collections_harassment'       THEN 'collections_and_recovery'
    WHEN 'fraud_security'               THEN 'fraud_and_security'
    WHEN 'customer_support'             THEN 'customer_support_channels'
    WHEN 'unknown'                      THEN 'other'
    ELSE NULL
END
""".strip()
