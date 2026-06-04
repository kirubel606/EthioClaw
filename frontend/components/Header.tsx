'use client'

import { APP_NAME } from '@/lib/env'

export default function Header() {
  return (
    <header className="bg-card border-b-2 border-border py-4 px-6 shadow-lg z-20">
      <div className="flex items-center gap-4">
        <div className="w-10 h-10 overflow-hidden rounded-full border-2 border-primary flex items-center justify-center bg-background shadow-[0_0_15px_rgba(var(--primary-rgb),0.3)]">
          <span className="text-primary font-bold text-sm">AI</span>
        </div>
        <div>
          <h1 className="neon-text text-2xl tracking-tighter">{APP_NAME}</h1>
          <p className="text-muted-foreground text-[10px] uppercase tracking-[0.2em] font-bold">Cognitive Intelligence</p>
        </div>
      </div>
    </header>
  )
}
