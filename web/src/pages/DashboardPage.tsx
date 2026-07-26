import { PlusOutlined, ReloadOutlined } from '@ant-design/icons'
import { Alert, App as AntApp, Button, Card, Progress, Space, Table } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { LiveIndicator, MetricCard, MonoText, PageHeader, StatusTag, TimeText } from '../components/common'
import { usePolling } from '../hooks/usePolling'
import { isUnauthorized, request } from '../lib/api'
import { canDeleteJob } from '../lib/job'
import type { Announcement, Job, JobPage, JobStats, User } from '../lib/types'
import styles from './pages.module.css'

const PAGE_SIZE = 12

export function DashboardPage({ user, localMode }: { user: User | null; localMode: boolean }) {
  const [jobs, setJobs] = useState<Job[]>([])
  const [stats, setStats] = useState<JobStats>({ total: 0, active: 0, completed: 0, failed: 0 })
  const [page, setPage] = useState(1)
  const [total, setTotal] = useState(0)
  const [announcement, setAnnouncement] = useState('')
  const [loading, setLoading] = useState(true)
  const [updatedAt, setUpdatedAt] = useState('')
  const { message, modal } = AntApp.useApp()
  const navigate = useNavigate()

  const isAdmin = localMode || !!user?.is_admin

  const loadJobs = async (nextPage = page) => {
    try {
      const [jobsData, announcementData] = await Promise.all([
        request<JobPage>(`/jobs?page=${nextPage}&page_size=${PAGE_SIZE}`),
        request<Announcement>('/announcements'),
      ])
      setJobs(jobsData.items)
      setStats(jobsData.stats)
      setPage(jobsData.page)
      setTotal(jobsData.total)
      setAnnouncement(announcementData.content)
      setUpdatedAt(new Date().toLocaleTimeString('zh-CN', { hour12: false }))
    } catch (error) {
      if (!isUnauthorized(error)) {
        message.error(error instanceof Error ? error.message : '加载任务失败')
      }
    } finally {
      setLoading(false)
    }
  }

  const hasActive = stats.active > 0
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
          await loadJobs(page)
        } catch (error) {
          message.error(error instanceof Error ? error.message : '删除任务失败')
        }
      },
    })
  }

  const columns: ColumnsType<Job> = [
    {
      title: '任务 ID',
      dataIndex: 'id',
      width: 190,
      render: (id: string) => (
        <Button type="link" size="small" style={{ padding: 0 }} onClick={() => navigate(`/tasks/${id}`)}>
          <MonoText>{id}</MonoText>
        </Button>
      ),
    },
    // 本地模式是单用户，提交人这一列没有信息量
    ...(localMode ? [] : [{ title: '提交人', dataIndex: 'username', width: 120 }]),
    {
      title: '状态',
      dataIndex: 'status',
      width: 100,
      render: (status: string, row: Job) => <StatusTag status={status} label={row.status_label} />,
    },
    {
      title: '进度',
      dataIndex: 'progress',
      width: 200,
      render: (progress: number, row: Job) => (
        <div className={styles.progressCell}>
          <Progress
            percent={progress}
            size="small"
            showInfo={false}
            status={row.status === 'failed' ? 'exception' : 'active'}
          />
          <span className={styles.progressDetail} title={row.status_detail}>
            {row.status_detail || '—'}
          </span>
        </div>
      ),
    },
    { title: '创建时间', dataIndex: 'created_at', width: 165, render: (v: string) => <TimeText value={v} /> },
    {
      title: '完成时间',
      dataIndex: 'finished_at',
      width: 165,
      render: (v: string | null) => <TimeText value={v} />,
    },
    {
      title: '操作',
      key: 'actions',
      render: (_: unknown, row: Job) => (
        <Space size={2}>
          <Button type="link" size="small" onClick={() => navigate(`/tasks/${row.id}`)}>
            详情
          </Button>
          {row.bundle_available && row.bundle_download_url && (
            <Button type="link" size="small" href={row.bundle_download_url}>
              下载
            </Button>
          )}
          {isAdmin && (
            <Button type="link" size="small" danger disabled={!canDeleteJob(row)} onClick={() => deleteJob(row.id)}>
              删除
            </Button>
          )}
        </Space>
      ),
    },
  ]

  return (
    <>
      <PageHeader
        title="任务中心"
        description="查看与管理全部巡检任务"
        extra={
          <>
            <Button icon={<ReloadOutlined />} onClick={() => void loadJobs(page)}>
              刷新
            </Button>
            <Button type="primary" icon={<PlusOutlined />} onClick={() => navigate('/tasks/new')}>
              新建任务
            </Button>
          </>
        }
      />

      {announcement && <Alert type="info" showIcon message={announcement} style={{ marginBottom: 16 }} />}

      <div className={styles.statGrid}>
        <MetricCard title="总任务" value={stats.total} />
        <MetricCard title="处理中" value={stats.active} tone={stats.active > 0 ? 'warning' : undefined} />
        <MetricCard title="已完成" value={stats.completed} />
        <MetricCard title="失败" value={stats.failed} tone={stats.failed > 0 ? 'error' : undefined} />
      </div>

      <Card size="small" title="任务列表" extra={<LiveIndicator active={hasActive} lastUpdatedAt={updatedAt} />}>
        <Table
          rowKey="id"
          size="small"
          dataSource={jobs}
          columns={columns}
          loading={loading}
          sticky
          scroll={{ x: 'max-content' }}
          pagination={{
            current: page,
            pageSize: PAGE_SIZE,
            total,
            showSizeChanger: false,
            onChange: (next) => void loadJobs(next),
          }}
        />
      </Card>
    </>
  )
}
