import type {
  GuardrailEvent,
  GuardrailJudgeSummary,
  GuardrailQueueHealth,
  GuardrailSummary,
  GuardrailTrendPoint,
} from '@features/admin/api/admin'
import type { EvalTraceDetail } from '@features/admin/types/admin'

export type GuardrailRiskLevel = 'critical' | 'high' | 'medium' | 'low'

export type GuardrailKpiCard = {
  label: string
  value: string
  tone: 'rose' | 'amber' | 'violet' | 'sky' | 'emerald' | 'indigo'
}

export function riskLevelFromScore(score: number): GuardrailRiskLevel {
  if (score >= 0.8) return 'critical'
  if (score >= 0.5) return 'high'
  if (score >= 0.3) return 'medium'
  return 'low'
}

export function isBlockingDecision(decision: string): boolean {
  const normalized = decision.toLowerCase()
  return normalized.includes('deny') || normalized.includes('block')
}

export function mapGuardrailKpis(params: {
  summary?: GuardrailSummary
  queue?: GuardrailQueueHealth
  judge?: GuardrailJudgeSummary
}): GuardrailKpiCard[] {
  const { summary, queue, judge } = params

  return [
    {
      label: 'Deny Rate',
      value: `${((summary?.deny_rate ?? 0) * 100).toFixed(1)}%`,
      tone: 'rose',
    },
    {
      label: 'Avg Risk',
      value: `${((summary?.avg_risk_score ?? 0) * 100).toFixed(0)}%`,
      tone: 'amber',
    },
    {
      label: 'Queue Depth',
      value: String(queue?.depth ?? 0),
      tone: 'violet',
    },
    {
      label: 'Oldest Queue Age',
      value: queue?.oldest_age_seconds ? `${queue.oldest_age_seconds}s` : '0s',
      tone: 'sky',
    },
    {
      label: 'Policy Adherence',
      value: `${((judge?.avg_policy_adherence ?? 0) * 100).toFixed(1)}%`,
      tone: 'emerald',
    },
    {
      label: 'Total Evaluations',
      value: String(judge?.total_evals ?? 0),
      tone: 'indigo',
    },
  ]
}

export function uniqueDecisionOptions(events: GuardrailEvent[]): string[] {
  const unique = new Set(events.map((event) => event.risk_decision).filter(Boolean))
  return ['all', ...unique]
}

export function peakTrendValue(trends: GuardrailTrendPoint[]): number {
  return Math.max(...trends.map((point) => point.total_events), 1)
}

export function extractInputTextFromTraceDetail(detail?: EvalTraceDetail | null): string {
  const input = detail?.trace?.inputs_json

  if (typeof input === 'string') {
    const raw = input.trim()
    if (!raw) return ''

    try {
      const parsed = JSON.parse(raw)
      return extractInputTextFromTraceDetail({ trace: { inputs_json: parsed } } as EvalTraceDetail)
    } catch {
      return raw
    }
  }

  if (typeof input !== 'object' || input === null) return ''

  const payload = input as Record<string, unknown>
  if (typeof payload.question === 'string' && payload.question.trim()) return payload.question.trim()
  if (typeof payload.input === 'string' && payload.input.trim()) return payload.input.trim()

  return ''
}
