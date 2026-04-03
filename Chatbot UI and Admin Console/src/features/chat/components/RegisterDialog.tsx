import { useEffect, useState } from 'react'
import { useForm } from 'react-hook-form'
import { AnimatePresence, motion } from 'motion/react'
import { toast } from 'sonner'
import { CheckCircle2, Loader2 } from 'lucide-react'
import { requestOtp, verifyOtp } from '@shared/api/crm'
import type { RegisterInput, RegisterResult } from '@shared/types/registration'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@components/ui/dialog'
import { Button } from '@components/ui/button'
import { Input } from '@components/ui/input'
import { Label } from '@components/ui/label'
import { InputOTP, InputOTPGroup, InputOTPSlot } from '@components/ui/input-otp'
import { RadioGroup, RadioGroupItem } from '@components/ui/radio-group'

// ─── Types ────────────────────────────────────────────────────────────────────

interface FormFields {
  phone: string
  firstname: string
  lastname: string
  dob: string
  keepMeFor: string
}

type Step = 'form' | 'otp' | 'success'

interface Props {
  open: boolean
  onOpenChange: (open: boolean) => void
}

// ─── Constants ────────────────────────────────────────────────────────────────

const OTP_RESEND_COOLDOWN = 60

const KEEP_ME_FOR_OPTIONS = [
  { value: '7d', label: '7 days', hint: 'Recommended' },
  { value: '30d', label: '30 days', hint: 'Longer access' },
  { value: '90d', label: '90 days', hint: 'Extended demo' },
] as const

// ─── Component ───────────────────────────────────────────────────────────────

export function RegisterDialog({ open, onOpenChange }: Props) {
  const [step, setStep] = useState<Step>('form')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [savedInput, setSavedInput] = useState<Omit<RegisterInput, 'otp'> | null>(null)
  const [result, setResult] = useState<RegisterResult | null>(null)
  const [otp, setOtp] = useState('')
  const [countdown, setCountdown] = useState(0)

  const {
    register,
    handleSubmit,
    reset,
    setValue,
    watch,
    formState: { errors },
  } = useForm<FormFields>({
    defaultValues: {
      keepMeFor: '7d',
    },
  })

  const selectedKeepMeFor = watch('keepMeFor')

  // Reset state when dialog closes
  useEffect(() => {
    if (!open) {
      setTimeout(() => {
        setStep('form')
        setError(null)
        setOtp('')
        setSavedInput(null)
        setResult(null)
        setCountdown(0)
        reset()
      }, 300) // wait for close animation
    }
  }, [open, reset])

  // Resend OTP countdown timer
  useEffect(() => {
    if (countdown <= 0) return
    const id = setTimeout(() => setCountdown((c) => c - 1), 1000)
    return () => clearTimeout(id)
  }, [countdown])

  // ── Step 1: Request OTP ────────────────────────────────────────────────────

  async function onFormSubmit(fields: FormFields) {
    setLoading(true)
    setError(null)
    const input: Omit<RegisterInput, 'otp'> = {
      phone: fields.phone.trim(),
      firstname: fields.firstname.trim(),
      lastname: fields.lastname.trim(),
      ...(fields.dob ? { dob: fields.dob } : {}),
      keepMeFor: fields.keepMeFor,
    }
    try {
      await requestOtp(input)
      setSavedInput(input)
      setStep('otp')
      setCountdown(OTP_RESEND_COOLDOWN)
      toast.success('OTP sent to your WhatsApp!')
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to send OTP'
      setError(msg)
      toast.error(msg)
    } finally {
      setLoading(false)
    }
  }

  // ── Step 2: Verify OTP ─────────────────────────────────────────────────────

  async function onVerifyOtp() {
    if (!savedInput || otp.length !== 6) return
    setLoading(true)
    setError(null)
    try {
      const data = await verifyOtp({ ...savedInput, otp })
      setResult(data)
      setStep('success')
      toast.success('Registration complete!')
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Invalid or expired OTP'
      setError(msg)
      toast.error(msg)
    } finally {
      setLoading(false)
    }
  }

  async function onResendOtp() {
    if (!savedInput || countdown > 0) return
    setLoading(true)
    setError(null)
    try {
      await requestOtp(savedInput)
      setOtp('')
      setCountdown(OTP_RESEND_COOLDOWN)
      toast.success('OTP resent!')
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to resend OTP'
      setError(msg)
    } finally {
      setLoading(false)
    }
  }

  // ─── Render ─────────────────────────────────────────────────────────────────

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md dark border-slate-700 bg-slate-900 text-slate-100">
        <AnimatePresence mode="wait">

          {/* ── Step 1: Registration Form ── */}
          {step === 'form' && (
            <motion.div
              key="form"
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              transition={{ duration: 0.2 }}
            >
              <DialogHeader className="mb-4">
                <DialogTitle className="text-xl text-white">Create your account</DialogTitle>
                <DialogDescription className="text-slate-400">
                  Enter your details and we'll send an OTP to your WhatsApp.
                </DialogDescription>
              </DialogHeader>

              <form onSubmit={handleSubmit(onFormSubmit)} className="space-y-4">
                {/* Phone */}
                <div className="space-y-1.5">
                  <Label htmlFor="phone" className="text-slate-300">
                    Mobile Number <span className="text-rose-400">*</span>
                  </Label>
                  <Input
                    id="phone"
                    type="tel"
                    placeholder="9876543210"
                    inputMode="numeric"
                    className="border-slate-700 bg-slate-800 text-white placeholder:text-slate-500 focus-visible:ring-teal-500"
                    {...register('phone', {
                      required: 'Mobile number is required',
                      pattern: {
                        value: /^(\+91)?[6-9]\d{9}$/,
                        message: 'Enter a valid 10-digit Indian mobile number',
                      },
                    })}
                  />
                  {errors.phone && (
                    <p className="text-xs text-rose-400">{errors.phone.message}</p>
                  )}
                </div>

                {/* Name row */}
                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-1.5">
                    <Label htmlFor="firstname" className="text-slate-300">
                      First Name <span className="text-rose-400">*</span>
                    </Label>
                    <Input
                      id="firstname"
                      placeholder="Riya"
                      className="border-slate-700 bg-slate-800 text-white placeholder:text-slate-500 focus-visible:ring-teal-500"
                      {...register('firstname', { required: 'Required' })}
                    />
                    {errors.firstname && (
                      <p className="text-xs text-rose-400">{errors.firstname.message}</p>
                    )}
                  </div>

                  <div className="space-y-1.5">
                    <Label htmlFor="lastname" className="text-slate-300">
                      Last Name <span className="text-rose-400">*</span>
                    </Label>
                    <Input
                      id="lastname"
                      placeholder="Sharma"
                      className="border-slate-700 bg-slate-800 text-white placeholder:text-slate-500 focus-visible:ring-teal-500"
                      {...register('lastname', { required: 'Required' })}
                    />
                    {errors.lastname && (
                      <p className="text-xs text-rose-400">{errors.lastname.message}</p>
                    )}
                  </div>
                </div>

                {/* Date of Birth (optional) */}
                <div className="space-y-1.5">
                  <Label htmlFor="dob" className="text-slate-300">
                    Date of Birth{' '}
                    <span className="text-slate-500 text-xs font-normal">(optional)</span>
                  </Label>
                  <Input
                    id="dob"
                    type="date"
                    className="border-slate-700 bg-slate-800 text-white placeholder:text-slate-500 focus-visible:ring-teal-500 [color-scheme:dark]"
                    {...register('dob')}
                  />
                </div>

                <div className="space-y-2">
                  <Label className="text-slate-300">Keep me signed in for</Label>
                  <input type="hidden" {...register('keepMeFor')} />
                  <RadioGroup
                    value={selectedKeepMeFor}
                    onValueChange={(value) => setValue('keepMeFor', value, { shouldDirty: true })}
                    className="grid grid-cols-1 gap-2 sm:grid-cols-3"
                  >
                    {KEEP_ME_FOR_OPTIONS.map((option) => {
                      const inputId = `keep-me-for-${option.value}`
                      return (
                        <div key={option.value} className="relative">
                          <RadioGroupItem
                            id={inputId}
                            value={option.value}
                            className="peer sr-only"
                          />
                          <Label
                            htmlFor={inputId}
                            className="flex cursor-pointer flex-col rounded-xl border border-slate-700 bg-slate-800/70 px-3 py-2.5 text-left transition-colors peer-focus-visible:ring-2 peer-focus-visible:ring-teal-400 peer-focus-visible:ring-offset-2 peer-focus-visible:ring-offset-slate-900 peer-data-[state=checked]:border-teal-400 peer-data-[state=checked]:bg-teal-500/10"
                          >
                            <span className="text-sm font-semibold text-white">{option.label}</span>
                            <span className="mt-1 text-xs text-slate-400">{option.hint}</span>
                          </Label>
                        </div>
                      )
                    })}
                  </RadioGroup>
                </div>

                {/* Error */}
                {error && (
                  <p className="rounded-lg border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-sm text-rose-400">
                    {error}
                  </p>
                )}

                <Button
                  type="submit"
                  disabled={loading}
                  className="w-full bg-gradient-to-r from-teal-500 to-cyan-600 text-white hover:opacity-90 disabled:opacity-60"
                >
                  {loading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                  {loading ? 'Sending OTP…' : 'Send OTP via WhatsApp'}
                </Button>
              </form>
            </motion.div>
          )}

          {/* ── Step 2: OTP Verification ── */}
          {step === 'otp' && savedInput && (
            <motion.div
              key="otp"
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              transition={{ duration: 0.2 }}
            >
              <DialogHeader className="mb-4">
                <DialogTitle className="text-xl text-white">Verify your number</DialogTitle>
                <DialogDescription className="text-slate-400">
                  Enter the 6-digit OTP sent to{' '}
                  <span className="font-medium text-teal-400">{savedInput.phone}</span> via
                  WhatsApp.
                </DialogDescription>
              </DialogHeader>

              <div className="space-y-5">
                {/* Summary */}
                <div className="rounded-lg border border-slate-700 bg-slate-800/50 px-4 py-3 text-sm text-slate-300">
                  <span className="font-medium text-white">
                    {savedInput.firstname} {savedInput.lastname}
                  </span>
                  {savedInput.dob && (
                    <span className="ml-2 text-slate-400">· DOB: {savedInput.dob}</span>
                  )}
                </div>

                {/* OTP input */}
                <div className="flex flex-col items-center gap-3">
                  <InputOTP
                    maxLength={6}
                    value={otp}
                    onChange={setOtp}
                    autoComplete="one-time-code"
                  >
                    <InputOTPGroup>
                      {[0, 1, 2, 3, 4, 5].map((i) => (
                        <InputOTPSlot
                          key={i}
                          index={i}
                          className="border-slate-600 bg-slate-800 text-white"
                        />
                      ))}
                    </InputOTPGroup>
                  </InputOTP>

                  <button
                    type="button"
                    onClick={onResendOtp}
                    disabled={countdown > 0 || loading}
                    className="text-sm text-teal-400 hover:underline disabled:cursor-not-allowed disabled:text-slate-500"
                  >
                    {countdown > 0 ? `Resend OTP in ${countdown}s` : 'Resend OTP'}
                  </button>
                </div>

                {/* Error */}
                {error && (
                  <p className="rounded-lg border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-sm text-rose-400">
                    {error}
                  </p>
                )}

                <div className="flex gap-3">
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => { setStep('form'); setError(null) }}
                    className="flex-1 border-slate-700 text-slate-300 hover:bg-slate-800"
                  >
                    Back
                  </Button>
                  <Button
                    type="button"
                    onClick={onVerifyOtp}
                    disabled={otp.length !== 6 || loading}
                    className="flex-1 bg-gradient-to-r from-teal-500 to-cyan-600 text-white hover:opacity-90 disabled:opacity-60"
                  >
                    {loading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                    {loading ? 'Verifying…' : 'Verify OTP'}
                  </Button>
                </div>
              </div>
            </motion.div>
          )}

          {/* ── Step 3: Success ── */}
          {step === 'success' && result && (
            <motion.div
              key="success"
              initial={{ opacity: 0, scale: 0.96 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ duration: 0.25 }}
              className="flex flex-col items-center gap-4 py-4 text-center"
            >
              <motion.div
                initial={{ scale: 0, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                transition={{ delay: 0.1, type: 'spring', stiffness: 200 }}
              >
                <CheckCircle2 className="h-16 w-16 text-teal-400" />
              </motion.div>

              <div>
                <h3 className="text-xl font-semibold text-white">Welcome aboard!</h3>
                <p className="mt-1 text-slate-400">
                  {result.user
                    ? `Hello, ${result.user.firstname} ${result.user.lastname}`
                    : result.message}
                </p>
              </div>

              <div className="w-full rounded-lg border border-slate-700 bg-slate-800/50 px-4 py-3 text-sm text-slate-300 space-y-1">
                {result.loansCreated > 0 && (
                  <p>
                    <span className="text-teal-400 font-medium">{result.loansCreated}</span>{' '}
                    mock loan{result.loansCreated > 1 ? 's' : ''} created for you
                  </p>
                )}
                {result.expiresAt && (
                  <p className="text-slate-400 text-xs">
                    Demo account expires:{' '}
                    {new Date(result.expiresAt).toLocaleDateString('en-IN', {
                      day: 'numeric',
                      month: 'short',
                      year: 'numeric',
                    })}
                  </p>
                )}
              </div>

              <p className="text-xs text-slate-500">
                You can now use the chatbot to explore your loan details.
              </p>

              <Button
                onClick={() => onOpenChange(false)}
                className="w-full bg-gradient-to-r from-teal-500 to-cyan-600 text-white hover:opacity-90"
              >
                Start Exploring
              </Button>
            </motion.div>
          )}

        </AnimatePresence>
      </DialogContent>
    </Dialog>
  )
}
