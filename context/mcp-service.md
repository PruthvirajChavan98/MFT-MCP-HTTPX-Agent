# MCP Service

## Overview
FastMCP SSE server at `:8050`. Session-aware tool proxy between LLM agent and MockFinTech CRM.

## Tools (12 active, 4 commented-out)

| Tool | Auth | Input | Output | CRM Endpoint |
|---|---|---|---|---|
| generate_otp | No | user_input (phone/app_id) | CSV | POST /otp/generate_new/ |
| validate_otp | No | otp | CSV | POST /otp/validate_new/ |
| is_logged_in | No | — | JSON dict | Redis check |
| dashboard_home | Yes | — | TOON | GET /home |
| loan_details | Yes | — | TOON | GET /loan/details/{app_id}/ |
| foreclosure_details | Yes | — | TOON | GET /loan/foreclosuredetails/{app_id}/ |
| overdue_details | Yes | — | TOON | GET /loan/overdue-details/{app_id}/ |
| noc_details | Yes | — | TOON | GET /loan/noc-details/{app_id}/ |
| repayment_schedule | Yes | — | TOON | GET /loan/repayment-schedule/{id}/ |
| download_welcome_letter | Yes | — | TOON | GET /download/welcome-letter/ |
| download_soa | Yes | start_date, end_date | TOON | POST /download/soa/ |
| logout | No | — | String | Redis delete |

## Key Pattern: `_touch()`
Every tool call writes `{_last_tool, _last_touch_ts}` to Redis session. Enables activity monitoring.

## Session Flow
```
generate_otp(phone) → Redis: {phone_number}
  ↓
validate_otp(otp) → CRM returns access_token → Redis: {access_token, app_id, user_details}
  ↓
loan_details() → reads bearer token from Redis → CRM API → TOON response