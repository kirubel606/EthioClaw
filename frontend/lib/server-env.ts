const defaultThemeValue =
  process.env.NEXT_PUBLIC_DEFAULT_THEME?.trim() ||
  process.env.DEFAULT_THEME?.trim() ||
  'rick'

export const DEFAULT_THEME =
  defaultThemeValue === 'morty' || defaultThemeValue === 'portal'
    ? defaultThemeValue
    : 'rick'

export const OPENAI_MODEL = process.env.OPENAI_MODEL?.trim() || 'gpt-4-turbo'
