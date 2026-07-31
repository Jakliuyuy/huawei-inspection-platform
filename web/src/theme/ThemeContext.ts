import { createContext, useContext } from 'react'

import type { ResolvedMode, ThemeMode } from './tokens'

export type ThemeContextValue = {
  mode: ThemeMode
  resolved: ResolvedMode
  setMode: (mode: ThemeMode) => void
}

export const ThemeContext = createContext<ThemeContextValue | null>(null)

export function useTheme(): ThemeContextValue {
  const context = useContext(ThemeContext)
  if (!context) throw new Error('useTheme 必须在 ThemeProvider 内使用')
  return context
}
