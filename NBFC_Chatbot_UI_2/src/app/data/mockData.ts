// ==================== KNOWLEDGE BASE ====================
export interface KBEntry {
  id: string
  question: string
  answer: string
  category: string
  embeddingStatus: 'indexed' | 'pending' | 'failed'
  lastUpdated: string
  chunkCount: number
  similarity?: number
}

export const kbEntries: KBEntry[] = [
  { id: 'kb-001', question: 'What is the minimum credit score for a home loan?', answer: 'The minimum CIBIL score required for a home loan is 650. However, a score of 750+ gets you the best interest rates starting at 8.5% p.a.', category: 'Home Loans', embeddingStatus: 'indexed', lastUpdated: '2026-02-15', chunkCount: 3 },
  { id: 'kb-002', question: 'How long does loan approval take?', answer: 'Home loan approval typically takes 3-5 business days after document submission. For pre-approved customers, it can be as fast as 24 hours.', category: 'Process', embeddingStatus: 'indexed', lastUpdated: '2026-02-14', chunkCount: 2 },
  { id: 'kb-003', question: 'What documents are needed for a business loan?', answer: 'Business loan requires: PAN card, Aadhaar, last 2 years ITR, bank statements (6 months), business registration certificate, and GST returns.', category: 'Business Loans', embeddingStatus: 'indexed', lastUpdated: '2026-02-13', chunkCount: 4 },
  { id: 'kb-004', question: 'Can I prepay my loan without penalty?', answer: 'Yes, TrustFin allows prepayment without any charges on floating rate loans. Fixed rate loans have a 2% prepayment charge on the outstanding amount.', category: 'General', embeddingStatus: 'indexed', lastUpdated: '2026-02-12', chunkCount: 2 },
  { id: 'kb-005', question: 'What is the maximum loan tenure?', answer: 'Home loans: up to 30 years, Vehicle loans: up to 7 years, Business loans: up to 5 years, Education loans: up to 15 years, Personal loans: up to 5 years.', category: 'General', embeddingStatus: 'indexed', lastUpdated: '2026-02-10', chunkCount: 3 },
  { id: 'kb-006', question: 'How do I check my EMI schedule?', answer: "You can check your EMI schedule in the TrustFin mobile app under 'My Loans' > 'EMI Schedule', or log in to the web portal.", category: 'Process', embeddingStatus: 'indexed', lastUpdated: '2026-02-09', chunkCount: 1 },
  { id: 'kb-007', question: 'What are the vehicle loan interest rates?', answer: 'Vehicle loan interest rates start from 9.2% p.a. for new cars and 11.5% p.a. for used cars. The rate depends on the vehicle type, loan amount, and credit score.', category: 'Vehicle Loans', embeddingStatus: 'pending', lastUpdated: '2026-02-08', chunkCount: 2 },
  { id: 'kb-008', question: 'Is there a processing fee?', answer: 'Processing fee ranges from 0.5% to 2% of the loan amount depending on the product. During festive offers, processing fees may be waived.', category: 'General', embeddingStatus: 'indexed', lastUpdated: '2026-02-07', chunkCount: 2 },
  { id: 'kb-009', question: 'What is the eligibility for education loan?', answer: 'Indian nationals aged 18-35, with admission to a recognized institution. Co-applicant (parent/guardian) required. No collateral needed up to ₹7.5 lakhs.', category: 'Education Loans', embeddingStatus: 'failed', lastUpdated: '2026-02-06', chunkCount: 3 },
  { id: 'kb-010', question: 'How do I contact customer support?', answer: 'Toll-free: 1800-123-4567 (24/7), Email: support@trustfin.in, WhatsApp: +91 98765 43210, or visit any of our 150+ branches.', category: 'General', embeddingStatus: 'indexed', lastUpdated: '2026-02-05', chunkCount: 1 },
  { id: 'kb-011', question: 'What is the maximum business loan amount?', answer: 'Collateral-free business loans up to ₹50 lakhs. With collateral, you can avail loans up to ₹5 crores based on business turnover and creditworthiness.', category: 'Business Loans', embeddingStatus: 'indexed', lastUpdated: '2026-02-04', chunkCount: 2 },
  { id: 'kb-012', question: 'Can NRIs apply for home loans?', answer: 'Yes, NRIs can apply for home loans with us. Additional documents include passport, visa, overseas employment proof, and NRE/NRO account statements.', category: 'Home Loans', embeddingStatus: 'indexed', lastUpdated: '2026-02-03', chunkCount: 3 },
]

// ==================== CHAT SESSIONS & COSTS ====================
export interface ChatSession {
  id: string
  userId: string
  userName: string
  startTime: string
  endTime: string
  messageCount: number
  inputTokens: number
  outputTokens: number
  totalTokens: number
  model: string
  cost: number
  category: string
  sentiment: 'positive' | 'neutral' | 'negative'
  resolved: boolean
}

export const chatSessions: ChatSession[] = [
  { id: 'cs-001', userId: 'u-101', userName: 'Rahul Mehta', startTime: '2026-02-18T09:15:00', endTime: '2026-02-18T09:22:00', messageCount: 8, inputTokens: 1245, outputTokens: 892, totalTokens: 2137, model: 'gpt-4o', cost: 0.034, category: 'Home Loans', sentiment: 'positive', resolved: true },
  { id: 'cs-002', userId: 'u-102', userName: 'Anita Desai', startTime: '2026-02-18T09:30:00', endTime: '2026-02-18T09:41:00', messageCount: 12, inputTokens: 2100, outputTokens: 1580, totalTokens: 3680, model: 'gpt-4o', cost: 0.058, category: 'Business Loans', sentiment: 'neutral', resolved: true },
  { id: 'cs-003', userId: 'u-103', userName: 'Vikram Singh', startTime: '2026-02-18T10:05:00', endTime: '2026-02-18T10:08:00', messageCount: 4, inputTokens: 620, outputTokens: 410, totalTokens: 1030, model: 'gpt-4o-mini', cost: 0.004, category: 'Complaint', sentiment: 'negative', resolved: false },
  { id: 'cs-004', userId: 'u-104', userName: 'Sneha Patel', startTime: '2026-02-18T10:30:00', endTime: '2026-02-18T10:45:00', messageCount: 15, inputTokens: 2800, outputTokens: 2100, totalTokens: 4900, model: 'gpt-4o', cost: 0.078, category: 'Education Loans', sentiment: 'positive', resolved: true },
  { id: 'cs-005', userId: 'u-105', userName: 'Amit Joshi', startTime: '2026-02-18T11:00:00', endTime: '2026-02-18T11:12:00', messageCount: 10, inputTokens: 1800, outputTokens: 1350, totalTokens: 3150, model: 'gpt-4o', cost: 0.050, category: 'Vehicle Loans', sentiment: 'neutral', resolved: true },
  { id: 'cs-006', userId: 'u-106', userName: 'Meera Nair', startTime: '2026-02-18T11:20:00', endTime: '2026-02-18T11:25:00', messageCount: 5, inputTokens: 750, outputTokens: 520, totalTokens: 1270, model: 'gpt-4o-mini', cost: 0.005, category: 'General', sentiment: 'positive', resolved: true },
  { id: 'cs-007', userId: 'u-107', userName: 'Suresh Reddy', startTime: '2026-02-18T11:45:00', endTime: '2026-02-18T11:58:00', messageCount: 14, inputTokens: 2450, outputTokens: 1900, totalTokens: 4350, model: 'gpt-4o', cost: 0.069, category: 'Home Loans', sentiment: 'neutral', resolved: true },
  { id: 'cs-008', userId: 'u-108', userName: 'Kavita Sharma', startTime: '2026-02-18T12:10:00', endTime: '2026-02-18T12:18:00', messageCount: 7, inputTokens: 1100, outputTokens: 780, totalTokens: 1880, model: 'gpt-4o-mini', cost: 0.007, category: 'Complaint', sentiment: 'negative', resolved: false },
  { id: 'cs-009', userId: 'u-109', userName: 'Deepak Gupta', startTime: '2026-02-18T13:00:00', endTime: '2026-02-18T13:20:00', messageCount: 18, inputTokens: 3200, outputTokens: 2500, totalTokens: 5700, model: 'gpt-4o', cost: 0.091, category: 'Business Loans', sentiment: 'positive', resolved: true },
  { id: 'cs-010', userId: 'u-110', userName: 'Pooja Agarwal', startTime: '2026-02-18T13:30:00', endTime: '2026-02-18T13:35:00', messageCount: 6, inputTokens: 900, outputTokens: 650, totalTokens: 1550, model: 'gpt-4o-mini', cost: 0.006, category: 'General', sentiment: 'neutral', resolved: true },
  { id: 'cs-011', userId: 'u-101', userName: 'Rahul Mehta', startTime: '2026-02-17T14:00:00', endTime: '2026-02-17T14:15:00', messageCount: 11, inputTokens: 1950, outputTokens: 1400, totalTokens: 3350, model: 'gpt-4o', cost: 0.053, category: 'Home Loans', sentiment: 'positive', resolved: true },
  { id: 'cs-012', userId: 'u-111', userName: 'Rohan Kapoor', startTime: '2026-02-17T15:00:00', endTime: '2026-02-17T15:10:00', messageCount: 9, inputTokens: 1500, outputTokens: 1100, totalTokens: 2600, model: 'gpt-4o', cost: 0.041, category: 'Vehicle Loans', sentiment: 'neutral', resolved: true },
]

// ==================== QUESTION CATEGORIES ====================
export interface QuestionCategory {
  name: string
  count: number
  percentage: number
  trend: 'up' | 'down' | 'stable'
  trendValue: number
  color: string
  subcategories: { name: string; count: number }[]
}

export const questionCategories: QuestionCategory[] = [
  { name: 'Home Loans', count: 1245, percentage: 28.5, trend: 'up', trendValue: 12, color: '#0ea5e9', subcategories: [{ name: 'Interest Rates', count: 420 }, { name: 'Eligibility', count: 380 }, { name: 'Documents', count: 285 }, { name: 'EMI Calculator', count: 160 }] },
  { name: 'Business Loans', count: 890, percentage: 20.4, trend: 'up', trendValue: 8, color: '#8b5cf6', subcategories: [{ name: 'Collateral Free', count: 310 }, { name: 'MSME Loans', count: 280 }, { name: 'Working Capital', count: 180 }, { name: 'Eligibility', count: 120 }] },
  { name: 'Vehicle Loans', count: 678, percentage: 15.5, trend: 'stable', trendValue: 2, color: '#10b981', subcategories: [{ name: 'New Car', count: 350 }, { name: 'Used Car', count: 180 }, { name: 'Two Wheeler', count: 148 }] },
  { name: 'Education Loans', count: 520, percentage: 11.9, trend: 'up', trendValue: 25, color: '#f59e0b', subcategories: [{ name: 'Study Abroad', count: 280 }, { name: 'Domestic', count: 150 }, { name: 'Skill Development', count: 90 }] },
  { name: 'Complaints', count: 412, percentage: 9.4, trend: 'down', trendValue: -15, color: '#ef4444', subcategories: [{ name: 'Delayed Processing', count: 180 }, { name: 'Customer Service', count: 120 }, { name: 'Technical Issues', count: 72 }, { name: 'Incorrect Charges', count: 40 }] },
  { name: 'Account & General', count: 380, percentage: 8.7, trend: 'stable', trendValue: 1, color: '#6b7280', subcategories: [{ name: 'Account Access', count: 150 }, { name: 'EMI Schedule', count: 110 }, { name: 'Prepayment', count: 80 }, { name: 'Others', count: 40 }] },
  { name: 'Escalations', count: 240, percentage: 5.5, trend: 'down', trendValue: -8, color: '#dc2626', subcategories: [{ name: 'Unresolved Complaints', count: 140 }, { name: 'Manager Request', count: 60 }, { name: 'Legal Queries', count: 40 }] },
]

// ==================== DAILY COST DATA ====================
export const dailyCostData = [
  { date: 'Feb 1', sessions: 145, cost: 4.52, tokens: 185000 },
  { date: 'Feb 2', sessions: 132, cost: 4.10, tokens: 168000 },
  { date: 'Feb 3', sessions: 98, cost: 2.95, tokens: 121000 },
  { date: 'Feb 4', sessions: 110, cost: 3.40, tokens: 140000 },
  { date: 'Feb 5', sessions: 156, cost: 5.12, tokens: 210000 },
  { date: 'Feb 6', sessions: 168, cost: 5.45, tokens: 224000 },
  { date: 'Feb 7', sessions: 142, cost: 4.38, tokens: 180000 },
  { date: 'Feb 8', sessions: 150, cost: 4.80, tokens: 196000 },
  { date: 'Feb 9', sessions: 138, cost: 4.25, tokens: 175000 },
  { date: 'Feb 10', sessions: 95, cost: 2.80, tokens: 115000 },
  { date: 'Feb 11', sessions: 105, cost: 3.15, tokens: 130000 },
  { date: 'Feb 12', sessions: 172, cost: 5.68, tokens: 232000 },
  { date: 'Feb 13', sessions: 185, cost: 6.10, tokens: 250000 },
  { date: 'Feb 14', sessions: 160, cost: 5.25, tokens: 215000 },
  { date: 'Feb 15', sessions: 148, cost: 4.70, tokens: 192000 },
  { date: 'Feb 16', sessions: 155, cost: 5.00, tokens: 205000 },
  { date: 'Feb 17', sessions: 120, cost: 3.65, tokens: 150000 },
  { date: 'Feb 18', sessions: 88, cost: 2.90, tokens: 108000 },
]

// ==================== USER ANALYTICS ====================
export interface UserAnalytics {
  id: string
  name: string
  sessions: number
  totalMessages: number
  avgSessionLength: string
  lastActive: string
  topCategory: string
  satisfaction: number
  returning: boolean
}

export const userAnalytics: UserAnalytics[] = [
  { id: 'u-101', name: 'Rahul Mehta', sessions: 5, totalMessages: 42, avgSessionLength: '8m 30s', lastActive: '2026-02-18', topCategory: 'Home Loans', satisfaction: 92, returning: true },
  { id: 'u-102', name: 'Anita Desai', sessions: 3, totalMessages: 28, avgSessionLength: '10m 15s', lastActive: '2026-02-18', topCategory: 'Business Loans', satisfaction: 78, returning: true },
  { id: 'u-103', name: 'Vikram Singh', sessions: 2, totalMessages: 9, avgSessionLength: '3m 45s', lastActive: '2026-02-18', topCategory: 'Complaint', satisfaction: 25, returning: false },
  { id: 'u-104', name: 'Sneha Patel', sessions: 4, totalMessages: 35, avgSessionLength: '12m 00s', lastActive: '2026-02-18', topCategory: 'Education Loans', satisfaction: 95, returning: true },
  { id: 'u-105', name: 'Amit Joshi', sessions: 2, totalMessages: 18, avgSessionLength: '9m 00s', lastActive: '2026-02-18', topCategory: 'Vehicle Loans', satisfaction: 85, returning: true },
  { id: 'u-106', name: 'Meera Nair', sessions: 1, totalMessages: 5, avgSessionLength: '4m 30s', lastActive: '2026-02-18', topCategory: 'General', satisfaction: 88, returning: false },
  { id: 'u-107', name: 'Suresh Reddy', sessions: 3, totalMessages: 30, avgSessionLength: '11m 20s', lastActive: '2026-02-18', topCategory: 'Home Loans', satisfaction: 80, returning: true },
  { id: 'u-108', name: 'Kavita Sharma', sessions: 2, totalMessages: 14, avgSessionLength: '6m 00s', lastActive: '2026-02-18', topCategory: 'Complaint', satisfaction: 30, returning: false },
  { id: 'u-109', name: 'Deepak Gupta', sessions: 6, totalMessages: 55, avgSessionLength: '15m 00s', lastActive: '2026-02-18', topCategory: 'Business Loans', satisfaction: 90, returning: true },
  { id: 'u-110', name: 'Pooja Agarwal', sessions: 1, totalMessages: 6, avgSessionLength: '5m 00s', lastActive: '2026-02-18', topCategory: 'General', satisfaction: 82, returning: false },
  { id: 'u-111', name: 'Rohan Kapoor', sessions: 2, totalMessages: 16, avgSessionLength: '7m 45s', lastActive: '2026-02-17', topCategory: 'Vehicle Loans', satisfaction: 65, returning: true },
]

// ==================== HOURLY USAGE DATA ====================
export const hourlyUsageData = [
  { hour: '6AM', sessions: 5, users: 4 },
  { hour: '7AM', sessions: 12, users: 10 },
  { hour: '8AM', sessions: 28, users: 22 },
  { hour: '9AM', sessions: 45, users: 38 },
  { hour: '10AM', sessions: 52, users: 42 },
  { hour: '11AM', sessions: 48, users: 40 },
  { hour: '12PM', sessions: 35, users: 30 },
  { hour: '1PM', sessions: 42, users: 35 },
  { hour: '2PM', sessions: 50, users: 41 },
  { hour: '3PM', sessions: 46, users: 38 },
  { hour: '4PM', sessions: 38, users: 32 },
  { hour: '5PM', sessions: 30, users: 25 },
  { hour: '6PM', sessions: 22, users: 18 },
  { hour: '7PM', sessions: 15, users: 12 },
  { hour: '8PM', sessions: 10, users: 8 },
  { hour: '9PM', sessions: 8, users: 6 },
]

// ==================== MODEL CONFIG ====================
export interface ModelConfigRecord {
  id: string
  name: string
  provider: string
  model: string
  temperature: number
  maxTokens: number
  topP: number
  systemPrompt: string
  active: boolean
  costPer1kInput: number
  costPer1kOutput: number
}

export const modelConfigs: ModelConfigRecord[] = [
  {
    id: 'mc-001',
    name: 'Primary (GPT-4o)',
    provider: 'OpenAI',
    model: 'gpt-4o',
    temperature: 0.3,
    maxTokens: 500,
    topP: 0.95,
    systemPrompt: "You are TrustFin's AI assistant. You help customers with financial queries about loans, account management, and general information. Be professional, empathetic, and accurate. Never provide specific financial advice — always recommend consulting with a financial advisor for personalized guidance. If you don't know something, say so honestly.",
    active: true,
    costPer1kInput: 0.005,
    costPer1kOutput: 0.015,
  },
  {
    id: 'mc-002',
    name: 'Fallback (GPT-4o-mini)',
    provider: 'OpenAI',
    model: 'gpt-4o-mini',
    temperature: 0.3,
    maxTokens: 400,
    topP: 0.9,
    systemPrompt: "You are TrustFin's AI assistant. Help customers with loan and account queries. Be professional and concise. Redirect complex queries to human agents.",
    active: true,
    costPer1kInput: 0.00015,
    costPer1kOutput: 0.0006,
  },
]
