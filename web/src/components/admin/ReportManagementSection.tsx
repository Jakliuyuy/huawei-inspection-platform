import { Button, Card, List, Space, Table, Tag } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import type { ReportDate, ReportFile, ReportUser } from '../../lib/types'

export function ReportManagementSection({
  reportDates,
  reportUsers,
  reportFiles,
  selectedDate,
  selectedUser,
  onSelectDate,
  onSelectUser,
  onDeleteReport,
}: {
  reportDates: ReportDate[]
  reportUsers: ReportUser[]
  reportFiles: ReportFile[]
  selectedDate: string | null
  selectedUser: string | null
  onSelectDate: (value: string) => void
  onSelectUser: (value: string) => void
  onDeleteReport: (jobId: string, fileName: string) => void | Promise<void>
}) {
  const columns: ColumnsType<ReportFile> = [
    { title: '任务ID', dataIndex: 'job_id' },
    { title: '文件名', dataIndex: 'name' },
    { title: '大小', dataIndex: 'size' },
    { title: '更新时间', dataIndex: 'modified_at' },
    {
      title: '操作',
      render: (_, record) => (
        <Space>
          <Button href={record.download_url}>下载</Button>
          <Button onClick={() => void onDeleteReport(record.job_id, record.name)}>删除</Button>
        </Space>
      ),
    },
  ]

  return (
    <div className="report-grid">
      <Card className="compact-card" title="日期">
        <List
          dataSource={reportDates}
          renderItem={(item) => (
            <List.Item
              className={selectedDate === item.report_date ? 'select-row active' : 'select-row'}
              onClick={() => onSelectDate(item.report_date)}
            >
              <span>{item.report_date}</span>
              <Tag>{item.count}</Tag>
            </List.Item>
          )}
        />
      </Card>
      <Card className="compact-card" title={selectedDate ? `${selectedDate} 的用户` : '请选择日期'}>
        <List
          dataSource={reportUsers}
          locale={{ emptyText: '请选择日期后查看用户' }}
          renderItem={(item) => (
            <List.Item
              className={selectedUser === item.username ? 'select-row active' : 'select-row'}
              onClick={() => onSelectUser(item.username)}
            >
              <span>{item.username}</span>
              <Tag>{item.count}</Tag>
            </List.Item>
          )}
        />
      </Card>
      <Card className="compact-card" title={selectedUser ? `${selectedUser} 的文档` : '请选择用户'}>
        <Table<ReportFile>
          rowKey={(record) => `${record.job_id}-${record.name}`}
          columns={columns}
          dataSource={reportFiles}
          pagination={false}
          size="small"
        />
      </Card>
    </div>
  )
}
