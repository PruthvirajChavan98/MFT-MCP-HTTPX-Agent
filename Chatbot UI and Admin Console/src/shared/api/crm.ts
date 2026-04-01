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

async function crmGraphQL<T>(
  query: string,
  variables?: Record<string, unknown>,
): Promise<T> {
  const base = getCrmBase()
  const res = await fetch(`${base}/graphql`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query, variables }),
  })

  const json: GraphQLResponse<T> = await res.json()

  if (json.errors && json.errors.length > 0) {
    throw new Error(json.errors[0].message)
  }

  if (!res.ok) {
    throw new Error(`CRM request failed (${res.status})`)
  }

  if (!json.data) {
    throw new Error('Empty response from CRM')
  }

  return json.data
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
