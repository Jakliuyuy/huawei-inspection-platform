import { App as AntApp, ConfigProvider, theme } from 'antd'
import zhCN from 'antd/locale/zh_CN'
import type { ReactNode } from 'react'
import { useMemo } from 'react'

import { ThemeBridge } from './ThemeBridge'
import { buildComponents } from './components'
import { darkToken, lightToken } from './tokens'
import { ThemeContext } from './ThemeContext'
import { useThemeMode } from './useThemeMode'

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
