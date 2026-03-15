import { Card, Table } from 'antd'
import type { AuditPage, AuditRecord } from '../../lib/types'

export function AuditManagementSection({
  auditPage,
  onPageChange,
}: {
  auditPage: AuditPage | null
  onPageChange: (page: number) => void | Promise<void>
}) {
  return (
    <Card className="compact-card">
      <Table<AuditRecord>
        rowKey="id"
        dataSource={auditPage?.items || []}
        size="middle"
        pagination={{
          current: auditPage?.page,
          pageSize: auditPage?.page_size,
          total: auditPage?.total,
          showSizeChanger: false,
          onChange: (page) => {
            void onPageChange(page)
          },
        }}
        columns={[
          { title: '时间', dataIndex: 'created_at' },
          { title: '用户', dataIndex: 'username' },
          { title: '动作', dataIndex: 'action' },
          { title: '详情', dataIndex: 'detail' },
        ]}
      />
    </Card>
  )
}
