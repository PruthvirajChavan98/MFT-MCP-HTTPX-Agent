/**
 * Tool catalogue — sourced verbatim from
 * backend/src/mcp_service/tool_descriptions.yaml (purpose lines)
 * + backend/src/mcp_service/{auth_api,core_api}.py (CRM endpoints)
 * + backend/src/agent_service/tools/mcp_manager.py:19-24 (PUBLIC_TOOLS).
 */

export type ToolTier = 'public' | 'session-gated'
export type ToolAuth = 'basic' | 'bearer' | 'none'

export interface ToolEntry {
  name: string
  purpose: string
  tier: ToolTier
  endpoint: string | null
  auth: ToolAuth
  sideEffect: boolean
}

export const TOOLS: readonly ToolEntry[] = [
  {
    name: 'generate_otp',
    purpose: "Generate and send an OTP to the user's WhatsApp number.",
    tier: 'public',
    endpoint: 'POST /mockfin-service/otp/generate_new/',
    auth: 'basic',
    sideEffect: true,
  },
  {
    name: 'validate_otp',
    purpose: 'Validate OTP for the current session and finalize authentication.',
    tier: 'public',
    endpoint: 'POST /mockfin-service/otp/validate_new/',
    auth: 'basic',
    sideEffect: true,
  },
  {
    name: 'is_logged_in',
    purpose: 'Check whether the current session is authenticated.',
    tier: 'public',
    endpoint: null,
    auth: 'none',
    sideEffect: false,
  },
  {
    name: 'search_knowledge_base',
    purpose: 'Search the product FAQ knowledge base for answers relevant to a user question.',
    tier: 'public',
    endpoint: null,
    auth: 'none',
    sideEffect: false,
  },
  {
    name: 'dashboard_home',
    purpose: 'Fetch dashboard summary for the authenticated session.',
    tier: 'session-gated',
    endpoint: 'GET /mockfin-service/home',
    auth: 'bearer',
    sideEffect: false,
  },
  {
    name: 'loan_details',
    purpose: 'Fetch detailed loan information for the authenticated session.',
    tier: 'session-gated',
    endpoint: 'GET /mockfin-service/loan/details/{app_id}/',
    auth: 'bearer',
    sideEffect: false,
  },
  {
    name: 'foreclosure_details',
    purpose: 'Fetch foreclosure and closure eligibility details.',
    tier: 'session-gated',
    endpoint: 'GET /mockfin-service/loan/foreclosuredetails/{app_id}/',
    auth: 'bearer',
    sideEffect: false,
  },
  {
    name: 'overdue_details',
    purpose: 'Fetch overdue summary for the current loan.',
    tier: 'session-gated',
    endpoint: 'GET /mockfin-service/loan/overdue-details/{app_id}/',
    auth: 'bearer',
    sideEffect: false,
  },
  {
    name: 'noc_details',
    purpose: 'Fetch No Objection Certificate (NOC) availability details.',
    tier: 'session-gated',
    endpoint: 'GET /mockfin-service/loan/noc-details/{app_id}/',
    auth: 'bearer',
    sideEffect: false,
  },
  {
    name: 'repayment_schedule',
    purpose: 'Fetch full repayment schedule for the current loan.',
    tier: 'session-gated',
    endpoint: 'GET /mockfin-service/loan/repayment-schedule/{ident}/',
    auth: 'bearer',
    sideEffect: false,
  },
  {
    name: 'download_welcome_letter',
    purpose: 'Generate a Welcome Letter for the currently selected loan.',
    tier: 'session-gated',
    endpoint: 'GET /mockfin-service/download/welcome-letter/',
    auth: 'bearer',
    sideEffect: true,
  },
  {
    name: 'download_soa',
    purpose: 'Generate a Statement of Account (SOA) for a given date range.',
    tier: 'session-gated',
    endpoint: 'POST /mockfin-service/download/soa/',
    auth: 'bearer',
    sideEffect: true,
  },
  {
    name: 'list_loans',
    purpose: "List all loans linked to the authenticated user's account.",
    tier: 'session-gated',
    endpoint: 'GET /mockfin-service/loans/',
    auth: 'bearer',
    sideEffect: false,
  },
  {
    name: 'select_loan',
    purpose: 'Set the active loan for the current session.',
    tier: 'session-gated',
    endpoint: null,
    auth: 'none',
    sideEffect: true,
  },
] as const

export const TOOL_COUNT = TOOLS.length
