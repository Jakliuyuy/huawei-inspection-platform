/**
 * 色板 —— 全站唯一色值来源。
 *
 * 基调是 NOC 控制台 / 网管系统，不是 SaaS 落地页：低饱和钢蓝主色、
 * 冷灰中性色、零渐变。暗色底用 #0F1318 而非纯黑，运维要盯一整天。
 *
 * 语义色明暗两套，暗色统一提亮以补偿暗底。状态一律三重编码
 * （图标 + 文字 + 数字），颜色只作增强 —— 约 8% 男性有红绿色觉障碍。
 */

export const blue = {
  1: '#EDF3FA',
  2: '#D3E2F3',
  3: '#AECBE8',
  4: '#84AEDA',
  5: '#5A90CA',
  6: '#2F6FB5', // 亮色主色，白字对比 5.17:1（AA）
  7: '#245A99',
  8: '#1B477A',
  9: '#13355C',
  10: '#0C2440', // 登录页左栏底
} as const

export const blueDark = {
  hover: '#6BA5E7',
  base: '#4E90DE',
  active: '#3A7AC4',
} as const

export const light = {
  bgLayout: '#F1F3F7',
  bgContainer: '#FFFFFF',
  bgElevated: '#FFFFFF',
  fillTertiary: '#F5F7FA',
  border: '#D7DDE6',
  borderSecondary: '#E7EBF1',
  text: '#1B2430',
  textSecondary: '#57647A',
  textTertiary: '#818E9F',
  textQuaternary: '#AEB7C4',
  success: '#1F8A4C',
  successBg: '#E8F5ED',
  warning: '#B4740E',
  warningBg: '#FBF2E2',
  error: '#C6392F',
  errorBg: '#FBECEA',
  neutral: '#818E9F',
  neutralBg: '#F1F3F7',
} as const

export const dark = {
  bgLayout: '#0F1318',
  bgContainer: '#171C23',
  bgElevated: '#1E242C',
  fillTertiary: '#1C222A',
  border: '#2C343E',
  borderSecondary: '#232A33',
  text: '#E3E8EF',
  textSecondary: '#98A3B3',
  textTertiary: '#6C7787',
  textQuaternary: '#4E5865',
  success: '#3FB37A',
  successBg: '#14261D',
  warning: '#E0A33A',
  warningBg: '#2A2113',
  error: '#EA6A5E',
  errorBg: '#2B1715',
  neutral: '#6C7787',
  neutralBg: '#1C222A',
} as const

export const fontFamily =
  '-apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", ' +
  '"HarmonyOS Sans SC", "Source Han Sans SC", "Noto Sans SC", ' +
  '"Microsoft YaHei", "Hiragino Sans GB", sans-serif'

/** 任务 ID、路径、主机名、文件名、时间戳、计数一律走等宽栈 —— 对可扫读性的贡献大于任何配色调整 */
export const fontFamilyCode =
  '"Cascadia Mono", "JetBrains Mono", "SF Mono", Consolas, ' +
  '"Noto Sans Mono", "Liberation Mono", monospace'
