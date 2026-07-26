import { useCallback, useEffect, useState } from 'react'
import type { ResolvedMode, ThemeMode } from './tokens'
import { dark, light } from './palette'

export const THEME_STORAGE_KEY = 'inspection.theme'

function readStored(): ThemeMode {
  try {
    const raw = localStorage.getItem(THEME_STORAGE_KEY)
    if (raw === 'light' || raw === 'dark' || raw === 'system') return raw
  } catch {
    /* 隐私模式下 localStorage 可能不可用 */
  }
  return 'system'
}

function prefersDark(): boolean {
  return typeof matchMedia === 'function' && matchMedia('(prefers-color-scheme: dark)').matches
}

export function useThemeMode() {
  const [mode, setModeState] = useState<ThemeMode>(readStored)
  const [systemDark, setSystemDark] = useState(prefersDark)

  useEffect(() => {
    if (mode !== 'system' || typeof matchMedia !== 'function') return
    const query = matchMedia('(prefers-color-scheme: dark)')
    const onChange = (e: MediaQueryListEvent) => setSystemDark(e.matches)
    query.addEventListener('change', onChange)
    return () => query.removeEventListener('change', onChange)
  }, [mode])

  const resolved: ResolvedMode = mode === 'system' ? (systemDark ? 'dark' : 'light') : mode

  useEffect(() => {
    const root = document.documentElement
    root.dataset.theme = resolved
    // 让原生滚动条与表单控件跟随
    root.style.colorScheme = resolved
    root.style.backgroundColor = resolved === 'dark' ? dark.bgLayout : light.bgLayout
  }, [resolved])

  const setMode = useCallback((next: ThemeMode) => {
    setModeState(next)
    try {
      localStorage.setItem(THEME_STORAGE_KEY, next)
    } catch {
      /* 忽略写入失败 */
    }
  }, [])

  return { mode, resolved, setMode }
}
