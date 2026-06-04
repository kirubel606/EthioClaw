'use client'

import { useState } from 'react'
import { X, Check } from 'lucide-react'
import { Button } from '@/components/ui/button'

interface SettingsProps {
  isOpen: boolean
  onClose: () => void
}

export default function Settings({ isOpen, onClose }: SettingsProps) {
  if (!isOpen) return null

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
      <div className="bg-card w-full max-w-md rounded-lg border border-border p-6 shadow-2xl">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-xl font-bold text-foreground">Settings</h2>
          <Button onClick={onClose} variant="ghost" size="icon"><X size={20}/></Button>
        </div>
        
        <div className="space-y-4">
          <p className="text-sm text-muted-foreground">General application settings will appear here.</p>
          <div className="p-4 border border-border rounded bg-background">
            <p className="text-xs text-muted-foreground">Theme: Default (Dark)</p>
          </div>
        </div>
        
        <div className="mt-6 flex justify-end">
          <Button onClick={onClose}>Close</Button>
        </div>
      </div>
    </div>
  )
}
