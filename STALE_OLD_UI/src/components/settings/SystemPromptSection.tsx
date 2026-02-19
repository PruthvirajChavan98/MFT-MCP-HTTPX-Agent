import { Component } from 'solid-js';

interface SystemPromptSectionProps {
  systemPrompt: string;
  setSystemPrompt: (val: string) => void;
  defaultPrompt: string;
}

const SystemPromptSection: Component<SystemPromptSectionProps> = (props) => {
  return (
    <div class="space-y-2">
      <label class="block text-sm font-medium text-slate-700 dark:text-slate-300">
        System Prompt
      </label>
      <textarea
        value={props.systemPrompt}
        onInput={(e) => props.setSystemPrompt(e.currentTarget.value)}
        rows={8}
        class="w-full rounded-xl border border-slate-300 bg-white p-4 text-sm font-mono leading-relaxed focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-200"
        placeholder={props.defaultPrompt}
      />
    </div>
  );
};

export default SystemPromptSection;
