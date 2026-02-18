import { ApiWorkbench } from '../components/workbench/ApiWorkbench'
import { CATEGORY_GROUPS, ENDPOINTS } from '../config/endpoints'

const operationSet = new Set<string>(CATEGORY_GROUPS.operations)
const operationEndpoints = ENDPOINTS.filter((endpoint) => operationSet.has(endpoint.category))

export function OperationsPage() {
  return (
    <ApiWorkbench
      title="Operations Console"
      subtitle="Health, Evaluation, Rate Limits, GraphQL"
      endpoints={operationEndpoints}
      rightLabel="Ops Routes"
      rightValue={String(operationEndpoints.length)}
    />
  )
}
