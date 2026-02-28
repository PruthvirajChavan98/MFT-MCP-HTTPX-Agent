import { flags } from '../../../shared/config/flags'
import { ChatCostsEnterprise } from './redesign/ChatCostsEnterprise'
import { ChatCostsLegacy } from './ChatCostsLegacy'

export function ChatCosts() {
  return flags.adminEnterpriseRedesign ? <ChatCostsEnterprise /> : <ChatCostsLegacy />
}
