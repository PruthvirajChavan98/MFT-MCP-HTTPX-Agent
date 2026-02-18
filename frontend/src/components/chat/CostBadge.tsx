import type { CostEvent } from '../../types/chat'

export function CostBadge(props: { cost: CostEvent }) {
  return (
    <span
      class="chat-cost-badge"
      title={`${props.cost.model} via ${props.cost.provider} | prompt ${props.cost.usage.prompt_tokens} + completion ${props.cost.usage.completion_tokens} + reasoning ${props.cost.usage.reasoning_tokens}`}
    >
      ${props.cost.total_cost.toFixed(4)}
      <small>{props.cost.usage.total_tokens.toLocaleString()} tok</small>
    </span>
  )
}
