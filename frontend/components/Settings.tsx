'use client'

import { useState, useEffect } from 'react'
import { useTheme } from 'next-themes'

type ThemeId = 'toxic' | 'morty' | 'portal' | 'custom'

const THEMES: { id: ThemeId; name: string; description: string }[] = [
  {
    id: 'toxic',
    name: 'Toxic Mode',
    description: 'Dark and edgy with toxic green and cyan. The default.',
  },
  {
    id: 'morty',
    name: 'Muted Mode',
    description: 'Softer and easier on the eyes with muted blues.',
  },
  {
    id: 'portal',
    name: 'Vibrant Mode',
    description: 'High contrast and vibrant with magenta and cyan.',
  },
  {
    id: 'custom',
    name: 'Custom Mode',
    description: 'Design your own theme with custom colors.',
  },
]

interface SettingsProps {
  isOpen: boolean
  onClose: () => void
}

const DEFAULT_CUSTOM_COLORS = {
  background: '#0a0e27',
  foreground: '#00ff41',
  primary: '#00d4ff',
  'primary-foreground': '#0a0e27',
  secondary: '#ff006e',
  'secondary-foreground': '#ffffff',
  accent: '#ff006e',
  'accent-foreground': '#ffffff',
  border: '#2d3456',
  card: '#1a1f3a',
  'card-foreground': '#00ff41',
  muted: '#404a6a',
  'muted-foreground': '#a0a9c9',
}

export default function Settings({ isOpen, onClose }: SettingsProps) {
  const [mounted, setMounted] = useState(false)
  const { theme, setTheme } = useTheme()
  const [customColors, setCustomColors] = useState(DEFAULT_CUSTOM_COLORS)

  useEffect(() => {
    setMounted(true)
    const saved = localStorage.getItem('custom-theme-colors')
    if (saved) {
      try {
        const parsed = JSON.parse(saved)
        setCustomColors({ ...DEFAULT_CUSTOM_COLORS, ...parsed })
      } catch (e) {
        console.error('Failed to parse custom colors', e)
      }
    }
  }, [])

  const updateCustomColor = (key: keyof typeof DEFAULT_CUSTOM_COLORS, value: string) => {
    const newColors = { ...customColors, [key]: value }
    setCustomColors(newColors)
    localStorage.setItem('custom-theme-colors', JSON.stringify(newColors))
    if (theme === 'custom') {
      applyCustomColors(newColors)
    }
  }

  const applyCustomColors = (colors: typeof DEFAULT_CUSTOM_COLORS) => {
    const root = document.documentElement
    Object.entries(colors).forEach(([key, value]) => {
      root.style.setProperty(`--${key}`, value)
    })
  }

  const handleThemeChange = (newTheme: string) => {
    setTheme(newTheme)
    if (newTheme === 'custom') {
      applyCustomColors(customColors)
    } else {
      // Clear inline styles when switching back to preset themes
      const root = document.documentElement
      Object.keys(DEFAULT_CUSTOM_COLORS).forEach((key) => {
        root.style.removeProperty(`--${key}`)
      })
    }
  }

  if (!isOpen || !mounted) return null

  const activeTheme = (theme as ThemeId | undefined) ?? 'toxic'

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 px-4 animate-in fade-in duration-200">
      <div className="max-w-md w-full max-h-[90vh] overflow-y-auto scrollbar-hidden rounded-lg border-2 border-cyan-400 bg-card p-6 shadow-2xl animate-in slide-in-from-bottom-4 duration-300">
        <div className="flex items-center justify-between mb-6 sticky top-0 bg-card z-10 pb-2">
          <h2 className="text-2xl font-bold text-green-400 neon-text">Settings</h2>
          <button
            onClick={onClose}
            className="text-cyan-400 hover:text-red-400 transition-colors p-1 hover:bg-cyan-400/10 rounded"
          >
            ✕
          </button>
        </div>

        <div className="space-y-6">
          <div>
            <h3 className="text-cyan-400 font-bold mb-3 text-sm uppercase tracking-wider">
              Theme Selection
            </h3>
            <div className="grid grid-cols-1 gap-2">
              {THEMES.map((t) => (
                <button
                  key={t.id}
                  onClick={() => handleThemeChange(t.id)}
                  className={`w-full text-left p-3 rounded-lg border-2 transition-all duration-200 ${
                    activeTheme === t.id
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

          {activeTheme === 'custom' && (
            <div className="border-t border-cyan-400/20 pt-4 animate-in fade-in slide-in-from-top-2 duration-300">
              <h3 className="text-cyan-400 font-bold mb-4 text-sm uppercase tracking-wider">
                Custom Colors
              </h3>
              <div className="grid grid-cols-2 gap-4">
                {Object.entries(customColors).map(([key, value]) => (
                  <div key={key} className="space-y-1">
                    <label className="text-xs text-gray-400 capitalize">{key}</label>
                    <div className="flex items-center gap-2">
                      <input
                        type="color"
                        value={value}
                        onChange={(e) => updateCustomColor(key as any, e.target.value)}
                        className="w-8 h-8 rounded border border-cyan-400/30 bg-transparent cursor-pointer"
                      />
                      <input
                        type="text"
                        value={value}
                        onChange={(e) => updateCustomColor(key as any, e.target.value)}
                        className="flex-1 bg-gray-900 border border-cyan-400/30 rounded px-2 py-1 text-xs text-green-400 focus:outline-none focus:border-cyan-400"
                      />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

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
