/**
 * Captured SSE transcripts from prod — sources:
 *   A: session 019de474-35f2-7ac2-aabb-684816321519 — natural login phrasing
 *      successfully routed through generate_otp.
 *   B: session 019de473-e657-7053-8b27-6b92d8fd3903 — the literal command-style
 *      prompt blocked by inline guard at agent_stream.py:467.
 *   C: representative bearer-token transcript for dashboard_home (composed —
 *      the structure is honest, the bearer token would not normally be safe to
 *      surface in user-facing docs).
 */

export interface SSEEvent {
  event: 'trace' | 'reasoning' | 'tool_call' | 'token' | 'cost' | 'done' | 'error'
  data: string
}

export const WALKTHROUGH_A: readonly SSEEvent[] = [
  { event: 'trace', data: '{"trace_id":"019de474-35f3-7c12-bf4b-e9036802471b"}' },
  { event: 'reasoning', data: '"User wants to log in. Provide mobile, generate OTP via generate_otp tool."' },
  {
    event: 'tool_call',
    data: '{"name":"generate_otp","tool_call_id":"019de474-3a3d-7c12-bf4b-e9036802471b","output":"status,phone_number,message\\r\\nOTP Sent,9876543210,OTP generated Successfully\\r\\n"}',
  },
  { event: 'token', data: '"OTP "' },
  { event: 'token', data: '"sent "' },
  { event: 'token', data: '"to "' },
  { event: 'token', data: '"9876543210."' },
  {
    event: 'cost',
    data: '{"total":0.000174,"model":"openai/gpt-oss-120b","provider":"groq","usage":{"input_tokens":482,"output_tokens":58}}',
  },
  { event: 'done', data: '{"status":"complete"}' },
] as const

export const WALKTHROUGH_B: readonly SSEEvent[] = [
  { event: 'trace', data: '{"trace_id":"cae0c42a-4f0e-49c2-843a-75bd1c55a2bf"}' },
  { event: 'error', data: '{"message":"Prompt violates security policy"}' },
  { event: 'done', data: '{"status":"complete"}' },
] as const

export const WALKTHROUGH_C: readonly SSEEvent[] = [
  { event: 'trace', data: '{"trace_id":"019de4a1-c7b8-7042-8a91-abc123def456"}' },
  { event: 'reasoning', data: '"User asks for loan dashboard. Session has bearer token. Call dashboard_home."' },
  {
    event: 'tool_call',
    data: '{"name":"dashboard_home","tool_call_id":"019de4a1-d123-7c12-bf4b-fedcba654321","output":"loan_number=LN-742199, status=active, principal=Rs.500000, next_due=2026-06-15, overdue=0"}',
  },
  { event: 'token', data: '"Here is "' },
  { event: 'token', data: '"your loan "' },
  { event: 'token', data: '"summary..."' },
  {
    event: 'cost',
    data: '{"total":0.000291,"model":"openai/gpt-oss-120b","provider":"groq","usage":{"input_tokens":612,"output_tokens":134}}',
  },
  { event: 'done', data: '{"status":"complete"}' },
] as const
