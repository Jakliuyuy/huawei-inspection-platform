import { Button, Form, Input, Modal, Typography } from 'antd'
import type { User } from '../../lib/types'

export function ResetPasswordModal({
  open,
  user,
  onCancel,
  onSubmit,
}: {
  open: boolean
  user: User | null
  onCancel: () => void
  onSubmit: (values: { new_password: string }) => void | Promise<void>
}) {
  return (
    <Modal title="重置密码" open={open} footer={null} onCancel={onCancel} destroyOnClose>
      <Typography.Paragraph>
        为用户 <strong>{user?.username}</strong> 设置新密码
      </Typography.Paragraph>
      <Form layout="vertical" onFinish={(values) => void onSubmit(values)}>
        <Form.Item name="new_password" label="新密码" rules={[{ required: true, message: '请输入新密码' }]}>
          <Input.Password />
        </Form.Item>
        <Button htmlType="submit" type="primary" block>
          确认重置
        </Button>
      </Form>
    </Modal>
  )
}
