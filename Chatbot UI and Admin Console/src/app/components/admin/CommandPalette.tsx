import { useEffect, useState, useCallback } from 'react'
import { useNavigate } from 'react-router'
import {
  BadgeDollarSign,
  Database,
  GitBranch,
  LayoutDashboard,
  MessageSquare,
  Settings,
  ShieldAlert,
  Tags,
  ThumbsUp,
  Users,
} from 'lucide-react'
import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from '../ui/command'

const NAV_ITEMS = [
  { path: '/admin', label: 'Dashboard', icon: LayoutDashboard },
  { path: '/admin/knowledge-base', label: 'Knowledge Base', icon: Database },
  { path: '/admin/costs', label: 'Chat Costs', icon: BadgeDollarSign },
  { path: '/admin/traces', label: 'Chat Traces', icon: GitBranch },
  { path: '/admin/categories', label: 'Question Categories', icon: Tags },
  { path: '/admin/conversations', label: 'Conversations', icon: MessageSquare },
  { path: '/admin/model-config', label: 'Model Config', icon: Settings },
  { path: '/admin/guardrails', label: 'Guardrails', icon: ShieldAlert },
  { path: '/admin/users', label: 'Users & Analytics', icon: Users },
  { path: '/admin/feedback', label: 'Feedback', icon: ThumbsUp },
]

interface Props {
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function CommandPalette({ open, onOpenChange }: Props) {
  const navigate = useNavigate()

  const handleSelect = useCallback(
    (path: string) => {
      navigate(path)
      onOpenChange(false)
    },
    [navigate, onOpenChange],
  )

  return (
    <CommandDialog open={open} onOpenChange={onOpenChange}>
      <CommandInput placeholder="Go to admin section…" />
      <CommandList>
        <CommandEmpty>No results found.</CommandEmpty>
        <CommandGroup heading="Navigation">
          {NAV_ITEMS.map(({ path, label, icon: Icon }) => (
            <CommandItem key={path} value={label} onSelect={() => handleSelect(path)}>
              <Icon className="mr-2 h-4 w-4 text-muted-foreground" />
              {label}
            </CommandItem>
          ))}
        </CommandGroup>
      </CommandList>
    </CommandDialog>
  )
}
