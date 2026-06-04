'use client'

import { useState } from 'react'
import { MessageSquare, Library, Settings as SettingsIcon, Trash2, Menu, X } from 'lucide-react'

interface SidebarProps {
  onTabChange: (tab: 'history' | 'memory') => void
  onSettingsClick: () => void
  onClearChat: () => void
  activeTab: 'history' | 'memory'
}

export default function Sidebar({ onTabChange, onSettingsClick, onClearChat, activeTab }: SidebarProps) {
  const [isOpen, setIsOpen] = useState(true)

  if (!isOpen) {
    return (
      <div className="w-16 bg-card border-r border-border flex flex-col items-center py-4 gap-4">
        <button onClick={() => setIsOpen(true)} className="p-2 text-muted-foreground cursor-pointer hover:text-foreground"><Menu size={20}/></button>
        <button onClick={() => { setIsOpen(true); onTabChange('history') }} className="p-2 text-muted-foreground cursor-pointer hover:text-foreground"><MessageSquare size={20}/></button>
        <button onClick={() => { setIsOpen(true); onTabChange('memory') }} className="p-2 text-muted-foreground cursor-pointer hover:text-foreground"><Library size={20}/></button>
      </div>
    )
  }

  return (
    <div className="w-64 bg-card border-r border-border flex flex-col h-full">
      <div className="p-4 border-b border-border flex items-center justify-between">
        <h2 className="font-bold text-lg">Menu</h2>
        <button onClick={() => setIsOpen(false)} className="p-1 cursor-pointer hover:text-destructive"><X size={20}/></button>
      </div>
      <div className="flex flex-col p-2 gap-1">
        <button onClick={() => onTabChange('history')} className={`flex items-center gap-2 p-2 rounded cursor-pointer ${activeTab === 'history' ? 'bg-primary/10 text-primary' : 'text-muted-foreground hover:text-foreground'}`}>
          <MessageSquare size={18}/> History
        </button>
        <button onClick={() => onTabChange('memory')} className={`flex items-center gap-2 p-2 rounded cursor-pointer ${activeTab === 'memory' ? 'bg-primary/10 text-primary' : 'text-muted-foreground hover:text-foreground'}`}>
          <Library size={18}/> Memory
        </button>
      </div>
      <div className="mt-auto p-2 border-t border-border">
        <button onClick={onSettingsClick} className="flex items-center gap-2 p-2 w-full text-muted-foreground hover:text-foreground cursor-pointer">
          <SettingsIcon size={18}/> Settings
        </button>
        <button onClick={onClearChat} className="flex items-center gap-2 p-2 w-full text-muted-foreground hover:text-destructive cursor-pointer">
          <Trash2 size={18}/> Clear Chat
        </button>
      </div>
    </div>
  )
}
