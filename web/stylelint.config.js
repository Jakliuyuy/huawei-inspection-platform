/**
 * 把「不再穿透 antd 内部类」从口头约定变成编译期约束。
 *
 * 之前 511 行的全局 index.css 里有 5 处 .ant-* 穿透和 3 处 !important，
 * 它们在 antd 升级或 DOM 结构调整时最先碎掉。需要改 antd 外观时，
 * 依次尝试：theme/components.ts 的 token → 组件的 classNames/styles →
 * ConfigProvider 的组件级默认 props。三者都不行说明该用自定义 DOM。
 */
export default {
  extends: ['stylelint-config-standard'],
  rules: {
    'declaration-no-important': true,
    'selector-disallowed-list': [
      ['/\\.ant-/', '/\\.rc-/'],
      {
        message: '禁止穿透 antd 内部类，请改用 theme/components.ts 的 token 或组件的 styles/classNames',
      },
    ],
    'selector-max-specificity': '0,3,0',

    // 以下是 stylelint-config-standard 的风格默认值，与本项目约定无关，关掉以免噪音淹没上面三条
    'custom-property-pattern': null,
    'selector-class-pattern': null,
    'custom-property-empty-line-before': null,
    'color-hex-length': null,
    'media-feature-range-notation': null,
    'property-no-deprecated': null,
    // CSS Modules 的 :global()
    'selector-pseudo-class-no-unknown': [true, { ignorePseudoClasses: ['global'] }],
  },
}
