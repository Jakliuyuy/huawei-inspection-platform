import { App as AntApp, Button, Card, Form, Input, Space, Table } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { useState } from 'react'
import { request } from '../../lib/api'
import { formatTime } from '../../lib/format'
import type { User } from '../../lib/types'

function buildUserColumns(onResetPassword: (user: User) => void): ColumnsType<User> {
  return [
    { title: '用户名', dataIndex: 'username' },
    { title: '角色', dataIndex: 'role_label' },
    { title: '创建时间', render: (_, record) => formatTime(record.created_at) },
    { title: '最后登录', render: (_, record) => formatTime(record.last_login_at) },
    {
      title: '操作',
      render: (_, record) => <Button onClick={() => onResetPassword(record)}>重置密码</Button>,
    },
  ]
}

export function UserManagementSection({
  users,
  announcement,
  onOpenCreateUser,
  onOpenResetPassword,
  onAnnouncementSaved,
}: {
  users: User[]
  announcement: string
  onOpenCreateUser: () => void
  onOpenResetPassword: (user: User) => void
  onAnnouncementSaved: (content: string) => void
}) {
  const { message } = AntApp.useApp()
  const [savingAnnouncement, setSavingAnnouncement] = useState(false)

  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      <Card className="compact-card" extra={<Button onClick={onOpenCreateUser}>新增用户</Button>}>
        <Table<User>
          rowKey="id"
          columns={buildUserColumns(onOpenResetPassword)}
          dataSource={users}
          pagination={false}
          size="middle"
        />
      </Card>
      <Card className="compact-card" title="系统公告">
        <Form
          layout="vertical"
          key={announcement}
          initialValues={{ content: announcement }}
          onFinish={async (values: { content: string }) => {
            setSavingAnnouncement(true)
            try {
              const result = await request<{ ok: boolean; content: string }>('/admin/announcement', {
                method: 'PUT',
                body: JSON.stringify(values),
              })
              onAnnouncementSaved(result.content)
            } catch (error) {
              message.error(error instanceof Error ? error.message : '保存公告失败')
            } finally {
              setSavingAnnouncement(false)
            }
          }}
        >
          <Form.Item name="content" rules={[{ required: true, message: '请输入公告内容' }]}>
            <Input.TextArea rows={5} />
          </Form.Item>
          <Button htmlType="submit" type="primary" loading={savingAnnouncement}>
            保存公告
          </Button>
        </Form>
      </Card>
    </Space>
  )
}
