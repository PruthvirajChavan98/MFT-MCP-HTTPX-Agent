import { Component, createMemo, Show } from 'solid-js';
import { unified } from 'unified';
import remarkParse from 'remark-parse';
import remarkGfm from 'remark-gfm';
import remarkRehype from 'remark-rehype';
import rehypeStringify from 'rehype-stringify';
import { chatActions } from '../stores/chat';
import clsx from 'clsx';

/**
 * Production-Grade Markdown Renderer
 * Implementation Strategy: AST-to-HTML with incremental reactivity.
 */

interface MarkdownMessageProps {
  content: string;
  isStreaming?: boolean;
}

const MarkdownMessage: Component<MarkdownMessageProps> = (props) => {
  // Processor configured once for efficiency
  const processor = unified()
    .use(remarkParse)
    .use(remarkGfm)
    .use(remarkRehype, { allowDangerousHtml: true })
    .use(rehypeStringify);

  /**
   * Memoized HTML generation.
   * SolidJS's createMemo ensures we only re-process the markdown
   * when the content string actually changes.
   */
  const htmlContent = createMemo(() => {
    try {
      return processor.processSync(props.content).toString();
    } catch (e) {
      console.error("Markdown Rendering Error:", e);
      return props.content;
    }
  });

  const handleLinkClick = (e: MouseEvent) => {
    const target = e.target as HTMLElement;
    const anchor = target.closest('a');
    if (!anchor) return;

    const href = anchor.getAttribute('href');
    if (href?.startsWith('input:')) {
      e.preventDefault();
      chatActions.setInput(decodeURIComponent(href.substring(6)));
      document.getElementById('chat-input-textarea')?.focus();
    }
    if (href?.startsWith('run:')) {
      e.preventDefault();
      chatActions.setInput(decodeURIComponent(href.substring(4)));
      setTimeout(() => window.dispatchEvent(new Event('chat:submit')), 0);
    }
  };

  return (
    <div
      class="markdown-content relative leading-relaxed"
      onClick={handleLinkClick}
    >
      <div
        class={clsx(
          "prose prose-slate dark:prose-invert max-w-none transition-all duration-200",
          props.isStreaming && "cursor-wait"
        )}
        innerHTML={htmlContent()}
      />

      <Show when={props.isStreaming}>
        <span class="inline-block h-4 w-1 animate-pulse bg-indigo-500 align-middle ml-1 rounded-full" />
      </Show>
    </div>
  );
};

export default MarkdownMessage;
