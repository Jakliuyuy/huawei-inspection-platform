import { Button, Card, Space, Table, Tag } from 'antd'
import type { ColumnsType } from 'antd/es/table'

import { MonoText, SelectableList } from '../common'
import type { ReportDate, ReportFile, ReportUser } from '../../lib/types'
import styles from '../../pages/pages.module.css'

export function ReportManagementSection({
  loading,
  reportDates,
  reportUsers,
  reportFiles,
  selectedDate,
  selectedUser,
  onSelectDate,
  onSelectUser,
  onDeleteReport,
}: {
  loading: boolean
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
    { title: '任务 ID', dataIndex: 'job_id', width: 170, render: (v: string) => <MonoText>{v}</MonoText> },
    { title: '文件名', dataIndex: 'name', ellipsis: true },
    { title: '大小', dataIndex: 'size', width: 90, render: (v: string) => <MonoText>{v}</MonoText> },
    { title: '更新时间', dataIndex: 'modified_at', width: 165, render: (v: string) => <MonoText>{v}</MonoText> },
    {
      title: '操作',
      width: 120,
      render: (_, record) => (
        <Space size={2}>
          <Button type="link" size="small" href={record.download_url}>
            下载
          </Button>
          <Button type="link" size="small" danger onClick={() => void onDeleteReport(record.job_id, record.name)}>
            删除
          </Button>
        </Space>
      ),
    },
  ]

  return (
    <div className={styles.reportGrid}>
      <Card size="small" title="日期" loading={loading}>
        <SelectableList
          items={reportDates}
          selectedKey={selectedDate}
          getKey={(item) => item.report_date}
          renderLabel={(item) => <MonoText>{item.report_date}</MonoText>}
          renderExtra={(item) => <Tag bordered={false}>{item.count}</Tag>}
          onSelect={onSelectDate}
          emptyText="暂无归档报告"
        />
      </Card>

      <Card size="small" title={selectedDate ? `${selectedDate} 的用户` : '用户'}>
        <SelectableList
          items={reportUsers}
          selectedKey={selectedUser}
          getKey={(item) => item.username}
          renderLabel={(item) => item.username}
          renderExtra={(item) => <Tag bordered={false}>{item.count}</Tag>}
          onSelect={onSelectUser}
          emptyText="请先选择日期"
        />
      </Card>

      <Card size="small" title={selectedUser ? `${selectedUser} 的文档` : '文档'}>
        <Table<ReportFile>
          rowKey={(record) => `${record.job_id}-${record.name}`}
          size="small"
          columns={columns}
          dataSource={reportFiles}
          pagination={false}
          scroll={{ x: 'max-content' }}
          locale={{ emptyText: '请先选择用户' }}
        />
      </Card>
    </div>
  )
}
