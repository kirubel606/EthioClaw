'use client'

import { useEffect } from 'react'
import {
  ThemeProvider as NextThemesProvider,
  type ThemeProviderProps,
  useTheme,
} from 'next-themes'

function CustomThemeHandler() {
  const { theme } = useTheme()

  useEffect(() => {
    if (theme === 'custom') {
      const saved = localStorage.getItem('custom-theme-colors')
      if (saved) {
        try {
          const colors = JSON.parse(saved)
          const root = document.documentElement
          Object.entries(colors).forEach(([key, value]) => {
            root.style.setProperty(`--${key}`, value as string)
          })
        } catch (e) {
          console.error('Failed to apply custom colors', e)
        }
      }
    } else {
      // Clear custom colors when not in custom theme
      const root = document.documentElement
      const keys = ['background', 'foreground', 'primary', 'secondary', 'accent', 'border']
      keys.forEach((key) => {
        root.style.removeProperty(`--${key}`)
      })
    }
  }, [theme])

  return null
}

export function ThemeProvider({ children, ...props }: ThemeProviderProps) {
  return (
    <NextThemesProvider {...props}>
      <CustomThemeHandler />
      {children}
    </NextThemesProvider>
  )
}
