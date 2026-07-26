import { Button, Card, Space, Table } from 'antd'
import type { ColumnsType } from 'antd/es/table'

import { MonoText, StatusTag, TimeText } from '../common'
import { canDeleteJob } from '../../lib/job'
import type { Job } from '../../lib/types'

export function JobManagementSection({
  jobs,
  loading,
  page,
  total,
  stats,
  onPageChange,
  onDeleteJob,
}: {
  jobs: Job[]
  loading: boolean
  page: number
  total: number
  stats: { total: number; active: number; completed: number; failed: number }
  onPageChange: (page: number) => void
  onDeleteJob: (jobId: string) => void | Promise<void>
}) {
  const columns: ColumnsType<Job> = [
    { title: '任务 ID', dataIndex: 'id', width: 190, render: (v: string) => <MonoText>{v}</MonoText> },
    { title: '提交人', dataIndex: 'username', width: 120 },
    {
      title: '状态',
      width: 100,
      render: (_, record) => <StatusTag status={record.status} label={record.status_label} />,
    },
    { title: '创建时间', width: 165, render: (_, record) => <TimeText value={record.created_at} /> },
    { title: '完成时间', width: 165, render: (_, record) => <TimeText value={record.finished_at} /> },
    {
      title: '操作',
      render: (_, record) => (
        <Space size={2}>
          {record.bundle_available && record.bundle_download_url && (
            <Button type="link" size="small" href={record.bundle_download_url}>
              下载
            </Button>
          )}
          <Button
            type="link"
            size="small"
            danger
            disabled={!canDeleteJob(record)}
            onClick={() => void onDeleteJob(record.id)}
          >
            删除
          </Button>
        </Space>
      ),
    },
  ]

  return (
    <Card
      size="small"
      title={`总任务 ${stats.total} · 处理中 ${stats.active} · 已完成 ${stats.completed} · 失败 ${stats.failed}`}
    >
      <Table<Job>
        rowKey="id"
        size="small"
        columns={columns}
        dataSource={jobs}
        loading={loading}
        sticky
        scroll={{ x: 'max-content' }}
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
