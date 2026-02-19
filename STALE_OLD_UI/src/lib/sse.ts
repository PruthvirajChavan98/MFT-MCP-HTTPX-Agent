import { Env } from '../config/env';

export type SSECallback = (event: string, data: string) => void;

export class SSESubscription {
  private controller: AbortController;
  private decoder = new TextDecoder();

  constructor(
    private url: string,
    private body: any,
    private onEvent: SSECallback,
    private onDone: () => void,
    private onError: (err: Error) => void
  ) {
    this.controller = new AbortController();
  }

  async start() {
    try {
      const response = await fetch(`${Env.API_BASE_URL}${this.url}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(this.body),
        signal: this.controller.signal,
      });

      if (!response.body) throw new Error('No readable stream');

      const reader = response.body.getReader();
      let partialLine = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = this.decoder.decode(value, { stream: true });
        const lines = (partialLine + chunk).split('\n\n');
        partialLine = lines.pop() ?? '';

        for (const block of lines) {
          if (!block.trim()) continue;
          this.parseSSEBlock(block);
        }
      }
      this.onDone();
    } catch (err: any) {
      if (err.name === 'AbortError') return;
      this.onError(err);
    }
  }

  private parseSSEBlock(block: string) {
    const lines = block.split('\n');
    let event = 'message';
    let data = '';

    for (const line of lines) {
      if (line.startsWith('event:')) event = line.slice(6).trim();
      else if (line.startsWith('data:')) {
        const content = line.slice(5);
        data += content.startsWith(' ') ? content.slice(1) : content;
      }
    }
    this.onEvent(event, data);
  }

  cancel() {
    this.controller.abort();
  }
}
