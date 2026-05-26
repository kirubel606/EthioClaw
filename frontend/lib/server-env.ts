const defaultThemeValue =
  process.env.NEXT_PUBLIC_DEFAULT_THEME?.trim() ||
  process.env.DEFAULT_THEME?.trim() ||
  'toxic'

export const DEFAULT_THEME =
  defaultThemeValue === 'morty' || defaultThemeValue === 'portal' || defaultThemeValue === 'custom'
    ? defaultThemeValue
    : 'toxic'

export const OPENAI_MODEL = process.env.OPENAI_MODEL?.trim() || 'gpt-4-turbo'

// Backend API URL – used by the chat route
export const BACKEND_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL?.trim() ||
  process.env.BACKEND_URL?.trim() ||
  'http://127.0.0.1:8000'
