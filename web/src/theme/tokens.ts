import { blue, blueDark, dark, fontFamily, fontFamilyCode, light } from './palette'

const shared = {
  fontFamily,
  fontFamilyCode,
  fontSize: 14,
  fontSizeSM: 12,
  fontSizeLG: 16,
  fontSizeHeading1: 26,
  fontSizeHeading2: 22,
  fontSizeHeading3: 18,
  fontSizeHeading4: 16,
  fontSizeHeading5: 14,
  borderRadiusXS: 2,
  borderRadiusSM: 4,
  borderRadius: 6,
  borderRadiusLG: 8,
  controlHeight: 32,
  controlHeightSM: 26,
  controlHeightLG: 38,
  sizeUnit: 4,
  sizeStep: 4,
  wireframe: false,
  motionDurationMid: '0.16s',
}

// 卡片零阴影，靠 1px 边框划界；只有浮层有阴影
const shadowLight = '0 6px 16px -8px rgba(16,24,40,.14), 0 9px 28px 0 rgba(16,24,40,.08)'
const shadowDark = '0 8px 24px -6px rgba(0,0,0,.55), 0 2px 8px rgba(0,0,0,.40)'

export const lightToken = {
  ...shared,
  colorPrimary: blue[6],
  colorInfo: blue[6],
  colorSuccess: light.success,
  colorWarning: light.warning,
  colorError: light.error,
  colorBgLayout: light.bgLayout,
  colorBgContainer: light.bgContainer,
  colorBgElevated: light.bgElevated,
  colorFillTertiary: light.fillTertiary,
  colorBorder: light.border,
  colorBorderSecondary: light.borderSecondary,
  colorText: light.text,
  colorTextSecondary: light.textSecondary,
  colorTextTertiary: light.textTertiary,
  colorTextQuaternary: light.textQuaternary,
  boxShadow: 'none',
  boxShadowTertiary: 'none',
  boxShadowSecondary: shadowLight,
}

export const darkToken = {
  ...shared,
  colorPrimary: blueDark.base,
  colorInfo: blueDark.base,
  colorSuccess: dark.success,
  colorWarning: dark.warning,
  colorError: dark.error,
  colorBgBase: dark.bgLayout, // 让 darkAlgorithm 从这个基色派生整套
  colorBgLayout: dark.bgLayout,
  colorBgContainer: dark.bgContainer,
  colorBgElevated: dark.bgElevated,
  colorFillTertiary: dark.fillTertiary,
  colorBorder: dark.border,
  colorBorderSecondary: dark.borderSecondary,
  colorText: dark.text,
  colorTextSecondary: dark.textSecondary,
  colorTextTertiary: dark.textTertiary,
  colorTextQuaternary: dark.textQuaternary,
  boxShadow: 'none',
  boxShadowTertiary: 'none',
  boxShadowSecondary: shadowDark,
}

export type ThemeMode = 'light' | 'dark' | 'system'
export type ResolvedMode = 'light' | 'dark'
