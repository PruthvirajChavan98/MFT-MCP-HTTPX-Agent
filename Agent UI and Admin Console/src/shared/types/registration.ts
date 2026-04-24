export interface RegisterInput {
  phone: string
  firstname: string
  lastname: string
  dob?: string
  otp?: string
  keepMeFor?: string
}

export interface UserGql {
  id: string
  phone: string
  firstname: string
  lastname: string
  dob: string | null
}

export interface RegisterResult {
  otpSent: boolean
  token: string | null
  user: UserGql | null
  loansCreated: number
  expiresAt: string | null
  message: string
}
