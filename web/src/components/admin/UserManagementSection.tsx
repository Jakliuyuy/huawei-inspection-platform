import { App as AntApp, Button, Card, Form, Input, Space, Table } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { useState } from 'react'

import { TimeText } from '../common'
import { request } from '../../lib/api'
import type { User } from '../../lib/types'

function buildUserColumns(onResetPassword: (user: User) => void): ColumnsType<User> {
  return [
    { title: '用户名', dataIndex: 'username', width: 160 },
    { title: '角色', dataIndex: 'role_label', width: 110 },
    { title: '创建时间', width: 165, render: (_, record) => <TimeText value={record.created_at} /> },
    { title: '最后登录', width: 165, render: (_, record) => <TimeText value={record.last_login_at} /> },
    {
      title: '操作',
      render: (_, record) => (
        <Button type="link" size="small" onClick={() => onResetPassword(record)}>
          重置密码
        </Button>
      ),
    },
  ]
}

export function UserManagementSection({
  users,
  loading,
  announcement,
  onOpenCreateUser,
  onOpenResetPassword,
  onAnnouncementSaved,
}: {
  users: User[]
  loading: boolean
  announcement: string
  onOpenCreateUser: () => void
  onOpenResetPassword: (user: User) => void
  onAnnouncementSaved: (content: string) => void
}) {
  const { message } = AntApp.useApp()
  const [savingAnnouncement, setSavingAnnouncement] = useState(false)

  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      <Card
        size="small"
        title="用户"
        extra={
          <Button type="primary" size="small" onClick={onOpenCreateUser}>
            新增用户
          </Button>
        }
      >
        <Table<User>
          rowKey="id"
          size="small"
          columns={buildUserColumns(onOpenResetPassword)}
          dataSource={users}
          loading={loading}
          pagination={false}
          scroll={{ x: 'max-content' }}
        />
      </Card>

      <Card size="small" title="系统公告">
        <Form
          layout="vertical"
          // announcement 变化时强制重挂载，让 initialValues 取到最新值
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
              // antd Form 不处理 onFinish 的 rejection，这里必须自己兜住
              message.error(error instanceof Error ? error.message : '保存公告失败')
            } finally {
              setSavingAnnouncement(false)
            }
          }}
        >
          <Form.Item name="content" rules={[{ required: true, message: '请输入公告内容' }]}>
            <Input.TextArea rows={4} />
          </Form.Item>
          <Button htmlType="submit" type="primary" loading={savingAnnouncement}>
            保存公告
          </Button>
        </Form>
      </Card>
    </Space>
  )
}
