import { DownloadOutlined, MailOutlined, ReloadOutlined } from '@ant-design/icons'
import { Alert, App as AntApp, Button, Card, Descriptions, Grid, List, Progress, Result, Space, Steps } from 'antd'
import { useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { SendEmailModal } from '../components/SendEmailModal'
import { EmptyState, MonoText, PageHeader, StatusTag, TimeText } from '../components/common'
import { usePolling } from '../hooks/usePolling'
import { ApiError, isUnauthorized, request } from '../lib/api'
import { isActiveStatus } from '../lib/job'
import type { Job } from '../lib/types'
import styles from './pages.module.css'

export function TaskDetailPage() {
  const { jobId = '' } = useParams()
  const [job, setJob] = useState<Job | null>(null)
  const [loading, setLoading] = useState(true)
  const [emailModalOpen, setEmailModalOpen] = useState(false)
  const [loadStopped, setLoadStopped] = useState(false)
  const failureCount = useRef(0)
  const errorNotified = useRef(false)
  const { message } = AntApp.useApp()
  const screens = Grid.useBreakpoint()

  const load = async () => {
    try {
      const data = await request<Job>(`/jobs/${jobId}`)
      failureCount.current = 0
      errorNotified.current = false
      setJob(data)
      setLoadStopped(false)
    } catch (error) {
      if (isUnauthorized(error)) {
        // 全局 handler 会跳登录，这里既不计数也不提示
        setLoadStopped(true)
        return
      }
      failureCount.current += 1
      // 404/403 是终态，连续失败 3 次同样停止轮询，避免定时器长期空转。
      const terminal = error instanceof ApiError && [403, 404].includes(error.status)
      if (terminal || failureCount.current >= 3) {
        setLoadStopped(true)
      }
      if (!errorNotified.current) {
        errorNotified.current = true
        message.error(error instanceof Error ? error.message : '加载任务详情失败')
      }
    } finally {
      setLoading(false)
    }
  }

  usePolling(load, !loadStopped && (!job || isActiveStatus(job.status)), 3000)

  if (loading && !job) {
    return (
      <div style={{ display: 'grid', placeItems: 'center', minHeight: '40vh' }}>
        <Progress type="circle" percent={0} size={48} showInfo={false} />
      </div>
    )
  }
  if (!job) return <Result status="404" title="任务不存在" />

  const canSendEmail = job.status === 'completed' && job.generated_files.length > 0
  const reached = job.timeline.filter((item) => item.active).length
  const steps = job.timeline.map((item, index) => ({
    title: item.title,
    description: item.description,
    status:
      index < reached - 1
        ? ('finish' as const)
        : index === reached - 1
          ? job.status === 'failed'
            ? ('error' as const)
            : job.status === 'completed'
              ? ('finish' as const)
              : ('process' as const)
          : ('wait' as const),
  }))

  return (
    <>
      <PageHeader
        breadcrumb={[{ title: <Link to="/dashboard">任务中心</Link> }, { title: '任务详情' }]}
        title={job.id}
        extra={
          <>
            <StatusTag status={job.status} label={job.status_label} />
            {job.bundle_available && job.bundle_download_url && (
              <Button type="primary" icon={<DownloadOutlined />} href={job.bundle_download_url}>
                下载结果
              </Button>
            )}
            {canSendEmail && (
              <Button icon={<MailOutlined />} onClick={() => setEmailModalOpen(true)}>
                发送邮件
              </Button>
            )}
            <Button icon={<ReloadOutlined />} onClick={() => void load()} aria-label="刷新" />
          </>
        }
      />

      <Space direction="vertical" size={16} style={{ width: '100%' }}>
        {/* 进度是全页最该一眼看到的信息，单独提到最上方 */}
        <Card size="small">
          <Progress
            percent={job.progress}
            status={job.status === 'failed' ? 'exception' : job.status === 'completed' ? 'success' : 'active'}
          />
          <div className={styles.progressDetail} style={{ marginTop: 4 }}>
            {job.status_detail || '—'}
          </div>
        </Card>

        <div className={styles.detailGrid}>
          <Card size="small" title="任务信息">
            <Descriptions column={{ xs: 1, md: 2 }} size="small">
              <Descriptions.Item label="任务 ID">
                <MonoText>{job.id}</MonoText>
              </Descriptions.Item>
              <Descriptions.Item label="提交人">{job.username}</Descriptions.Item>
              <Descriptions.Item label="报告日期">
                <MonoText>{job.report_date || '—'}</MonoText>
              </Descriptions.Item>
              <Descriptions.Item label="生成范围">
                {job.selected_systems.length === 0 ? '全部系统' : job.selected_systems.join('、')}
              </Descriptions.Item>
              <Descriptions.Item label="创建时间">
                <TimeText value={job.created_at} />
              </Descriptions.Item>
              <Descriptions.Item label="完成时间">
                <TimeText value={job.finished_at} />
              </Descriptions.Item>
              <Descriptions.Item label="日志根目录" span={2}>
                <MonoText ellipsis>{job.log_root || '—'}</MonoText>
              </Descriptions.Item>
            </Descriptions>
          </Card>

          <Card size="small" title="结果文件">
            {job.generated_files.length === 0 ? (
              <EmptyState title="尚未生成文件" />
            ) : (
              <List
                size="small"
                dataSource={job.generated_files}
                renderItem={(item) => (
                  <List.Item
                    actions={[
                      <a key="download" href={item.download_url}>
                        下载
                      </a>,
                    ]}
                  >
                    <MonoText ellipsis>{item.name}</MonoText>
                  </List.Item>
                )}
              />
            )}
            {job.error_message && (
              <Alert style={{ marginTop: 12 }} type="error" showIcon message={job.error_message} />
            )}
          </Card>
        </div>

        <Card size="small" title="处理时间线">
          <Steps
            size="small"
            direction={screens.xl ? 'horizontal' : 'vertical'}
            items={steps}
          />
        </Card>
      </Space>

      <SendEmailModal
        open={emailModalOpen}
        jobId={job.id}
        files={job.generated_files}
        onCancel={() => setEmailModalOpen(false)}
      />
    </>
  )
}
