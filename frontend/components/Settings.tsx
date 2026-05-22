'use client'

import { useTheme, type Theme } from '@/lib/theme-context'
import { useState, useEffect } from 'react'

const THEMES: { id: Theme; name: string; description: string }[] = [
  {
    id: 'rick',
    name: 'Rick Mode',
    description: 'Dark and edgy with toxic green and cyan. The default.',
  },
  {
    id: 'morty',
    name: 'Morty Mode',
    description: 'Softer and easier on the eyes with muted blues.',
  },
  {
    id: 'portal',
    name: 'Portal Mode',
    description: 'High contrast and vibrant with magenta and cyan.',
  },
]

interface SettingsProps {
  isOpen: boolean
  onClose: () => void
}

export default function Settings({ isOpen, onClose }: SettingsProps) {
  const [mounted, setMounted] = useState(false)
  const { theme, setTheme } = useTheme()

  useEffect(() => {
    setMounted(true)
  }, [])

  if (!isOpen || !mounted) return null

  return (
    <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 animate-in fade-in duration-200">
      <div className="bg-card border-2 border-cyan-400 rounded-lg p-6 max-w-md w-full mx-4 shadow-2xl animate-in slide-in-from-bottom-4 duration-300">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-2xl font-bold text-green-400 neon-text">Settings</h2>
          <button
            onClick={onClose}
            className="text-cyan-400 hover:text-red-400 transition-colors p-1 hover:bg-cyan-400/10 rounded"
          >
            ✕
          </button>
        </div>

        <div className="space-y-4">
          <div>
            <h3 className="text-cyan-400 font-bold mb-3 text-sm uppercase tracking-wider">
              Theme Selection
            </h3>
            <div className="space-y-2">
              {THEMES.map((t) => (
                <button
                  key={t.id}
                  onClick={() => setTheme(t.id)}
                  className={`w-full text-left p-3 rounded-lg border-2 transition-all duration-200 ${
                    theme === t.id
                      ? 'border-green-400 bg-green-400/10 text-green-400'
                      : 'border-cyan-400/30 bg-gray-900/50 text-cyan-300 hover:border-cyan-400 hover:bg-cyan-400/5'
                  }`}
                >
                  <div className="font-bold">{t.name}</div>
                  <div className="text-xs opacity-75 mt-1">{t.description}</div>
                </button>
              ))}
            </div>
          </div>

          <div className="border-t border-cyan-400/20 pt-4">
            <p className="text-xs text-gray-500">
              Theme preferences are saved and will persist across sessions.
            </p>
          </div>
        </div>

        <button
          onClick={onClose}
          className="w-full mt-6 bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 text-white font-bold py-2 px-4 rounded-lg border-2 border-cyan-300 transition-all duration-200 hover:shadow-lg hover:shadow-cyan-500/50"
        >
          Close Settings
        </button>
      </div>
    </div>
  )
}
