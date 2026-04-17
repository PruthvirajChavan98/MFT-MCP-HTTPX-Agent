import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Loader2, ShieldCheck, Trash2, UserPlus } from 'lucide-react'
import { toast } from 'sonner'

import { Alert, AlertDescription } from '@components/ui/alert'
import { Skeleton } from '@components/ui/skeleton'
import { MobileHeader } from '@components/ui/mobile-header'
import { useAdminAuth } from '@features/admin/auth/AdminAuthProvider'
import { MfaCancelled } from '@features/admin/auth/MfaPromptProvider'
import { useMfaPrompt } from '@features/admin/auth/useMfaPrompt'
import { adminsQueryOptions } from '@features/admin/query/queryOptions'
import {
  type AdminUser,
  type CreateAdminResult,
  revokeAdmin,
} from '@features/admin/api/admins'
import { formatDateTime } from '@shared/lib/format'
import { AdminUsersCreateModal } from './AdminUsersCreateModal'

function getErrorMessage(err: unknown): string {
  if (err instanceof Error && err.message.trim()) return err.message
  return 'Request failed'
}

export function AdminUsersPage() {
  const queryClient = useQueryClient()
  const { session } = useAdminAuth()
  const { withMfa } = useMfaPrompt()

  const [modalOpen, setModalOpen] = useState(false)
  const [lastCreated, setLastCreated] = useState<CreateAdminResult | null>(null)

  const { data: admins = [], isLoading, error } = useQuery(adminsQueryOptions())

  const revokeMut = useMutation({
    mutationFn: (row: AdminUser) =>
      withMfa(`revoke admin ${row.email}`, () => revokeAdmin(row.id)),
    onMutate: async (row) => {
      await queryClient.cancelQueries({ queryKey: ['admins'] })
      const snapshot = queryClient.getQueryData<AdminUser[]>(['admins'])
      queryClient.setQueryData<AdminUser[]>(['admins'], (prev) =>
        (prev ?? []).filter((a) => a.id !== row.id),
      )
      return { snapshot }
    },
    onSuccess: () => {
      toast.success('Admin revoked')
    },
    onError: (err, _row, context) => {
      if (context?.snapshot) queryClient.setQueryData(['admins'], context.snapshot)
      if (err instanceof MfaCancelled) return
      toast.error(getErrorMessage(err))
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ['admins'] })
    },
  })

  if (error) {
    return (
      <Alert variant="destructive">
        <AlertDescription>{getErrorMessage(error)}</AlertDescription>
      </Alert>
    )
  }

  const currentSub = session?.sub ?? null

  return (
    <div className="flex flex-col gap-6 px-4 sm:px-8 py-5 sm:py-7">
      <MobileHeader
        title="Admin Users"
        description="Create and revoke non-super-admin accounts. Each enrollment returns a one-time TOTP secret."
        actions={
          <button
            onClick={() => setModalOpen(true)}
            className="flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-medium bg-primary text-primary-foreground hover:bg-primary/90 transition-all active:scale-95"
          >
            <UserPlus size={16} />
            Add Admin
          </button>
        }
      />

      <div className="rounded-xl border border-border bg-card overflow-hidden">
        <div className="flex items-center justify-between border-b border-border px-5 py-3">
          <h2 className="text-sm font-semibold text-foreground">Active admins</h2>
          <span className="text-[10px] font-tabular uppercase tracking-[0.15em] text-muted-foreground">
            {isLoading ? '…' : admins.length} {admins.length === 1 ? 'row' : 'rows'}
          </span>
        </div>
        {isLoading ? (
          <div className="space-y-2 p-4">
            {Array.from({ length: 3 }).map((_, i) => (
              <Skeleton key={i} className="h-12 rounded" />
            ))}
          </div>
        ) : admins.length === 0 ? (
          <div className="p-10 text-center text-sm text-muted-foreground">
            No admins yet. Click <span className="font-medium text-foreground">Add Admin</span> to
            create the first one.
          </div>
        ) : (
          <ul className="divide-y divide-border">
            {admins.map((a) => {
              const isSelf = a.id === currentSub
              const isBusy =
                revokeMut.isPending && revokeMut.variables?.id === a.id
              return (
                <li
                  key={a.id}
                  className="flex items-center gap-4 px-5 py-3 hover:bg-accent/30 transition-colors"
                >
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium text-foreground">
                      {a.email}
                      {isSelf && (
                        <span className="ml-2 rounded bg-muted px-1.5 py-0.5 text-[10px] font-tabular uppercase tracking-[0.15em] text-muted-foreground">
                          you
                        </span>
                      )}
                    </p>
                    <p className="mt-0.5 text-xs font-tabular text-muted-foreground">
                      added {formatDateTime(a.created_at)}
                    </p>
                  </div>
                  {a.is_super_admin ? (
                    <span className="inline-flex items-center gap-1 rounded-full border border-primary/20 bg-primary/10 px-2 py-0.5 text-[10px] font-tabular uppercase tracking-[0.15em] text-primary">
                      <ShieldCheck size={11} /> super admin
                    </span>
                  ) : (
                    <span className="inline-flex items-center rounded-full border border-border bg-muted px-2 py-0.5 text-[10px] font-tabular uppercase tracking-[0.15em] text-muted-foreground">
                      admin
                    </span>
                  )}
                  <button
                    type="button"
                    disabled={isSelf || isBusy}
                    onClick={() => {
                      if (
                        window.confirm(
                          `Revoke ${a.email}? Their sessions will stop working on the next refresh.`,
                        )
                      ) {
                        revokeMut.mutate(a)
                      }
                    }}
                    className="rounded-md p-2 text-muted-foreground transition-colors hover:bg-destructive/10 hover:text-destructive disabled:opacity-40 disabled:cursor-not-allowed"
                    aria-label={`Revoke ${a.email}`}
                    title={isSelf ? 'You cannot revoke your own account' : 'Revoke'}
                  >
                    {isBusy ? (
                      <Loader2 size={14} className="animate-spin" />
                    ) : (
                      <Trash2 size={14} />
                    )}
                  </button>
                </li>
              )
            })}
          </ul>
        )}
      </div>

      {(modalOpen || lastCreated) && (
        <AdminUsersCreateModal
          open={modalOpen || Boolean(lastCreated)}
          created={lastCreated}
          onSuccess={(result) => {
            setLastCreated(result)
            setModalOpen(false)
            queryClient.invalidateQueries({ queryKey: ['admins'] })
          }}
          onClose={() => {
            setModalOpen(false)
            setLastCreated(null)
          }}
        />
      )}
    </div>
  )
}
