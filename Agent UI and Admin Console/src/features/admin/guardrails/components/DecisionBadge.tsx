import { Ban, CheckCheck } from 'lucide-react'
import { isBlockingDecision } from '../viewmodel'

export function DecisionBadge({ decision }: { decision: string }) {
  if (isBlockingDecision(decision)) {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full bg-red-500 px-2.5 py-1 text-[11px] font-bold text-white">
        <Ban className="size-3" /> {decision}
      </span>
    )
  }

  return (
    <span className="inline-flex items-center gap-1.5 rounded-full bg-teal-500 px-2.5 py-1 text-[11px] font-bold text-white">
      <CheckCheck className="size-3" /> {decision}
    </span>
  )
}
