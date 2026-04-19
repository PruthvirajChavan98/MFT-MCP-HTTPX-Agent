"""Admin enrollment-token flow — super-admin issues, new admin redeems.

See 05_admin_enrollment_tokens.sql for the schema and lifecycle. Public
(unauthenticated) endpoints live under /agent/admin/enrollment; the issuing
endpoint is gated by require_mfa_fresh + super-admin role.
"""
