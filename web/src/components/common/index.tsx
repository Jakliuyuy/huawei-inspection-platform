import {
  CheckCircleFilled,
  ClockCircleOutlined,
  CloseCircleFilled,
  DesktopOutlined,
  ExclamationCircleFilled,
  InboxOutlined,
  LoadingOutlined,
  MinusCircleOutlined,
  MoonOutlined,
  SunOutlined,
} from '@ant-design/icons'
import { Breadcrumb, Card, Progress, Segmented, Tag, Tooltip, Typography } from 'antd'
import type { ReactNode } from 'react'
import dayjs from 'dayjs'
import relativeTime from 'dayjs/plugin/relativeTime'

import { useTheme } from '../../theme/ThemeContext'
import type { ThemeMode } from '../../theme/tokens'
import { formatTime } from '../../lib/format'
import styles from './common.module.css'

dayjs.extend(relativeTime)

// ---------------------------------------------------------------- 版式

export function PageHeader({
  title,
  description,
  breadcrumb,
  extra,
  children,
}: {
  title: string
  description?: string
  breadcrumb?: { title: ReactNode; href?: string }[]
  extra?: ReactNode
  children?: ReactNode
}) {
  return (
    <div className={styles.pageHeader}>
      {breadcrumb && breadcrumb.length > 0 && <Breadcrumb items={breadcrumb} />}
      <div className={styles.pageHeaderTop}>
        <div>
          <h1 className={styles.pageTitle}>{title}</h1>
          {description && <p className={styles.pageDescription}>{description}</p>}
        </div>
        {extra && <div className={styles.pageExtra}>{extra}</div>}
      </div>
      {children}
    </div>
  )
}

/** 任务 ID、路径、主机名、文件名、时间戳一律用等宽，方便逐位扫读 */
export function MonoText({
  children,
  ellipsis,
  title,
}: {
  children: ReactNode
  ellipsis?: boolean
  title?: string
}) {
  const content = <span className={styles.mono}>{children}</span>
  if (!ellipsis) return content
  return (
    <Typography.Text className={styles.mono} ellipsis={{ tooltip: title ?? String(children) }}>
      {children}
    </Typography.Text>
  )
}

export function TimeText({ value }: { value: string | null }) {
  if (!value) return <span className={styles.mono}>-</span>
  return (
    <Tooltip title={dayjs(value).fromNow()}>
      <span className={styles.mono}>{formatTime(value)}</span>
    </Tooltip>
  )
}

// ---------------------------------------------------------------- 状态

const STATUS_ICON: Record<string, ReactNode> = {
  queued: <ClockCircleOutlined />,
  running: <LoadingOutlined />,
  completed: <CheckCircleFilled />,
  failed: <CloseCircleFilled />,
}

const STATUS_COLOR: Record<string, string> = {
  queued: 'default',
  running: 'processing',
  completed: 'success',
  failed: 'error',
}

/** 状态三重编码：图标 + 文字 + 颜色，颜色只作增强 */
export function StatusTag({ status, label }: { status: string; label: string }) {
  return (
    <Tag icon={STATUS_ICON[status]} color={STATUS_COLOR[status] ?? 'default'} bordered={false}>
      {label}
    </Tag>
  )
}

export function MetricCard({
  title,
  value,
  tone,
  hint,
}: {
  title: string
  value: number | string
  tone?: 'warning' | 'error'
  hint?: string
}) {
  const valueClass = [
    styles.metricValue,
    tone === 'warning' ? styles.metricValueWarning : '',
    tone === 'error' ? styles.metricValueError : '',
  ]
    .filter(Boolean)
    .join(' ')

  return (
    <Card size="small">
      <div className={styles.metric}>
        <span className={styles.metricTitle}>{title}</span>
        <span className={valueClass}>{value}</span>
        {hint && <span className={styles.metricHint}>{hint}</span>}
      </div>
    </Card>
  )
}

export function LiveIndicator({ active, lastUpdatedAt }: { active: boolean; lastUpdatedAt?: string }) {
  if (!active) return null
  return (
    <span className={styles.live}>
      <span className={styles.pulse} />
      自动刷新中{lastUpdatedAt ? ` · 上次更新 ${lastUpdatedAt}` : ''}
    </span>
  )
}

export function EmptyState({
  title,
  description,
  icon,
  action,
}: {
  title: string
  description?: string
  icon?: ReactNode
  action?: ReactNode
}) {
  return (
    <div className={styles.emptyState}>
      <span style={{ fontSize: 22 }}>{icon ?? <InboxOutlined />}</span>
      <span className={styles.emptyTitle}>{title}</span>
      {description && <span className={styles.emptyDescription}>{description}</span>}
      {action}
    </div>
  )
}

// ---------------------------------------------------------------- 完整度

export function CompletenessIcon({ actual, expected, hasLogs }: { actual: number; expected: number; hasLogs: boolean }) {
  if (!hasLogs) return <MinusCircleOutlined style={{ color: 'var(--app-text-3)' }} />
  if (actual >= expected) return <CheckCircleFilled style={{ color: 'var(--app-success)' }} />
  return <ExclamationCircleFilled style={{ color: 'var(--app-warning)' }} />
}

/** 「12/15」+ 细进度条。分子按状态着色，比单纯的三档图标更能表达"缺多少" */
export function CompletenessBar({
  actual,
  expected,
  hasLogs,
  width = 188,
}: {
  actual: number
  expected: number
  hasLogs: boolean
  width?: number
}) {
  const ratio = expected > 0 ? Math.min(actual / expected, 1) : 0
  const actualClass = !hasLogs ? styles.actualNone : actual >= expected ? styles.actualOk : styles.actualWarn

  return (
    <div className={styles.completeness}>
      <span className={styles.completenessCount}>
        <span className={`${styles.completenessActual} ${actualClass}`}>{actual}</span>
        <span>/{expected}</span>
      </span>
      <Progress
        percent={Math.round(ratio * 100)}
        size={[width, 4]}
        showInfo={false}
        status={hasLogs ? 'normal' : 'exception'}
      />
    </div>
  )
}

// ---------------------------------------------------------------- 交互

export function SelectableList<T>({
  items,
  selectedKey,
  getKey,
  renderLabel,
  renderExtra,
  onSelect,
  emptyText,
}: {
  items: T[]
  selectedKey: string | null
  getKey: (item: T) => string
  renderLabel: (item: T) => ReactNode
  renderExtra?: (item: T) => ReactNode
  onSelect: (key: string) => void
  emptyText: string
}) {
  if (items.length === 0) return <EmptyState title={emptyText} />
  return (
    <div className={styles.selectableList} role="listbox">
      {items.map((item) => {
        const key = getKey(item)
        const active = key === selectedKey
        return (
          <button
            key={key}
            type="button"
            role="option"
            aria-selected={active}
            className={`${styles.selectRow} ${active ? styles.selectRowActive : ''}`}
            onClick={() => onSelect(key)}
          >
            <span>{renderLabel(item)}</span>
            {renderExtra?.(item)}
          </button>
        )
      })}
    </div>
  )
}

export function ThemeToggle() {
  const { mode, setMode } = useTheme()
  return (
    <Segmented
      size="small"
      value={mode}
      onChange={(value) => setMode(value as ThemeMode)}
      options={[
        { value: 'light', icon: <SunOutlined />, title: '浅色' },
        { value: 'system', icon: <DesktopOutlined />, title: '跟随系统' },
        { value: 'dark', icon: <MoonOutlined />, title: '深色' },
      ]}
    />
  )
}
