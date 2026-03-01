import { useEffect } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { fetchEventSource } from '@microsoft/fetch-event-source';
import { API_BASE_URL } from '@shared/api/http';

const SSE_URL_BASE = API_BASE_URL + '/live/session';

export function useLiveSessionFeed(sessionId?: string, adminKey?: string) {
    const queryClient = useQueryClient();

    useEffect(() => {
        if (!sessionId || !adminKey) return;

        const controller = new AbortController();

        fetchEventSource(`${SSE_URL_BASE}/${sessionId}`, {
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
                if (ev.event === 'session_tick') {
                    const data = JSON.parse(ev.data);
                    queryClient.setQueryData(['session', sessionId], (oldData: any) => {
                        if (!oldData) return oldData;
                        return { ...oldData, session_cost: data.new_total };
                    });
                }
            },
            onclose() {
                console.log(`[SSE Session ${sessionId}] closed`);
            },
            onerror(err) {
                console.error(`[SSE Session ${sessionId}] Connection Error:`, err);
            }
        });

        return () => {
            controller.abort();
        };
    }, [sessionId, adminKey, queryClient]);
}
