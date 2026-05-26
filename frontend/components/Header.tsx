'use client'

import Image from 'next/image'
import { APP_NAME } from '@/lib/env'
import { MessageSquare, Library, Settings as SettingsIcon, Trash2 } from 'lucide-react'

interface HeaderProps {
  onMemoryToggle?: () => void
  memoryOpen?: boolean
  onHistoryToggle?: () => void
  historyOpen?: boolean
  onSettingsToggle?: () => void
  onClearChat?: () => void
}

export default function Header({
  onMemoryToggle,
  memoryOpen,
  onHistoryToggle,
  historyOpen,
  onSettingsToggle,
  onClearChat,
}: HeaderProps) {
  return (
    <header className="bg-card border-b-2 border-border py-4 px-6 shadow-lg z-20">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <div className="w-10 h-10 overflow-hidden rounded-full border-2 border-primary flex items-center justify-center bg-background shadow-[0_0_15px_rgba(var(--primary-rgb),0.3)]">
            <span className="text-primary font-bold text-sm">AI</span>
          </div>
          <div>
            <h1 className="neon-text text-2xl tracking-tighter">{APP_NAME}</h1>
            <p className="text-muted-foreground text-[10px] uppercase tracking-[0.2em] font-bold">Cognitive Intelligence</p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={onHistoryToggle}
            className={`hidden lg:flex items-center gap-2 px-4 py-2 rounded-lg border-2 transition-all duration-200 font-bold text-xs uppercase tracking-wider ${
              historyOpen
                ? 'border-destructive text-destructive bg-destructive/10 hover:bg-destructive/20'
                : 'border-primary text-primary bg-primary/10 hover:bg-primary/20'
            }`}
          >
            <MessageSquare className="size-4" />
            {historyOpen ? 'Close History' : 'History'}
          </button>

          <button
            onClick={onMemoryToggle}
            className={`hidden lg:flex items-center gap-2 px-4 py-2 rounded-lg border-2 transition-all duration-200 font-bold text-xs uppercase tracking-wider ${
              memoryOpen
                ? 'border-destructive text-destructive bg-destructive/10 hover:bg-destructive/20'
                : 'border-accent text-accent bg-accent/10 hover:bg-accent/20'
            }`}
          >
            <Library className="size-4" />
            {memoryOpen ? 'Close Memory' : 'Memory'}
          </button>

          <button
            onClick={onSettingsToggle}
            className="flex items-center gap-2 px-4 py-2 rounded-lg border-2 border-muted text-muted-foreground bg-muted/10 hover:bg-muted/20 hover:text-foreground transition-all duration-200 font-bold text-xs uppercase tracking-wider"
            title="Settings"
          >
            <SettingsIcon className="size-4" />
            Settings
          </button>

          <button
            onClick={onClearChat}
            className="hidden lg:flex items-center gap-2 px-4 py-2 rounded-lg border-2 border-destructive/50 text-destructive/70 bg-destructive/5 hover:bg-destructive/10 hover:border-destructive transition-all duration-200 font-bold text-xs uppercase tracking-wider"
            title="Clear current view"
          >
            <Trash2 className="size-4" />
            Clear
          </button>

          <div className="hidden xl:block text-right ml-4 border-l border-border pl-4">
            <p className="text-primary text-[10px] font-bold uppercase">System Online</p>
            <p className="text-green-400 text-[10px] animate-pulse font-mono">Neural Link Ready</p>
          </div>
        </div>
      </div>
    </header>
  )
}
