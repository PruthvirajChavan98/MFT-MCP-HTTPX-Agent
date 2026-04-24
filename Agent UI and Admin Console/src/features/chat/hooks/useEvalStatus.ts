import { useEffect, useRef, useState } from 'react'
import { API_BASE_URL } from '@shared/api/http'
import type { EvalStatus } from '@shared/types/chat'

const POLL_INTERVAL_MS = 5_000
const MAX_ATTEMPTS = 10

export interface EvalStatusResult {
  status: EvalStatus['status'] | null
  reason?: EvalStatus['reason']
  passed: number | undefined
  failed: number | undefined
  shadowJudge: EvalStatus['shadowJudge'] | undefined
}

type TimerRef = { current: ReturnType<typeof setInterval> | null }

function stopPolling(timerRef: TimerRef) {
  if (timerRef.current !== null) {
    clearInterval(timerRef.current)
    timerRef.current = null
  }
}

export function useEvalStatus(traceId: string | undefined): EvalStatusResult | null {
  const [result, setResult] = useState<EvalStatusResult | null>(null)
  const attemptRef = useRef(0)
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)

  useEffect(() => {
    if (!traceId) {
      setResult(null)
      return
    }

    attemptRef.current = 0

    const fetchStatus = async () => {
      if (attemptRef.current >= MAX_ATTEMPTS) {
        setResult({
          status: 'unavailable',
          reason: 'timed_out',
          passed: undefined,
          failed: undefined,
          shadowJudge: undefined,
        })
        stopPolling(timerRef)
        return
      }

      attemptRef.current += 1

      try {
        const response = await fetch(
          `${API_BASE_URL}/eval/trace/${encodeURIComponent(traceId)}/eval-status`,
        )

        if (!response.ok) {
          if (response.status === 404) {
            setResult({
              status: 'not_found',
              reason: undefined,
              passed: undefined,
              failed: undefined,
              shadowJudge: undefined,
            })
            stopPolling(timerRef)
          }
          return
        }

        const raw = await response.json() as {
          status: EvalStatus['status']
          reason?: EvalStatus['reason']
          inline_evals?: { passed: number; failed: number } | null
          shadow_judge?: EvalStatus['shadowJudge']
        }

        setResult({
          status: raw.status,
          reason: raw.reason,
          passed: raw.inline_evals?.passed,
          failed: raw.inline_evals?.failed,
          shadowJudge: raw.shadow_judge ?? undefined,
        })

        if (raw.status === 'complete' || raw.status === 'not_found' || raw.status === 'unavailable') {
          stopPolling(timerRef)
        }
      } catch {
        // Network errors are silently ignored; polling will retry
      }
    }

    // Fire first request immediately
    void fetchStatus()

    timerRef.current = setInterval(() => {
      void fetchStatus()
    }, POLL_INTERVAL_MS)

    return () => {
      stopPolling(timerRef)
    }
  }, [traceId])

  return result
}
