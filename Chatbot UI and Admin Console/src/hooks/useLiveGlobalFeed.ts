import { useEffect } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { fetchEventSource } from '@microsoft/fetch-event-source';
import { API_BASE_URL } from '../shared/api/http';

const SSE_URL = API_BASE_URL + '/live/global';

export function useLiveGlobalFeed(adminKey: string) {
    const queryClient = useQueryClient();

    useEffect(() => {
        if (!adminKey) return;

        const controller = new AbortController();

        fetchEventSource(SSE_URL, {
            method: 'GET',
            headers: {
                'X-Admin-Key': adminKey,
                'Accept': 'text/event-stream',
            },
            signal: controller.signal,
            onopen: async (response) => {
                if (!response.ok) {
                    throw new Error(`Connection failed: ${response.status}`);
                }
            },
            onmessage(ev) {
                if (ev.event === 'connected') {
                    console.log('[SSE] Global feed established');
                } else if (ev.event === 'cost_update') {
                    const data = JSON.parse(ev.data);
                    queryClient.setQueryData(['session-cost-summary'], (oldData: any) => {
                        if (!oldData) return oldData;
                        return {
                            ...oldData,
                            total_cost: data.new_total,
                            sessions: (oldData.sessions || []).map((s: any) =>
                                s.session_id === data.session_id ? { ...s, total_cost: data.new_total } : s
                            )
                        };
                    });
                } else if (ev.event === 'risk_denied') {
                    const data = JSON.parse(ev.data);
                    toast.error('Security Policy Intervention', {
                        description: `IP: ${data.ip} | Session: ${data.session_id} | Path: ${data.path}`,
                        duration: 8000,
                    });
                }
            },
            onclose() {
                console.log('[SSE] Global feed closed');
            },
            onerror(err) {
                console.error('[SSE] Connection Error:', err);
            }
        });

        return () => {
            controller.abort();
        };
    }, [adminKey, queryClient]);
}
