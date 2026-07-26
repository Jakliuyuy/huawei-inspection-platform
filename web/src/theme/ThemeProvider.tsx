import { App as AntApp, ConfigProvider, theme } from 'antd'
import zhCN from 'antd/locale/zh_CN'
import type { ReactNode } from 'react'
import { createContext, useContext, useMemo } from 'react'

import { ThemeBridge } from './ThemeBridge'
import { buildComponents } from './components'
import { darkToken, lightToken, type ResolvedMode, type ThemeMode } from './tokens'
import { useThemeMode } from './useThemeMode'

type ThemeContextValue = {
  mode: ThemeMode
  resolved: ResolvedMode
  setMode: (mode: ThemeMode) => void
}

const ThemeContext = createContext<ThemeContextValue | null>(null)

export function useTheme(): ThemeContextValue {
  const ctx = useContext(ThemeContext)
  if (!ctx) throw new Error('useTheme 必须在 ThemeProvider 内使用')
  return ctx
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const { mode, resolved, setMode } = useThemeMode()
  const value = useMemo(() => ({ mode, resolved, setMode }), [mode, resolved, setMode])

  return (
    <ThemeContext.Provider value={value}>
      <ConfigProvider
        locale={zhCN}
        theme={{
          algorithm: resolved === 'dark' ? theme.darkAlgorithm : theme.defaultAlgorithm,
          token: resolved === 'dark' ? darkToken : lightToken,
          components: buildComponents(resolved),
          cssVar: {},
          hashed: true,
        }}
        card={{ variant: 'outlined' }}
      >
        <ThemeBridge />
        <AntApp>{children}</AntApp>
      </ConfigProvider>
    </ThemeContext.Provider>
  )
}
