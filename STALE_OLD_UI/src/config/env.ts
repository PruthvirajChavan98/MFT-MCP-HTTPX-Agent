/**
 * Strict Environment Configuration
 */
export const Env = {
  APP_NAME: 'Dual-Stream AI',
  VERSION: '1.0.0',
  IS_DEV: import.meta.env.DEV,
  API_BASE_URL: '/agent',
  MCP_BASE_URL: '/tools',
  ENABLE_DEBUG_LOGS: import.meta.env.VITE_ENABLE_DEBUG === 'true',
  TIMEOUT_DEFAULT: 15000,
} as const;
