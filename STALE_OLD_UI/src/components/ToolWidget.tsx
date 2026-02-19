import { Component, Show } from 'solid-js';
import { Loader2 } from 'lucide-solid';
import { CheckCircle2 } from 'lucide-solid';
import { XCircle } from 'lucide-solid';
import { Terminal } from 'lucide-solid';
import clsx from 'clsx';

interface ToolWidgetProps {
  name: string;
  input: any;
  status: 'calling' | 'success' | 'error';
  result?: any;
}

const ToolWidget: Component<ToolWidgetProps> = (props) => {
  return (
    <div class="my-2 overflow-hidden rounded-md border border-slate-200 bg-slate-50 text-xs font-mono dark:border-slate-800 dark:bg-slate-900/50">
      <div class="flex items-center justify-between border-b border-slate-200 px-3 py-2 dark:border-slate-800">
        <div class="flex items-center gap-2">
          <Terminal size={14} class="text-slate-500" />
          <span class="font-semibold text-slate-700 dark:text-slate-300">
            {props.name}
          </span>
        </div>
        <div class="flex items-center gap-2">
          <Show
            when={props.status !== 'calling'}
            fallback={<Loader2 size={14} class="animate-spin text-blue-500" />}
          >
            <Show
              when={props.status === 'success'}
              fallback={<XCircle size={14} class="text-red-500" />}
            >
              <CheckCircle2 size={14} class="text-green-500" />
            </Show>
          </Show>
          <span
            class={clsx(
              'capitalize',
              props.status === 'calling' && 'text-blue-500',
              props.status === 'success' && 'text-green-500',
              props.status === 'error' && 'text-red-500'
            )}
          >
            {props.status}
          </span>
        </div>
      </div>

      <div class="p-3">
        <div class="mb-1 text-slate-500">Input:</div>
        <pre class="overflow-x-auto whitespace-pre-wrap rounded bg-slate-100 p-2 text-slate-600 dark:bg-slate-950 dark:text-slate-400">
          {JSON.stringify(props.input, null, 2)}
        </pre>

        <Show when={props.result}>
          <div class="mt-2 mb-1 text-slate-500">Result:</div>
          <pre class="max-h-32 overflow-y-auto overflow-x-auto whitespace-pre-wrap rounded bg-slate-100 p-2 text-slate-600 dark:bg-slate-950 dark:text-slate-400">
            {typeof props.result === 'string' ? props.result : JSON.stringify(props.result, null, 2)}
          </pre>
        </Show>
      </div>
    </div>
  );
};

export default ToolWidget;
