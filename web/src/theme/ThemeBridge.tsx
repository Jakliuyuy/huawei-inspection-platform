import { theme } from 'antd'
import { useLayoutEffect } from 'react'

/**
 * 把 antd token 写成 CSS 变量，供 CSS Modules 使用。
 *
 * 有了这座桥，自定义样式里只需要写 var(--app-*)，暗色切换自动跟随，
 * 不必写两套选择器，也不必再穿透 antd 内部类。
 * 规约：*.module.css 里禁止出现 hex 色值。
 */
const VAR_MAP: [string, string][] = [
  ['--app-bg-layout', 'colorBgLayout'],
  ['--app-bg-container', 'colorBgContainer'],
  ['--app-bg-elevated', 'colorBgElevated'],
  ['--app-fill-tertiary', 'colorFillTertiary'],
  ['--app-border', 'colorBorder'],
  ['--app-border-2', 'colorBorderSecondary'],
  ['--app-text', 'colorText'],
  ['--app-text-2', 'colorTextSecondary'],
  ['--app-text-3', 'colorTextTertiary'],
  ['--app-text-4', 'colorTextQuaternary'],
  ['--app-primary', 'colorPrimary'],
  ['--app-primary-bg', 'colorPrimaryBg'],
  ['--app-primary-border', 'colorPrimaryBorder'],
  ['--app-success', 'colorSuccess'],
  ['--app-success-bg', 'colorSuccessBg'],
  ['--app-warning', 'colorWarning'],
  ['--app-warning-bg', 'colorWarningBg'],
  ['--app-error', 'colorError'],
  ['--app-error-bg', 'colorErrorBg'],
  ['--app-radius', 'borderRadius'],
  ['--app-radius-lg', 'borderRadiusLG'],
  ['--app-shadow-popup', 'boxShadowSecondary'],
  ['--app-font', 'fontFamily'],
  ['--app-font-code', 'fontFamilyCode'],
]

export function ThemeBridge() {
  const { token } = theme.useToken()

  useLayoutEffect(() => {
    const style = document.documentElement.style
    for (const [cssVar, key] of VAR_MAP) {
      const value = (token as unknown as Record<string, unknown>)[key]
      if (value === undefined) continue
      style.setProperty(cssVar, typeof value === 'number' ? `${value}px` : String(value))
    }
  }, [token])

  return null
}
