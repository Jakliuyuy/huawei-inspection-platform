import { Button, Form, Input, Modal, Typography } from 'antd'
import { useState } from 'react'
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
  const [submitting, setSubmitting] = useState(false)

  const handleFinish = async (values: { new_password: string }) => {
    setSubmitting(true)
    try {
      await onSubmit(values)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Modal title="重置密码" open={open} footer={null} onCancel={onCancel} destroyOnHidden>
      <Typography.Paragraph>
        为用户 <strong>{user?.username}</strong> 设置新密码
      </Typography.Paragraph>
      <Form layout="vertical" onFinish={(values) => void handleFinish(values)}>
        <Form.Item name="new_password" label="新密码" rules={[
            { required: true, message: '请输入新密码' },
            { min: 8, message: '密码长度不能少于 8 位' },
          ]}>
          <Input.Password />
        </Form.Item>
        <Button htmlType="submit" type="primary" block loading={submitting}>
          确认重置
        </Button>
      </Form>
    </Modal>
  )
}
