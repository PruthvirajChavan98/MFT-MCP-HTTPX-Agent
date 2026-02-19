import { useState, useEffect, useCallback } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { toast } from 'sonner'
import { fetchSessionConfig, saveSessionConfig } from '../../../shared/api/admin'
import { useAvailableModels } from '../../../shared/hooks/useModels'
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
import { Cpu, Save, Search, Server, Sparkles } from 'lucide-react'

export function ModelConfig() {
  const auth = useAdminContext()
  const [sessionId, setSessionId] = useState('')
  const [fetchedSession, setFetchedSession] = useState('')

  const [config, setConfig] = useState({
    model_name: '',
    provider: 'groq',
    reasoning_effort: 'medium',
    system_prompt: ''
  })

  const [temperature, setTemperature] = useState([0.3])

  const handleModelChange = useCallback((newModelId: string) => {
    setConfig((prev) => ({ ...prev, model_name: newModelId }));
  }, []);

  // 🚀 Invoke the Shared Global Hook
  const { availableModels, isLoading: mLoading } = useAvailableModels(
    config.provider,
    config.model_name,
    handleModelChange
  );

  // Fetch specific session config
  const { data: sessionCfg, isLoading: sCfgLoading, refetch } = useQuery({
    queryKey: ['session-config', fetchedSession],
    queryFn: () => fetchSessionConfig(fetchedSession),
    enabled: !!fetchedSession,
  })

  // Hydrate config state when loaded
  useEffect(() => {
    if (sessionCfg) {
      setConfig({
        model_name: sessionCfg.model_name ?? '',
        provider: sessionCfg.provider ?? 'groq',
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
    onSuccess: () => toast.success('Configuration successfully deployed'),
    onError: (e) => toast.error((e as Error).message),
  })

  if (!auth.adminKey) {
    return (
      <Alert className="max-w-2xl mt-6 border-amber-200 bg-amber-50 text-amber-800">
        <AlertDescription className="font-medium">
          Admin API Key is missing. Please configure it in the top header to manage models.
        </AlertDescription>
      </Alert>
    )
  }

  return (
    <div className="space-y-6 max-w-4xl mx-auto pb-10">
      <div>
        <h1 className="text-2xl text-gray-900 tracking-tight" style={{ fontWeight: 700 }}>Model Configuration</h1>
        <p className="text-gray-500 text-sm mt-1">Manage execution parameters, logic paths, and provider assignments.</p>
      </div>

      {/* Target Session */}
      <Card className="border-gray-200 shadow-sm">
        <CardHeader className="bg-gray-50/50 border-b border-gray-100 pb-4">
          <CardTitle className="text-sm font-bold flex items-center gap-2">
            <Server size={16} className="text-cyan-600" /> Target Session Context
          </CardTitle>
        </CardHeader>
        <CardContent className="pt-6">
          <div className="flex flex-col sm:flex-row gap-3">
            <div className="relative flex-1">
              <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
              <Input
                value={sessionId}
                onChange={(e) => setSessionId(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && !!sessionId.trim() && (setFetchedSession(sessionId), refetch())}
                placeholder="Enter Session ID to override..."
                className="pl-9 text-sm font-mono bg-gray-50 h-10"
              />
            </div>
            <Button
              className="h-10 px-6 font-semibold"
              onClick={() => { setFetchedSession(sessionId); refetch() }}
              disabled={!sessionId.trim()}
            >
              Load Config
            </Button>
          </div>
          {sCfgLoading && <Skeleton className="h-10 w-full mt-4 rounded-lg" />}
        </CardContent>
      </Card>

      <div className="grid md:grid-cols-2 gap-6">
        {/* Engine Config */}
        <Card className="border-gray-200 shadow-sm">
          <CardHeader className="bg-gray-50/50 border-b border-gray-100 pb-4">
            <CardTitle className="text-sm font-bold flex items-center gap-2">
              <Cpu size={16} className="text-indigo-500" /> Inference Engine
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-6 pt-6">
            <div className="space-y-2">
              <Label className="text-xs font-bold uppercase tracking-wider text-gray-500">Provider Vendor</Label>
              <Select value={config.provider} onValueChange={(v) => setConfig((p) => ({ ...p, provider: v }))}>
                <SelectTrigger className="h-10 text-sm font-medium">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="groq">Groq (LPU - Fastest)</SelectItem>
                  <SelectItem value="openrouter">OpenRouter (Aggregator)</SelectItem>
                  <SelectItem value="nvidia">NVIDIA NIM</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label className="text-xs font-bold uppercase tracking-wider text-gray-500">Model Selection</Label>
              {mLoading ? <Skeleton className="h-10 rounded-md w-full" /> : (
                <Select value={config.model_name} onValueChange={(v) => setConfig((p) => ({ ...p, model_name: v }))}>
                  <SelectTrigger className="h-10 text-sm font-medium">
                    <SelectValue placeholder="Select model..." />
                  </SelectTrigger>
                  <SelectContent className="max-h-[300px]">
                    {availableModels.map((m: any) => (
                      <SelectItem key={m.id} value={m.id}>
                        <div className="flex items-center justify-between w-full pr-4">
                          <span>{m.name || m.id}</span>
                          {m.type === 'reasoning' && <span className="ml-2 text-[10px] bg-purple-100 text-purple-700 px-1.5 py-0.5 rounded uppercase font-bold tracking-wider">Reasoning</span>}
                        </div>
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
            </div>

            <div className="space-y-4 pt-2">
              <div className="flex items-center justify-between">
                <Label className="text-xs font-bold uppercase tracking-wider text-gray-500">Temperature</Label>
                <span className="text-xs font-mono font-bold bg-gray-100 px-2 py-0.5 rounded text-gray-700">{temperature[0].toFixed(2)}</span>
              </div>
              <Slider min={0} max={2} step={0.01} value={temperature} onValueChange={setTemperature} className="w-full cursor-grab" />
            </div>
          </CardContent>
        </Card>

        {/* Reasoning & Behavior */}
        <Card className="border-gray-200 shadow-sm flex flex-col">
          <CardHeader className="bg-gray-50/50 border-b border-gray-100 pb-4">
            <CardTitle className="text-sm font-bold flex items-center gap-2">
              <Sparkles size={16} className="text-amber-500" /> Behavior & Reasoning
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-6 pt-6 flex-1 flex flex-col">
            <div className="space-y-2">
              <Label className="text-xs font-bold uppercase tracking-wider text-gray-500">Reasoning Effort</Label>
              <Select value={config.reasoning_effort} onValueChange={(v) => setConfig((p) => ({ ...p, reasoning_effort: v }))}>
                <SelectTrigger className="h-10 text-sm font-medium">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="low">Low (Fastest)</SelectItem>
                  <SelectItem value="medium">Medium (Balanced)</SelectItem>
                  <SelectItem value="high">High (Deep Thinking)</SelectItem>
                </SelectContent>
              </Select>
              <p className="text-[10px] text-gray-400 mt-1">Only applicable for reasoning models (o1, o3, deepseek-r1).</p>
            </div>

            <div className="space-y-2 flex-1 flex flex-col">
              <div className="flex items-center justify-between">
                <Label className="text-xs font-bold uppercase tracking-wider text-gray-500">System Prompt</Label>
                <span className="text-[10px] font-mono text-gray-400">{config.system_prompt.length} chars</span>
              </div>
              <Textarea
                value={config.system_prompt}
                onChange={(e) => setConfig((p) => ({ ...p, system_prompt: e.target.value }))}
                className="flex-1 min-h-[140px] text-sm font-mono resize-none bg-gray-50 border-gray-200 focus:border-cyan-500 focus:ring-cyan-500/20"
                placeholder="You are an expert AI assistant..."
              />
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="flex justify-end pt-4">
        <Button
          size="lg"
          onClick={() => saveMut.mutate()}
          disabled={saveMut.isPending || !config.model_name || !sessionId.trim()}
          className="w-full sm:w-auto font-bold text-white shadow-lg disabled:opacity-50 bg-gradient-to-r from-cyan-500 to-teal-500 hover:from-cyan-600 hover:to-teal-600 border-0"
        >
          {saveMut.isPending ? 'Committing Changes...' : <><Save className="w-4 h-4 mr-2" /> Commit to Session</>}
        </Button>
      </div>
    </div>
  )
}