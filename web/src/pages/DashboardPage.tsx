import { ReloadOutlined, UploadOutlined } from '@ant-design/icons'
import { Alert, App as AntApp, Button, Card, Progress, Space, Statistic, Table, Tag, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { usePolling } from '../hooks/usePolling'
import { request } from '../lib/api'
import { formatTime, statusColor } from '../lib/format'
import type { Announcement, Job, User } from '../lib/types'

export function DashboardPage({ user }: { user: User }) {
  const [jobs, setJobs] = useState<Job[]>([])
  const [announcement, setAnnouncement] = useState('')
  const [loading, setLoading] = useState(true)
  const { message, modal } = AntApp.useApp()
  const navigate = useNavigate()

  const loadJobs = async () => {
    try {
      const [jobsData, announcementData] = await Promise.all([
        request<Job[]>('/jobs'),
        request<Announcement>('/announcements'),
      ])
      setJobs(jobsData)
      setAnnouncement(announcementData.content)
    } catch (error) {
      message.error(error instanceof Error ? error.message : '加载任务失败')
    } finally {
      setLoading(false)
    }
  }

  const hasActive = jobs.some((job) => job.status === 'queued' || job.status === 'running')
  usePolling(loadJobs, hasActive || loading, 5000)

  const deleteJob = (jobId: string) => {
    modal.confirm({
      title: '删除任务',
      content: `确认删除任务 ${jobId} 吗？删除后不可恢复。`,
      okText: '确认删除',
      cancelText: '取消',
      centered: true,
      onOk: async () => {
        try {
          await request<{ ok: boolean }>(`/admin/jobs/${jobId}`, { method: 'DELETE' })
          message.success('任务已删除')
          await loadJobs()
        } catch (error) {
          message.error(error instanceof Error ? error.message : '删除任务失败')
        }
      },
    })
  }

  const stats = useMemo(
    () => ({
      total: jobs.length,
      active: jobs.filter((job) => ['queued', 'running'].includes(job.status)).length,
      completed: jobs.filter((job) => job.status === 'completed').length,
      failed: jobs.filter((job) => job.status === 'failed').length,
    }),
    [jobs],
  )

  const columns: ColumnsType<Job> = [
    {
      title: '任务ID',
      dataIndex: 'id',
      render: (value: string) => (
        <Button type="link" onClick={() => navigate(`/tasks/${value}`)} style={{ padding: 0 }}>
          {value}
        </Button>
      ),
    },
    { title: '提交人', dataIndex: 'username' },
    {
      title: '状态',
      dataIndex: 'status_label',
      render: (_, record) => <Tag color={statusColor(record.status)}>{record.status_label}</Tag>,
    },
    {
      title: '进度',
      render: (_, record) => (
        <div>
          <Progress percent={record.progress} size="small" status={record.status === 'failed' ? 'exception' : 'active'} />
          <Typography.Text type="secondary">{record.status_detail || '-'}</Typography.Text>
        </div>
      ),
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      render: (value: string) => formatTime(value),
    },
    {
      title: '完成时间',
      dataIndex: 'finished_at',
      render: (value: string | null) => formatTime(value),
    },
    {
      title: '操作',
      render: (_, record) => (
        <Space wrap>
          <Button onClick={() => navigate(`/tasks/${record.id}`)}>详情</Button>
          {record.bundle_available && <Button href={record.bundle_download_url || undefined}>下载</Button>}
          {user.is_admin && (
            <Button
              disabled={['queued', 'running'].includes(record.status)}
              onClick={() => deleteJob(record.id)}
            >
              删除
            </Button>
          )}
        </Space>
      ),
    },
  ]

  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      <div className="stat-grid">
        <Card>
          <Statistic title="总任务数" value={stats.total} />
        </Card>
        <Card>
          <Statistic title="处理中" value={stats.active} />
        </Card>
        <Card>
          <Statistic title="已完成" value={stats.completed} />
        </Card>
        <Card>
          <Statistic title="失败" value={stats.failed} />
        </Card>
      </div>
      <Card className="compact-card">
        <Space align="start" style={{ width: '100%', justifyContent: 'space-between' }}>
          <div>
            <Typography.Title level={5} style={{ marginTop: 0 }}>
              系统公告
            </Typography.Title>
            <Typography.Paragraph type="secondary" style={{ marginBottom: 0 }}>
              {announcement || '暂无公告'}
            </Typography.Paragraph>
          </div>
          <Button type="primary" icon={<UploadOutlined />} onClick={() => navigate('/tasks/new')}>
            创建任务
          </Button>
        </Space>
      </Card>
      <Card
        className="compact-card"
        title="任务中心"
        extra={
          <Button icon={<ReloadOutlined />} onClick={() => void loadJobs()}>
            刷新
          </Button>
        }
      >
        <Table<Job>
          rowKey="id"
          loading={loading}
          columns={columns}
          dataSource={jobs}
          pagination={{ pageSize: 12, showSizeChanger: false }}
          size="middle"
        />
      </Card>
      {!user.is_admin && hasActive && <Alert type="info" message="系统检测到仍有任务在处理中，页面会自动刷新。" showIcon />}
    </Space>
  )
}
