import { useState, useEffect } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { toast } from 'sonner'
import { fetchModels, fetchSessionConfig, saveSessionConfig } from '../../../shared/api/admin'
import { useAdminContext } from './AdminContext'
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card'
import { Button } from '../ui/button'
import { Input } from '../ui/input'
import { Textarea } from '../ui/textarea'
import { Label } from '../ui/label'
import { Slider } from '../ui/slider'
import { Alert, AlertDescription } from '../ui/alert'
import { Skeleton } from '../ui/skeleton'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../ui/select'

export function ModelConfig() {
  const auth = useAdminContext()
  const [sessionId, setSessionId] = useState('')
  const [fetchedSession, setFetchedSession] = useState('')
  const [config, setConfig] = useState({ model_name: '', provider: 'openrouter', reasoning_effort: 'medium', system_prompt: '' })
  const [temperature, setTemperature] = useState([0.3])

  const { data: models = [], isLoading: mLoading } = useQuery({ queryKey: ['models'], queryFn: fetchModels })

  const { data: sessionCfg, isLoading: sCfgLoading, refetch } = useQuery({
    queryKey: ['session-config', fetchedSession],
    queryFn: () => fetchSessionConfig(fetchedSession),
    enabled: !!fetchedSession,
  })

  useEffect(() => {
    if (sessionCfg) {
      setConfig({
        model_name: sessionCfg.model_name ?? '',
        provider: sessionCfg.provider ?? 'openrouter',
        reasoning_effort: sessionCfg.reasoning_effort ?? 'medium',
        system_prompt: sessionCfg.system_prompt ?? '',
      })
    }
  }, [sessionCfg])

  const saveMut = useMutation({
    mutationFn: () =>
      saveSessionConfig({
        session_id: fetchedSession || sessionId,
        ...config,
        openrouter_api_key: auth.openrouterKey || undefined,
        groq_api_key: auth.groqKey || undefined,
      }),
    onSuccess: () => toast.success('Config saved'),
    onError: (e) => toast.error((e as Error).message),
  })

  const allModels = models.flatMap((cat) => cat.models)

  return (
    <div className="space-y-6 max-w-2xl">
      <h1 className="text-xl font-semibold">Model Configuration</h1>

      <Card>
        <CardHeader><CardTitle className="text-sm font-semibold">Session</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          <div className="flex gap-2">
            <Input value={sessionId} onChange={(e) => setSessionId(e.target.value)} placeholder="Session ID" className="text-sm font-mono" />
            <Button size="sm" variant="outline" onClick={() => { setFetchedSession(sessionId); refetch() }}>Load</Button>
          </div>
          {sCfgLoading && <Skeleton className="h-8 rounded" />}
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle className="text-sm font-semibold">Model & Provider</CardTitle></CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1">
              <Label className="text-xs">Model</Label>
              {mLoading ? <Skeleton className="h-10 rounded" /> : (
                <Select value={config.model_name} onValueChange={(v) => setConfig((p) => ({ ...p, model_name: v }))}>
                  <SelectTrigger className="text-sm"><SelectValue placeholder="Select model" /></SelectTrigger>
                  <SelectContent>{allModels.map((m) => <SelectItem key={m.id} value={m.id}>{m.name}</SelectItem>)}</SelectContent>
                </Select>
              )}
            </div>
            <div className="space-y-1">
              <Label className="text-xs">Provider</Label>
              <Select value={config.provider} onValueChange={(v) => setConfig((p) => ({ ...p, provider: v }))}>
                <SelectTrigger className="text-sm"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {['openrouter', 'groq', 'nvidia'].map((p) => <SelectItem key={p} value={p}>{p}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className="space-y-1">
            <Label className="text-xs">Reasoning Effort</Label>
            <Select value={config.reasoning_effort} onValueChange={(v) => setConfig((p) => ({ ...p, reasoning_effort: v }))}>
              <SelectTrigger className="text-sm"><SelectValue /></SelectTrigger>
              <SelectContent>{['low', 'medium', 'high'].map((e) => <SelectItem key={e} value={e}>{e}</SelectItem>)}</SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <Label className="text-xs">Temperature</Label>
              <span className="text-xs font-mono text-muted-foreground">{temperature[0].toFixed(2)}</span>
            </div>
            <Slider min={0} max={2} step={0.01} value={temperature} onValueChange={setTemperature} className="w-full" />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle className="text-sm font-semibold">System Prompt</CardTitle></CardHeader>
        <CardContent className="space-y-2">
          <Textarea value={config.system_prompt} onChange={(e) => setConfig((p) => ({ ...p, system_prompt: e.target.value }))} rows={8} className="text-sm font-mono resize-none" placeholder="You are TrustFin's AI assistant…" />
          <div className="flex items-center justify-between">
            <span className="text-xs text-muted-foreground">{config.system_prompt.length} chars</span>
            <Button size="sm" onClick={() => saveMut.mutate()} disabled={saveMut.isPending}>{saveMut.isPending ? 'Saving…' : 'Save Config'}</Button>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
