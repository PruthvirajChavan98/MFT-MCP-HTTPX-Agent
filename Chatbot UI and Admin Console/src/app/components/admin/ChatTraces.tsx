import { flags } from '../../../shared/config/flags'
import { ChatTracesEnterprise } from './redesign/ChatTracesEnterprise'
import { ChatTracesLegacy } from './ChatTracesLegacy'

export function ChatTraces() {
  return flags.adminEnterpriseRedesign ? <ChatTracesEnterprise /> : <ChatTracesLegacy />
}
