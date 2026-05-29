'use client'

import Image from 'next/image'
import { APP_NAME } from '@/lib/env'
import { MessageSquare, Library, Settings as SettingsIcon, Trash2, BarChart3, BrainCircuit } from 'lucide-react'

type AppMode = 'agent' | 'trading'

interface HeaderProps {
  onMemoryToggle?: () => void
  memoryOpen?: boolean
  onHistoryToggle?: () => void
  historyOpen?: boolean
  onSettingsToggle?: () => void
  onClearChat?: () => void
  mode?: AppMode
  onModeToggle?: () => void
  onDashboardToggle?: () => void
  dashboardOpen?: boolean
}

export default function Header({
  onMemoryToggle,
  memoryOpen,
  onHistoryToggle,
  historyOpen,
  onSettingsToggle,
  onClearChat,
  mode = 'agent',
  onModeToggle,
  onDashboardToggle,
  dashboardOpen,
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
          {/* Mode Switcher Tabs */}
          <div className="flex bg-background/50 p-1 rounded-xl border-2 border-border/50 gap-1 mr-4">
            <button
              onClick={() => mode !== 'agent' && onModeToggle?.()}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg transition-all duration-300 font-black text-[10px] uppercase tracking-widest ${
                mode === 'agent'
                  ? 'bg-cyan-500/20 text-cyan-400 border border-cyan-500/50 shadow-[0_0_10px_rgba(34,211,238,0.2)]'
                  : 'text-muted-foreground hover:text-foreground hover:bg-muted/30 border border-transparent'
              }`}
            >
              <BrainCircuit className={`size-3.5 ${mode === 'agent' ? 'animate-pulse' : ''}`} />
              Agent Mode
            </button>
            <button
              onClick={() => mode !== 'trading' && onModeToggle?.()}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg transition-all duration-300 font-black text-[10px] uppercase tracking-widest ${
                mode === 'trading'
                  ? 'bg-amber-500/20 text-amber-400 border border-amber-500/50 shadow-[0_0_10px_rgba(245,158,11,0.2)]'
                  : 'text-muted-foreground hover:text-foreground hover:bg-muted/30 border border-transparent'
              }`}
            >
              <BarChart3 className={`size-3.5 ${mode === 'trading' ? 'animate-pulse' : ''}`} />
              Trading Desk
            </button>
          </div>

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
            onClick={onDashboardToggle}
            className={`hidden lg:flex items-center gap-2 px-4 py-2 rounded-lg border-2 transition-all duration-200 font-bold text-xs uppercase tracking-wider ${
              dashboardOpen
                ? 'border-emerald-400 text-emerald-300 bg-emerald-400/10 hover:bg-emerald-400/20'
                : 'border-muted text-muted-foreground bg-muted/10 hover:bg-muted/20'
            }`}
            disabled={mode !== 'trading'}
            title={mode !== 'trading' ? 'Dashboard available in Trading Mode' : 'Toggle Dashboard'}
          >
            <BarChart3 className="size-4" />
            {dashboardOpen ? 'Close Dashboard' : 'Dashboard'}
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
