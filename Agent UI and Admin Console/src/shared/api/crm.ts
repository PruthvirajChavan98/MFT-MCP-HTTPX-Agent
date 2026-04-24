import type { RegisterInput, RegisterResult } from '@shared/types/registration'

const CRM_REGISTER_MUTATION = `
  mutation Register($input: RegisterInput!) {
    register(input: $input) {
      otpSent
      token
      user { id phone firstname lastname dob }
      loansCreated
      expiresAt
      message
    }
  }
`

function getCrmBase(): string {
  const runtime = window.__RUNTIME_CONFIG__?.CRM_API_BASE_URL?.trim()
  return runtime || '/crm-api'
}

interface GraphQLResponse<T> {
  data?: T
  errors?: Array<{ message: string }>
}

class CrmGraphQLError extends Error {
  constructor(
    message: string,
    public readonly status?: number,
    public readonly graphqlErrors?: Array<{ message: string }>,
  ) {
    super(message)
    this.name = 'CrmGraphQLError'
  }
}

const CRM_TIMEOUT_MS = 15_000
const CRM_MAX_RETRIES = 1

async function crmGraphQL<T>(
  query: string,
  variables?: Record<string, unknown>,
): Promise<T> {
  const base = getCrmBase()
  const url = `${base}/graphql`

  let lastError: Error | null = null
  for (let attempt = 0; attempt <= CRM_MAX_RETRIES; attempt++) {
    try {
      const controller = new AbortController()
      const timer = setTimeout(() => controller.abort(), CRM_TIMEOUT_MS)

      const res = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query, variables }),
        signal: controller.signal,
      })
      clearTimeout(timer)

      const json: GraphQLResponse<T> = await res.json()

      if (json.errors && json.errors.length > 0) {
        throw new CrmGraphQLError(
          json.errors[0].message,
          res.status,
          json.errors,
        )
      }

      if (!res.ok) {
        throw new CrmGraphQLError(`CRM request failed (${res.status})`, res.status)
      }

      if (!json.data) {
        throw new CrmGraphQLError('Empty response from CRM')
      }

      return json.data
    } catch (err) {
      lastError = err instanceof Error ? err : new Error(String(err))
      if (attempt < CRM_MAX_RETRIES && !(err instanceof CrmGraphQLError)) {
        continue // Retry on network/timeout errors only, not GraphQL errors
      }
      throw lastError
    }
  }

  throw lastError ?? new Error('CRM request failed')
}

function normalizePhone(raw: string): string {
  const digits = raw.replace(/\D/g, '')
  if (digits.length === 10) return digits
  if (digits.length === 12 && digits.startsWith('91')) return digits.slice(2)
  return digits
}

export async function requestOtp(
  input: Omit<RegisterInput, 'otp'>,
): Promise<RegisterResult> {
  const result = await crmGraphQL<{ register: RegisterResult }>(CRM_REGISTER_MUTATION, {
    input: { ...input, phone: normalizePhone(input.phone) },
  })
  return result.register
}

export async function verifyOtp(input: Required<Pick<RegisterInput, 'otp'>> & Omit<RegisterInput, 'otp'>): Promise<RegisterResult> {
  const result = await crmGraphQL<{ register: RegisterResult }>(CRM_REGISTER_MUTATION, {
    input: { ...input, phone: normalizePhone(input.phone) },
  })
  return result.register
}
