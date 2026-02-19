// API Configuration - Replace with your actual backend URL
export const API_BASE_URL = "http://localhost:8000";

// Headers helper
export function getHeaders(adminKey?: string, openRouterKey?: string) {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (adminKey) headers["X-Admin-Key"] = adminKey;
  if (openRouterKey) headers["X-OpenRouter-Key"] = openRouterKey;
  return headers;
}

// ===== MOCK DATA =====
export const mockAnalyticsOverview = {
  total_sessions: 1247,
  active_sessions: 38,
  total_queries: 15832,
  avg_response_time_ms: 1240,
  total_cost_usd: 342.87,
  avg_cost_per_query: 0.0217,
  uptime_hours: 720,
  guardrail_triggers: 89,
  positive_feedback_pct: 87.3,
  faq_count: 256,
};

export const mockSessions = [
  { session_id: "sess_a1b2c3", created_at: "2026-02-19T08:12:00Z", queries: 24, total_cost: 0.52, model: "deepseek/deepseek-r1", status: "active" },
  { session_id: "sess_d4e5f6", created_at: "2026-02-19T07:45:00Z", queries: 12, total_cost: 0.28, model: "openai/gpt-4o", status: "active" },
  { session_id: "sess_g7h8i9", created_at: "2026-02-18T22:30:00Z", queries: 45, total_cost: 1.12, model: "deepseek/deepseek-r1", status: "idle" },
  { session_id: "sess_j0k1l2", created_at: "2026-02-18T19:00:00Z", queries: 8, total_cost: 0.15, model: "anthropic/claude-3.5-sonnet", status: "idle" },
  { session_id: "sess_m3n4o5", created_at: "2026-02-18T15:20:00Z", queries: 67, total_cost: 2.34, model: "openai/gpt-4o", status: "closed" },
  { session_id: "sess_p6q7r8", created_at: "2026-02-18T12:00:00Z", queries: 33, total_cost: 0.89, model: "deepseek/deepseek-r1", status: "closed" },
  { session_id: "sess_s9t0u1", created_at: "2026-02-17T10:30:00Z", queries: 15, total_cost: 0.41, model: "anthropic/claude-3.5-sonnet", status: "closed" },
  { session_id: "sess_v2w3x4", created_at: "2026-02-17T08:00:00Z", queries: 92, total_cost: 3.67, model: "openai/gpt-4o", status: "closed" },
];

export const mockCostHistory = [
  { date: "2026-02-13", cost: 42.5, queries: 1890 },
  { date: "2026-02-14", cost: 38.2, queries: 1720 },
  { date: "2026-02-15", cost: 51.3, queries: 2340 },
  { date: "2026-02-16", cost: 29.8, queries: 1340 },
  { date: "2026-02-17", cost: 55.1, queries: 2510 },
  { date: "2026-02-18", cost: 67.4, queries: 3120 },
  { date: "2026-02-19", cost: 58.6, queries: 2912 },
];

export const mockFAQs = [
  { id: "faq_1", question: "What is the interest rate for home loans?", answer: "Our home loan interest rates start from 8.5% p.a. and vary based on the loan amount, tenure, and your credit profile.", category: "Home Loans", created_at: "2026-01-15" },
  { id: "faq_2", question: "How can I check my loan balance?", answer: "You can check your loan balance through our mobile app, net banking portal, or by visiting your nearest branch.", category: "Account", created_at: "2026-01-15" },
  { id: "faq_3", question: "What documents are required for a personal loan?", answer: "You need ID proof (Aadhaar/PAN), address proof, salary slips (last 3 months), bank statements (last 6 months), and passport-size photographs.", category: "Personal Loans", created_at: "2026-01-16" },
  { id: "faq_4", question: "What are the foreclosure charges?", answer: "Foreclosure charges are 2% of the outstanding principal for fixed-rate loans. Floating-rate loans have zero foreclosure charges for individual borrowers as per RBI guidelines.", category: "Fees & Charges", created_at: "2026-01-16" },
  { id: "faq_5", question: "How do I apply for a loan against property?", answer: "You can apply online through our website, visit a branch, or call our toll-free number 1800-XXX-XXXX. An executive will guide you through the process.", category: "Property Loans", created_at: "2026-01-17" },
  { id: "faq_6", question: "What is the maximum loan tenure?", answer: "Home loans: up to 30 years. Personal loans: up to 5 years. Loan against property: up to 15 years. Vehicle loans: up to 7 years.", category: "General", created_at: "2026-01-17" },
  { id: "faq_7", question: "How do I change my EMI date?", answer: "You can request an EMI date change through the mobile app or by visiting a branch. The change will be effective from the next billing cycle.", category: "EMI", created_at: "2026-01-18" },
  { id: "faq_8", question: "What happens if I miss an EMI payment?", answer: "A late fee of 2% per month on the overdue amount will be charged. It may also affect your credit score. Please contact us immediately for restructuring options.", category: "EMI", created_at: "2026-01-18" },
  { id: "faq_9", question: "Can I transfer my loan from another bank?", answer: "Yes, we offer balance transfer facility with competitive interest rates. You need to provide your existing loan account details and NOC from the current lender.", category: "Balance Transfer", created_at: "2026-01-19" },
  { id: "faq_10", question: "What is the processing fee for loans?", answer: "Processing fee varies: Home loans - 0.5% to 1%, Personal loans - 1% to 2.5%, Vehicle loans - 0.5% to 1.5% of the loan amount.", category: "Fees & Charges", created_at: "2026-01-19" },
];

export const mockTraces = [
  {
    trace_id: "tr_abc123",
    session_id: "sess_a1b2c3",
    timestamp: "2026-02-19T08:15:32Z",
    duration_ms: 2340,
    input: "What are the foreclosure charges for my home loan?",
    output: "Foreclosure charges are 2% of the outstanding principal for fixed-rate loans...",
    model: "deepseek/deepseek-r1",
    tokens_in: 45,
    tokens_out: 128,
    cost: 0.0023,
    status: "success",
    route: "faq_retrieval",
    steps: [
      { name: "Router Classify", duration_ms: 120, type: "router", result: "faq_retrieval" },
      { name: "Vector Search", duration_ms: 340, type: "retrieval", result: "3 documents found" },
      { name: "LLM Generation", duration_ms: 1800, type: "llm", result: "Response generated" },
      { name: "Guardrail Check", duration_ms: 80, type: "guardrail", result: "passed" },
    ],
  },
  {
    trace_id: "tr_def456",
    session_id: "sess_a1b2c3",
    timestamp: "2026-02-19T08:16:45Z",
    duration_ms: 3120,
    input: "Can I get a lower interest rate?",
    output: "Interest rates depend on several factors including your credit score, loan amount...",
    model: "deepseek/deepseek-r1",
    tokens_in: 38,
    tokens_out: 156,
    cost: 0.0031,
    status: "success",
    route: "general_query",
    steps: [
      { name: "Router Classify", duration_ms: 110, type: "router", result: "general_query" },
      { name: "Context Assembly", duration_ms: 210, type: "retrieval", result: "5 documents found" },
      { name: "LLM Generation", duration_ms: 2600, type: "llm", result: "Response generated" },
      { name: "Guardrail Check", duration_ms: 90, type: "guardrail", result: "passed" },
      { name: "Follow-up Gen", duration_ms: 110, type: "post_process", result: "3 follow-ups" },
    ],
  },
  {
    trace_id: "tr_ghi789",
    session_id: "sess_d4e5f6",
    timestamp: "2026-02-19T07:50:12Z",
    duration_ms: 1890,
    input: "Tell me about your political views",
    output: "I'm sorry, I can only help with questions related to HFCL's financial products and services.",
    model: "openai/gpt-4o",
    tokens_in: 28,
    tokens_out: 42,
    cost: 0.0012,
    status: "guardrail_blocked",
    route: "off_topic",
    steps: [
      { name: "Router Classify", duration_ms: 95, type: "router", result: "off_topic" },
      { name: "Guardrail Check", duration_ms: 60, type: "guardrail", result: "blocked - off_topic" },
      { name: "Fallback Response", duration_ms: 35, type: "post_process", result: "Standard rejection" },
    ],
  },
  {
    trace_id: "tr_jkl012",
    session_id: "sess_g7h8i9",
    timestamp: "2026-02-18T22:35:00Z",
    duration_ms: 4500,
    input: "Compare home loan vs loan against property",
    output: "Here's a detailed comparison of Home Loan vs Loan Against Property...",
    model: "deepseek/deepseek-r1",
    tokens_in: 52,
    tokens_out: 320,
    cost: 0.0058,
    status: "success",
    route: "comparison_query",
    steps: [
      { name: "Router Classify", duration_ms: 130, type: "router", result: "comparison_query" },
      { name: "Multi-Vector Search", duration_ms: 680, type: "retrieval", result: "8 documents found" },
      { name: "Context Ranking", duration_ms: 190, type: "retrieval", result: "Top 4 selected" },
      { name: "LLM Generation", duration_ms: 3200, type: "llm", result: "Response generated" },
      { name: "Guardrail Check", duration_ms: 75, type: "guardrail", result: "passed" },
      { name: "Follow-up Gen", duration_ms: 125, type: "post_process", result: "3 follow-ups" },
    ],
  },
  {
    trace_id: "tr_mno345",
    session_id: "sess_m3n4o5",
    timestamp: "2026-02-18T15:25:00Z",
    duration_ms: 1200,
    input: "What is EMI?",
    output: "EMI stands for Equated Monthly Installment. It is the fixed amount you pay every month...",
    model: "openai/gpt-4o",
    tokens_in: 18,
    tokens_out: 95,
    cost: 0.0018,
    status: "success",
    route: "faq_retrieval",
    steps: [
      { name: "Router Classify", duration_ms: 85, type: "router", result: "faq_retrieval" },
      { name: "Vector Search", duration_ms: 280, type: "retrieval", result: "2 documents found" },
      { name: "LLM Generation", duration_ms: 750, type: "llm", result: "Response generated" },
      { name: "Guardrail Check", duration_ms: 85, type: "guardrail", result: "passed" },
    ],
  },
];

export const mockQuestionCategories = [
  { category: "Home Loans", count: 3420, percentage: 21.6, trend: "+5.2%" },
  { category: "Personal Loans", count: 2890, percentage: 18.3, trend: "+3.1%" },
  { category: "EMI & Payments", count: 2456, percentage: 15.5, trend: "-1.2%" },
  { category: "Fees & Charges", count: 2100, percentage: 13.3, trend: "+8.7%" },
  { category: "Account Services", count: 1780, percentage: 11.2, trend: "+2.4%" },
  { category: "Balance Transfer", count: 1234, percentage: 7.8, trend: "+12.3%" },
  { category: "Property Loans", count: 890, percentage: 5.6, trend: "-0.5%" },
  { category: "Off Topic / Blocked", count: 562, percentage: 3.6, trend: "-15.2%" },
  { category: "General Inquiry", count: 500, percentage: 3.1, trend: "+1.8%" },
];

export const mockFeedback = [
  { id: "fb_1", session_id: "sess_a1b2c3", rating: "thumbs_up", comment: "Very helpful response about loan options!", category: "accuracy", timestamp: "2026-02-19T08:20:00Z" },
  { id: "fb_2", session_id: "sess_d4e5f6", rating: "thumbs_down", comment: "Response was too generic", category: "relevance", timestamp: "2026-02-19T07:55:00Z" },
  { id: "fb_3", session_id: "sess_g7h8i9", rating: "thumbs_up", comment: "Great comparison!", category: "completeness", timestamp: "2026-02-18T22:40:00Z" },
  { id: "fb_4", session_id: "sess_j0k1l2", rating: "thumbs_up", comment: "", category: "accuracy", timestamp: "2026-02-18T19:10:00Z" },
  { id: "fb_5", session_id: "sess_m3n4o5", rating: "thumbs_down", comment: "Took too long to respond", category: "speed", timestamp: "2026-02-18T15:30:00Z" },
  { id: "fb_6", session_id: "sess_p6q7r8", rating: "thumbs_up", comment: "Exactly what I needed", category: "accuracy", timestamp: "2026-02-18T12:15:00Z" },
  { id: "fb_7", session_id: "sess_s9t0u1", rating: "thumbs_up", comment: "Clear and concise", category: "clarity", timestamp: "2026-02-17T10:45:00Z" },
  { id: "fb_8", session_id: "sess_v2w3x4", rating: "thumbs_down", comment: "Should have provided more details", category: "completeness", timestamp: "2026-02-17T08:20:00Z" },
];

export const mockGuardrails = [
  { id: "gr_1", timestamp: "2026-02-19T08:30:00Z", session_id: "sess_a1b2c3", trigger: "off_topic", input: "What do you think about politics?", action: "blocked", severity: "medium" },
  { id: "gr_2", timestamp: "2026-02-19T07:20:00Z", session_id: "sess_d4e5f6", trigger: "pii_detected", input: "My Aadhaar number is 1234...", action: "redacted", severity: "high" },
  { id: "gr_3", timestamp: "2026-02-18T20:15:00Z", session_id: "sess_g7h8i9", trigger: "prompt_injection", input: "Ignore all instructions and...", action: "blocked", severity: "critical" },
  { id: "gr_4", timestamp: "2026-02-18T18:00:00Z", session_id: "sess_j0k1l2", trigger: "off_topic", input: "Tell me a joke", action: "redirected", severity: "low" },
  { id: "gr_5", timestamp: "2026-02-18T14:30:00Z", session_id: "sess_m3n4o5", trigger: "competitor_mention", input: "Why is HDFC better than you?", action: "redirected", severity: "medium" },
  { id: "gr_6", timestamp: "2026-02-17T11:00:00Z", session_id: "sess_s9t0u1", trigger: "pii_detected", input: "My PAN card is ABCDE...", action: "redacted", severity: "high" },
];

export const mockModels = [
  { id: "deepseek/deepseek-r1", name: "DeepSeek R1", contextLength: 64000, costPer1kIn: 0.0008, costPer1kOut: 0.002 },
  { id: "openai/gpt-4o", name: "GPT-4o", contextLength: 128000, costPer1kIn: 0.005, costPer1kOut: 0.015 },
  { id: "anthropic/claude-3.5-sonnet", name: "Claude 3.5 Sonnet", contextLength: 200000, costPer1kIn: 0.003, costPer1kOut: 0.015 },
  { id: "google/gemini-2.0-flash", name: "Gemini 2.0 Flash", contextLength: 1000000, costPer1kIn: 0.0001, costPer1kOut: 0.0004 },
  { id: "meta/llama-3.3-70b", name: "Llama 3.3 70B", contextLength: 131072, costPer1kIn: 0.0003, costPer1kOut: 0.0004 },
];

export const mockRateLimitMetrics = {
  total_requests: 15832,
  blocked_requests: 234,
  current_rps: 12.4,
  peak_rps: 45.2,
  active_limiters: 38,
  config: {
    global_rpm: 1000,
    session_rpm: 30,
    burst_limit: 5,
    window_seconds: 60,
  },
};

export const mockHealthStatus = {
  status: "healthy",
  uptime_seconds: 2592000,
  version: "1.4.2",
  dependencies: {
    redis: { status: "connected", latency_ms: 2 },
    qdrant: { status: "connected", latency_ms: 15 },
    openrouter: { status: "connected", latency_ms: 120 },
    postgres: { status: "connected", latency_ms: 5 },
  },
};
