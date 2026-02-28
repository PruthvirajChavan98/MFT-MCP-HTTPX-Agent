import { flags } from '../../../shared/config/flags'
import { GuardrailsEnterprise } from './redesign/GuardrailsEnterprise'
import { GuardrailsLegacy } from './GuardrailsLegacy'

export function Guardrails() {
  return flags.adminEnterpriseRedesign ? <GuardrailsEnterprise /> : <GuardrailsLegacy />
}
