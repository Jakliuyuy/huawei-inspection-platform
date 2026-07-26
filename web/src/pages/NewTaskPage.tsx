import { CalendarOutlined, InboxOutlined, ReloadOutlined } from '@ant-design/icons'
import {
  Alert,
  App as AntApp,
  Button,
  Card,
  DatePicker,
  List,
  Progress,
  Segmented,
  Space,
  Steps,
  Table,
  Tag,
  Typography,
} from 'antd'
import type { ColumnsType } from 'antd/es/table'
import dayjs, { type Dayjs } from 'dayjs'
import { useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import {
  CompletenessBar,
  CompletenessIcon,
  EmptyState,
  MonoText,
  PageHeader,
} from '../components/common'
import {
  ApiError,
  UPLOAD_TRANSPORT_HINT,
  UploadTransportError,
  isUnauthorized,
  request,
  uploadWithProgress,
  type UploadProgress,
} from '../lib/api'
import { buildUploadForm, dedupeFiles, displayPath, filesFromDrop, type UploadMode } from '../lib/fileTree'
import { fillOutputName } from '../lib/job'
import type { SystemStat, UploadPreview } from '../lib/types'
import styles from './pages.module.css'

type Stage = 'idle' | 'uploading' | 'analyzing' | 'preview' | 'submitting'

const PREVIEW_LIMIT = 15

export function NewTaskPage() {
  const { message } = AntApp.useApp()
  const navigate = useNavigate()

  const [stage, setStage] = useState<Stage>('idle')
  const [mode, setMode] = useState<UploadMode>('zip')
  const [dragging, setDragging] = useState(false)
  const [files, setFiles] = useState<File[]>([])
  const [progress, setProgress] = useState<UploadProgress | null>(null)
  const [preview, setPreview] = useState<UploadPreview | null>(null)
  const [selected, setSelected] = useState<string[]>([])
  const [reportDate, setReportDate] = useState<Dayjs | null>(null)
  const [filter, setFilter] = useState<'all' | 'with' | 'without'>('all')

  const filesRef = useRef<HTMLInputElement>(null)
  const folderRef = useRef<HTMLInputElement>(null)
  const abortRef = useRef<(() => void) | null>(null)

  const activeInputRef = mode === 'zip' ? filesRef : folderRef

  // ------------------------------------------------------------ 选择文件

  const syncFromInputs = () => {
    const picked = [...(filesRef.current?.files ?? []), ...(folderRef.current?.files ?? [])]
    setFiles(dedupeFiles(picked))
  }

  const handleDrop = async (event: React.DragEvent) => {
    event.preventDefault()
    setDragging(false)
    const dropped = await filesFromDrop(event.dataTransfer, mode)
    if (dropped.length === 0) {
      message.error(mode === 'zip' ? '未检测到可上传文件' : '请拖入日志目录或目录中的文件')
      return
    }
    setFiles((prev) => dedupeFiles([...prev, ...dropped]))
  }

  const resetToIdle = () => {
    setStage('idle')
    setPreview(null)
    setSelected([])
    setReportDate(null)
    setProgress(null)
  }

  // ------------------------------------------------------------ 上传与解析

  const startUpload = async (source: File[] = files) => {
    if (source.length === 0) {
      message.error('请先选择要上传的内容')
      return
    }
    setStage('uploading')
    setProgress({ loaded: 0, total: 0, percent: 0 })

    const { promise, abort } = uploadWithProgress<UploadPreview>(
      '/uploads',
      buildUploadForm(source),
      (p) => {
        setProgress(p)
        // 传完最后一个字节后服务端还要解压+扫描，状态要跟上
        if (p.percent >= 100) setStage('analyzing')
      },
    )
    abortRef.current = abort

    try {
      const data = await promise
      setPreview(data)
      setSelected(data.systems.filter((s) => s.has_logs).map((s) => s.key))
      setReportDate(dayjs(data.suggested_report_date))
      setStage('preview')
    } catch (error) {
      if ((error as DOMException)?.name === 'AbortError') {
        resetToIdle()
        return
      }
      if (error instanceof UploadTransportError) {
        message.error(UPLOAD_TRANSPORT_HINT)
      } else if (!isUnauthorized(error)) {
        message.error(error instanceof Error ? error.message : '上传失败')
      }
      setStage('idle')
      setProgress(null)
    } finally {
      abortRef.current = null
    }
  }

  // ------------------------------------------------------------ 提交生成

  const submit = async () => {
    if (!preview || !reportDate) return
    setStage('submitting')
    try {
      const result = await request<{ ok: boolean; job_id: string }>('/jobs', {
        method: 'POST',
        body: JSON.stringify({
          upload_id: preview.upload_id,
          systems: selected,
          report_date: reportDate.format('YYYY-MM-DD'),
        }),
      })
      message.success(`任务 ${result.job_id} 已创建`)
      navigate(`/tasks/${result.job_id}`)
    } catch (error) {
      // 暂存会话过期时文件还在内存里，可以一键重传，不必让用户重选
      if (error instanceof ApiError && error.status === 410) {
        message.warning('解析结果已过期，正在用已选文件重新解析')
        void startUpload()
        return
      }
      if (!isUnauthorized(error)) {
        message.error(error instanceof Error ? error.message : '创建任务失败')
      }
      setStage('preview')
    }
  }

  // ------------------------------------------------------------ 预览表格

  const visibleSystems = useMemo(() => {
    if (!preview) return []
    if (filter === 'with') return preview.systems.filter((s) => s.has_logs)
    if (filter === 'without') return preview.systems.filter((s) => !s.has_logs)
    return preview.systems
  }, [preview, filter])

  const missingSystems = preview?.systems.filter((s) => !s.has_logs) ?? []
  const selectedStats = preview?.systems.filter((s) => selected.includes(s.key)) ?? []
  const selectedDevices = selectedStats.reduce((sum, s) => sum + s.actual, 0)
  const dateText = reportDate?.format('YYYY-MM-DD') ?? ''

  const columns: ColumnsType<SystemStat> = [
    {
      title: '',
      key: 'icon',
      width: 48,
      render: (_: unknown, row) => (
        <CompletenessIcon actual={row.actual} expected={row.expected} hasLogs={row.has_logs} />
      ),
    },
    {
      title: '系统',
      dataIndex: 'display_name',
      width: 220,
      render: (name: string, row) => (
        <div>
          <div>{name}</div>
          <MonoText>
            <span style={{ fontSize: 12, color: 'var(--app-text-3)' }}>{row.key}</span>
          </MonoText>
        </div>
      ),
    },
    {
      title: '设备完整度',
      key: 'completeness',
      width: 210,
      render: (_: unknown, row) => (
        <CompletenessBar actual={row.actual} expected={row.expected} hasLogs={row.has_logs} />
      ),
    },
    {
      title: '情况',
      key: 'note',
      width: 130,
      render: (_: unknown, row) =>
        !row.has_logs ? (
          <span style={{ color: 'var(--app-text-3)' }}>无日志</span>
        ) : row.missing > 0 ? (
          <span style={{ color: 'var(--app-warning)' }}>缺 {row.missing} 台</span>
        ) : (
          <span style={{ color: 'var(--app-success)' }}>已就绪</span>
        ),
    },
    {
      title: '预计输出',
      key: 'output',
      render: (_: unknown, row) => (
        <MonoText ellipsis>{fillOutputName(row.output_name_template, dateText)}</MonoText>
      ),
    },
  ]

  const stepIndex = stage === 'preview' || stage === 'submitting' ? 1 : 0

  return (
    <>
      <PageHeader title="新建巡检任务" description="上传日志后确认生成范围与报告日期">
        <Steps
          size="small"
          current={stepIndex}
          items={[{ title: '选择日志' }, { title: '确认系统与日期' }, { title: '生成报告' }]}
        />
      </PageHeader>

      {stage === 'preview' || stage === 'submitting' ? (
        <PreviewStep />
      ) : (
        <UploadStep />
      )}
    </>
  )

  // ------------------------------------------------------------ 步骤一

  function UploadStep() {
    const busy = stage === 'uploading' || stage === 'analyzing'
    return (
      <div className={styles.createGrid}>
        <Card size="small">
          <Space direction="vertical" size={16} style={{ width: '100%' }}>
            <Segmented
              block
              value={mode}
              onChange={(value) => setMode(value as UploadMode)}
              disabled={busy}
              options={[
                { label: 'ZIP / 文件', value: 'zip' },
                { label: '日志目录', value: 'folder' },
              ]}
            />

            <input
              ref={filesRef}
              type="file"
              multiple
              accept=".zip,.log,application/zip,application/x-zip-compressed"
              onChange={syncFromInputs}
              className={styles.hiddenInput}
            />
            <input
              ref={folderRef}
              type="file"
              multiple
              onChange={syncFromInputs}
              className={styles.hiddenInput}
              {...({ webkitdirectory: 'true', directory: 'true' } as Record<string, string>)}
            />

            {busy ? (
              <div className={styles.progressPanel}>
                <Progress
                  percent={stage === 'analyzing' ? 100 : (progress?.percent ?? 0)}
                  status={stage === 'analyzing' ? 'active' : 'normal'}
                />
                <span className={styles.progressMeta}>
                  {stage === 'analyzing'
                    ? '正在解压并扫描日志目录，识别系统与设备数…'
                    : `正在上传 ${files.length} 个文件`}
                </span>
                {stage === 'uploading' && (
                  <div>
                    <Button size="small" onClick={() => abortRef.current?.()}>
                      取消上传
                    </Button>
                  </div>
                )}
              </div>
            ) : (
              <button
                type="button"
                className={`${styles.dropzone} ${dragging ? styles.dropzoneActive : ''}`}
                onClick={() => activeInputRef.current?.click()}
                onDragEnter={(e) => {
                  e.preventDefault()
                  setDragging(true)
                }}
                onDragOver={(e) => {
                  e.preventDefault()
                  e.dataTransfer.dropEffect = 'copy'
                }}
                onDragLeave={(e) => {
                  if (e.currentTarget === e.target) setDragging(false)
                }}
                onDrop={(e) => void handleDrop(e)}
              >
                <span className={styles.dropzoneIcon}>
                  <InboxOutlined />
                </span>
                <span className={styles.dropzoneCopy}>
                  <span className={styles.dropzoneTitle}>
                    {mode === 'zip' ? '点击选择 ZIP 或日志文件' : '点击选择整个日志目录'}
                  </span>
                  <span className={styles.dropzoneHint}>
                    {mode === 'zip'
                      ? '支持 ZIP、多个日志文件混合，也可直接拖拽到这里'
                      : '选择目录后保留原始层级上传，也可直接拖拽目录到这里'}
                  </span>
                </span>
                <Tag color={files.length ? 'success' : undefined} bordered={false}>
                  {files.length ? `已选 ${files.length} 项` : '尚未选择'}
                </Tag>
              </button>
            )}

            <Button type="primary" loading={busy} disabled={files.length === 0} onClick={() => void startUpload()}>
              上传并解析
            </Button>
          </Space>
        </Card>

        <Card size="small" title="当前选择" className={styles.sticky}>
          {files.length === 0 ? (
            <EmptyState title="当前未选择文件" description="选择 ZIP 压缩包或整个日志目录" />
          ) : (
            <List
              size="small"
              dataSource={files.slice(0, PREVIEW_LIMIT)}
              renderItem={(file) => (
                <List.Item>
                  <MonoText ellipsis>{displayPath(file)}</MonoText>
                </List.Item>
              )}
              footer={
                files.length > PREVIEW_LIMIT ? (
                  <span style={{ fontSize: 12, color: 'var(--app-text-3)' }}>
                    还有 {files.length - PREVIEW_LIMIT} 个文件未展开
                  </span>
                ) : null
              }
            />
          )}
        </Card>
      </div>
    )
  }

  // ------------------------------------------------------------ 步骤二

  function PreviewStep() {
    if (!preview) return null
    return (
      <Space direction="vertical" size={16} style={{ width: '100%' }}>
        <Card size="small">
          <div className={styles.summaryRow}>
            <span>
              日志根目录 <span className={styles.summaryValue}>{preview.log_root_label}</span>
            </span>
            <span>
              识别系统 <span className={styles.summaryValue}>{preview.systems.length}</span> 个
            </span>
            <span>
              实到设备 <span className={styles.summaryValue}>{preview.log_file_count}</span> 台
            </span>
            <Button size="small" icon={<ReloadOutlined />} onClick={resetToIdle} style={{ marginLeft: 'auto' }}>
              重新选择文件
            </Button>
          </div>
        </Card>

        {!preview.detected && (
          <Alert
            type="warning"
            showIcon
            message="未能识别出标准的日志目录结构，已按上传根目录统计，请确认下方设备数是否符合预期"
          />
        )}

        {missingSystems.length > 0 && (
          <Alert
            type="warning"
            showIcon
            message={`${missingSystems.length} 个系统未检测到日志：${missingSystems.map((s) => s.display_name).join('、')}`}
            description="若本次不需巡检可忽略；否则请补齐日志后重新上传。"
          />
        )}

        <div className={styles.createGrid}>
          <Card
            size="small"
            title={
              <div className={styles.tableToolbar}>
                <Segmented
                  size="small"
                  value={filter}
                  onChange={(v) => setFilter(v as typeof filter)}
                  options={[
                    { label: `全部 ${preview.systems.length}`, value: 'all' },
                    { label: `有日志 ${preview.systems.length - missingSystems.length}`, value: 'with' },
                    { label: `无日志 ${missingSystems.length}`, value: 'without' },
                  ]}
                />
                <span style={{ fontSize: 12, color: 'var(--app-text-2)' }}>
                  已选 {selected.length} / {preview.systems.length} 个系统 · 共 {selectedDevices} 台设备
                </span>
              </div>
            }
            extra={
              <div className={styles.toolbarActions}>
                <Button
                  type="link"
                  size="small"
                  onClick={() => setSelected(preview.systems.filter((s) => s.has_logs).map((s) => s.key))}
                >
                  全选
                </Button>
                <Button type="link" size="small" onClick={() => setSelected([])}>
                  全不选
                </Button>
                <Button
                  type="link"
                  size="small"
                  onClick={() =>
                    setSelected(preview.systems.filter((s) => s.has_logs && s.actual >= s.expected).map((s) => s.key))
                  }
                >
                  仅选完整的
                </Button>
              </div>
            }
          >
            <Table
              rowKey="key"
              size="small"
              dataSource={visibleSystems}
              columns={columns}
              pagination={false}
              scroll={{ x: 'max-content' }}
              rowClassName={(row) => (row.has_logs ? '' : styles.rowMuted)}
              rowSelection={{
                selectedRowKeys: selected,
                onChange: (keys) => setSelected(keys as string[]),
                // 没有日志的系统即使勾上也只能生成空报告
                getCheckboxProps: (row) => ({
                  disabled: !row.has_logs,
                  title: row.has_logs ? undefined : '该系统未检测到日志，无法生成报告',
                }),
                columnWidth: 44,
              }}
            />
          </Card>

          <Card size="small" title="生成参数" className={styles.sticky}>
            <Space direction="vertical" size={12} style={{ width: '100%' }}>
              <div>
                <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                  报告日期
                </Typography.Text>
                <DatePicker
                  style={{ width: '100%', marginTop: 4 }}
                  value={reportDate}
                  onChange={setReportDate}
                  allowClear={false}
                  format="YYYY-MM-DD"
                  suffixIcon={<CalendarOutlined />}
                  disabledDate={(d) => d.isAfter(dayjs(), 'day')}
                />
                <div style={{ fontSize: 12, color: 'var(--app-text-3)', marginTop: 4 }}>
                  默认取自日志目录名 {preview.log_root_label}
                </div>
                <Space size={4} style={{ marginTop: 6 }}>
                  <Button size="small" type="link" onClick={() => setReportDate(dayjs(preview.suggested_report_date))}>
                    日志推断日
                  </Button>
                  <Button size="small" type="link" onClick={() => setReportDate(dayjs().subtract(1, 'day'))}>
                    昨天
                  </Button>
                  <Button size="small" type="link" onClick={() => setReportDate(dayjs())}>
                    今天
                  </Button>
                </Space>
              </div>

              <div>
                <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                  将生成 {selected.length} 份 Word
                </Typography.Text>
                <ul className={styles.outputList}>
                  {selectedStats.map((s) => (
                    <li key={s.key} className={styles.outputItem}>
                      {fillOutputName(s.output_name_template, dateText)}
                    </li>
                  ))}
                </ul>
              </div>

              <Button
                type="primary"
                block
                loading={stage === 'submitting'}
                disabled={selected.length === 0 || !reportDate}
                onClick={() => void submit()}
              >
                开始生成报告
              </Button>
            </Space>
          </Card>
        </div>
      </Space>
    )
  }
}
