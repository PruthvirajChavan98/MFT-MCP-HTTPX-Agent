// src/components/MessageItem.tsx
import { Component, Show } from 'solid-js';
import { Bot, User } from 'lucide-solid';
import clsx from 'clsx';
import MarkdownMessage from './MarkdownMessage';
import ReasoningAccordion from './ReasoningAccordion';
import FollowUpChips from './FollowUpChips';
import RouterWidget from './RouterWidget';
import type { Message } from '../types/chat';

interface MessageItemProps {
  message: Message;
  isGenerating: boolean;
  onFollowUpClick: (question: string) => void;
  followUpStatus?: string | null;
}

const MessageItem: Component<MessageItemProps> = (props) => {
  const isUser = () => props.message.role === 'user';
  const isAssistant = () => props.message.role === 'assistant';

  return (
    <div
      class={clsx(
        'group flex gap-4 transition-all duration-300 animate-fade-in',
        isUser() ? 'flex-row-reverse' : 'flex-row',
      )}
    >
      {/* Avatar */}
      <div
        class={clsx(
          'flex h-8 w-8 shrink-0 items-center justify-center rounded-full border shadow-sm mt-1',
          isUser()
            ? 'bg-white text-slate-600 border-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:border-slate-700'
            : 'bg-indigo-100 text-indigo-600 border-indigo-200 dark:bg-indigo-900/30 dark:text-indigo-300 dark:border-indigo-800',
        )}
      >
        {isUser() ? <User size={16} /> : <Bot size={16} />}
      </div>

      {/* Bubble Container */}
      <div
        class={clsx(
          'flex min-w-0 max-w-[85%] flex-col shadow-sm relative',
          isUser()
            ? 'rounded-2xl rounded-tr-sm bg-slate-900 text-white dark:bg-slate-800'
            : 'w-full rounded-2xl rounded-tl-sm bg-white border border-slate-200 dark:bg-slate-900 dark:border-slate-800',
        )}
      >
        {/* Reasoning Block */}
        <Show when={isAssistant() && props.message.reasoning}>
          <div
            class="border-b border-slate-100 bg-slate-50/50 px-4 py-2 dark:border-slate-800 dark:bg-slate-900/50 rounded-tl-sm rounded-tr-2xl"
          >
            <ReasoningAccordion reasoning={props.message.reasoning!} isStreaming={!!props.message.isStreaming} />
          </div>
        </Show>

        {/* Content Block */}
        <div
          class={clsx(
            'px-5 py-3 text-[15px] leading-relaxed',
            isUser() ? 'whitespace-pre-wrap font-medium' : '',
            isAssistant()
              ? props.message.reasoning
                ? 'rounded-bl-2xl rounded-br-2xl'
                : 'rounded-tl-sm rounded-tr-2xl rounded-bl-2xl rounded-br-2xl'
              : '',
          )}
        >
          {/* ✅ Router Widget */}
          <Show when={isAssistant() && props.message.router}>
            <RouterWidget payload={props.message.router} />
          </Show>

          <Show when={isAssistant()} fallback={props.message.content}>
            <MarkdownMessage content={props.message.content} />
          </Show>

          <Show when={props.message.isStreaming && isAssistant()}>
            <span class="inline-block h-4 w-1 animate-pulse bg-indigo-500 align-middle ml-1 rounded-full" />
          </Show>

          {/* Follow-Up Chips */}
          <Show when={isAssistant() && ((props.message.followUpCandidates?.length ?? 0) > 0 || !!props.followUpStatus)}>
            <FollowUpChips
              candidates={props.message.followUpCandidates ?? []}
              isGenerating={props.isGenerating}
              onSelect={props.onFollowUpClick}
              status={props.followUpStatus}
            />
          </Show>
        </div>
      </div>
    </div>
  );
};

export default MessageItem;
