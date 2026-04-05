import { Button, Card, Space, Table, Tag } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { formatTime, statusColor } from '../../lib/format'
import type { Job } from '../../lib/types'

export function JobManagementSection({
  jobs,
  page,
  total,
  stats,
  onPageChange,
  onDeleteJob,
}: {
  jobs: Job[]
  page: number
  total: number
  stats: { total: number; active: number; completed: number; failed: number }
  onPageChange: (page: number) => void
  onDeleteJob: (jobId: string) => void | Promise<void>
}) {
  const columns: ColumnsType<Job> = [
    { title: '任务ID', dataIndex: 'id' },
    { title: '提交人', dataIndex: 'username' },
    { title: '状态', render: (_, record) => <Tag color={statusColor(record.status)}>{record.status_label}</Tag> },
    { title: '创建时间', render: (_, record) => formatTime(record.created_at) },
    { title: '完成时间', render: (_, record) => formatTime(record.finished_at) },
    {
      title: '操作',
      render: (_, record) => (
        <Space>
          {record.bundle_available && <Button href={record.bundle_download_url || undefined}>下载</Button>}
          <Button disabled={['queued', 'running'].includes(record.status)} onClick={() => void onDeleteJob(record.id)}>
            删除
          </Button>
        </Space>
      ),
    },
  ]

  return (
    <Card className="compact-card">
      <Table<Job>
        rowKey="id"
        columns={columns}
        dataSource={jobs}
        size="middle"
        title={() => `总任务 ${stats.total}，处理中 ${stats.active}，已完成 ${stats.completed}，失败 ${stats.failed}`}
        pagination={{
          current: page,
          pageSize: 20,
          total,
          showSizeChanger: false,
          onChange: onPageChange,
        }}
      />
    </Card>
  )
}
