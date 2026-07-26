import { blue, blueDark, dark, light } from './palette'
import type { ResolvedMode } from './tokens'

/**
 * antd 组件级 token。
 *
 * 每一条都替代了一处曾经的全局 CSS 穿透（.app-sider{...!important}、
 * .compact-card .ant-card-head、.compact-card .ant-table-wrapper 等）。
 * 需要改 antd 外观时先来这里找 token，不要写 .ant-* 选择器 ——
 * stylelint 会直接拦下。
 */
export function buildComponents(mode: ResolvedMode) {
  const isDark = mode === 'dark'
  const c = isDark ? dark : light
  const primary = isDark ? blueDark.base : blue[6]

  return {
    Layout: {
      siderBg: isDark ? '#131820' : c.bgContainer,
      headerBg: isDark ? '#131820' : c.bgContainer,
      bodyBg: c.bgLayout,
      headerHeight: 52,
      headerPadding: '0 20px',
      triggerBg: 'transparent',
    },
    Card: {
      headerHeight: 44,
      headerHeightSM: 38,
      headerFontSize: 14,
      headerFontSizeSM: 13,
      headerBg: 'transparent',
      bodyPadding: 16,
      bodyPaddingSM: 12,
      paddingLG: 16,
      boxShadowTertiary: 'none',
    },
    Table: {
      headerBg: c.fillTertiary,
      headerColor: c.textSecondary,
      headerSplitColor: 'transparent',
      cellPaddingBlock: 10,
      cellPaddingInline: 12,
      cellPaddingBlockSM: 7,
      cellPaddingInlineSM: 10,
      rowHoverBg: isDark ? '#1C222A' : '#F7F9FC',
      rowSelectedBg: isDark ? '#182430' : blue[1],
      rowSelectedHoverBg: isDark ? '#1D2B39' : '#E3EDF8',
      borderColor: c.borderSecondary,
      footerBg: 'transparent',
    },
    Menu: {
      itemHeight: 38,
      itemMarginInline: 8,
      itemMarginBlock: 2,
      itemBorderRadius: 6,
      itemBg: 'transparent',
      itemSelectedBg: isDark ? '#1B2836' : blue[1],
      itemSelectedColor: isDark ? '#7DB0EA' : blue[7],
      itemHoverBg: isDark ? '#1C222A' : '#F2F5F9',
      activeBarWidth: 0,
      activeBarBorderWidth: 0,
      iconSize: 15,
      collapsedIconSize: 16,
      subMenuItemBg: 'transparent',
    },
    Statistic: { contentFontSize: 24, titleFontSize: 13 },
    Tag: { defaultBg: c.neutralBg, borderRadiusSM: 4, lineHeightSM: 1.6 },
    Segmented: {
      itemSelectedBg: isDark ? '#2A323C' : '#FFFFFF',
      trackBg: isDark ? c.bgContainer : '#EEF1F6',
      borderRadius: 6,
      borderRadiusSM: 4,
    },
    Progress: {
      defaultColor: primary,
      remainingColor: isDark ? c.borderSecondary : '#EBEFF4',
      circleTextColor: 'inherit',
    },
    Descriptions: {
      labelBg: 'transparent',
      itemPaddingBottom: 10,
      colonMarginRight: 8,
      titleMarginBottom: 12,
    },
    Modal: {
      headerBg: 'transparent',
      contentBg: c.bgElevated,
      titleFontSize: 16,
      borderRadiusLG: 8,
    },
    Tabs: {
      horizontalItemPadding: '10px 0',
      horizontalItemGutter: 24,
      titleFontSize: 14,
      cardBg: 'transparent',
      inkBarColor: primary,
    },
    Alert: { withDescriptionPadding: '12px 16px', defaultPadding: '8px 12px' },
    List: { itemPadding: '8px 12px', itemPaddingSM: '6px 10px' },
    Steps: { titleLineHeight: 22, iconSize: 26, iconFontSize: 13, descriptionMaxWidth: 220 },
    Breadcrumb: {
      itemColor: c.textSecondary,
      lastItemColor: c.text,
      separatorMargin: 6,
    },
    Button: {
      paddingInline: 14,
      defaultShadow: 'none',
      primaryShadow: 'none',
      dangerShadow: 'none',
      fontWeight: 400,
    },
    Input: {
      paddingBlock: 4,
      activeShadow: isDark ? '0 0 0 2px rgba(78,144,222,.20)' : '0 0 0 2px rgba(47,111,181,.14)',
    },
    Select: { optionSelectedBg: isDark ? '#1B2836' : blue[1] },
    DatePicker: { cellActiveWithRangeBg: isDark ? '#1B2836' : blue[1] },
  }
}
