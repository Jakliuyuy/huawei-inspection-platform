import { Card, Table, Tag, Tooltip } from 'antd'
import type { ColumnsType } from 'antd/es/table'

import { MonoText, TimeText } from '../common'
import type { AuditPage, AuditRecord } from '../../lib/types'

const columns: ColumnsType<AuditRecord> = [
  { title: '时间', dataIndex: 'created_at', width: 165, render: (v: string) => <TimeText value={v} /> },
  { title: '用户', dataIndex: 'username', width: 120 },
  {
    title: '动作',
    dataIndex: 'action',
    width: 140,
    render: (v: string) => <Tag bordered={false}>{v}</Tag>,
  },
  { title: 'IP', dataIndex: 'ip_address', width: 130, render: (v: string) => <MonoText>{v || '—'}</MonoText> },
  {
    title: '详情',
    dataIndex: 'detail',
    ellipsis: { showTitle: false },
    render: (v: string) => (
      <Tooltip title={v} placement="topLeft">
        {v}
      </Tooltip>
    ),
  },
]

export function AuditManagementSection({
  auditPage,
  loading,
  onPageChange,
}: {
  auditPage: AuditPage | null
  loading: boolean
  onPageChange: (page: number) => void | Promise<void>
}) {
  return (
    <Card size="small">
      <Table<AuditRecord>
        rowKey="id"
        size="small"
        dataSource={auditPage?.items || []}
        loading={loading}
        columns={columns}
        sticky
        scroll={{ x: 'max-content' }}
        pagination={{
          current: auditPage?.page,
          pageSize: auditPage?.page_size,
          total: auditPage?.total,
          showSizeChanger: false,
          onChange: (page) => {
            void onPageChange(page)
          },
        }}
      />
    </Card>
  )
}
