import { Alert, App as AntApp, Button, Card, Descriptions, List, Progress, Result, Space, Spin, Tag, Typography } from 'antd'
import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { usePolling } from '../hooks/usePolling'
import { request } from '../lib/api'
import { formatTime, statusColor } from '../lib/format'
import type { Job } from '../lib/types'

export function TaskDetailPage() {
  const { jobId = '' } = useParams()
  const [job, setJob] = useState<Job | null>(null)
  const [loading, setLoading] = useState(true)
  const { message } = AntApp.useApp()

  const load = async () => {
    try {
      const data = await request<Job>(`/jobs/${jobId}`)
      setJob(data)
    } catch (error) {
      message.error(error instanceof Error ? error.message : '加载任务详情失败')
    } finally {
      setLoading(false)
    }
  }

  usePolling(load, !job || ['queued', 'running'].includes(job.status), 3000)

  if (loading && !job) return <Spin size="large" />
  if (!job) return <Result status="404" title="任务不存在" />

  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      <div className="detail-grid">
        <Card className="compact-card" title="任务状态">
          <Descriptions column={1} size="small">
            <Descriptions.Item label="任务ID">{job.id}</Descriptions.Item>
            <Descriptions.Item label="提交人">{job.username}</Descriptions.Item>
            <Descriptions.Item label="状态">
              <Tag color={statusColor(job.status)}>{job.status_label}</Tag>
            </Descriptions.Item>
            <Descriptions.Item label="进度">
              <Progress percent={job.progress} status={job.status === 'failed' ? 'exception' : 'active'} />
              <Typography.Text type="secondary">{job.status_detail || '-'}</Typography.Text>
            </Descriptions.Item>
            <Descriptions.Item label="创建时间">{formatTime(job.created_at)}</Descriptions.Item>
            <Descriptions.Item label="完成时间">{formatTime(job.finished_at)}</Descriptions.Item>
            <Descriptions.Item label="日志根目录">{job.log_root || '-'}</Descriptions.Item>
          </Descriptions>
          {job.bundle_available && (
            <Button type="primary" href={job.bundle_download_url || undefined}>
              下载任务结果
            </Button>
          )}
        </Card>
        <Card className="compact-card" title="结果文件">
          <List
            size="small"
            dataSource={job.generated_files}
            locale={{ emptyText: '尚未生成文件' }}
            renderItem={(item) => (
              <List.Item actions={[<a key="download" href={item.download_url}>下载</a>]}>
                {item.name}
              </List.Item>
            )}
          />
          <Alert
            style={{ marginTop: 16 }}
            type={job.error_message ? 'error' : 'success'}
            showIcon
            message={job.error_message ? job.error_message : '当前没有错误信息'}
          />
        </Card>
      </div>
      <Card className="compact-card" title="处理时间线">
        <div className="timeline-grid">
          {job.timeline.map((item) => (
            <div key={item.step} className={`timeline-card${item.active ? ' active' : ''}`}>
              <span className="timeline-step">{item.step}</span>
              <div>
                <Typography.Text strong>{item.title}</Typography.Text>
                <Typography.Paragraph type="secondary" style={{ marginBottom: 0 }}>
                  {item.description}
                </Typography.Paragraph>
              </div>
            </div>
          ))}
        </div>
      </Card>
    </Space>
  )
}
