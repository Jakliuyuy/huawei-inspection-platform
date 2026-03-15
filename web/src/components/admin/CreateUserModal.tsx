import { Button, Form, Input, Modal, Segmented } from 'antd'

export function CreateUserModal({
  open,
  onCancel,
  onSubmit,
}: {
  open: boolean
  onCancel: () => void
  onSubmit: (values: { username: string; password: string; is_admin: boolean }) => void | Promise<void>
}) {
  return (
    <Modal title="新增用户" open={open} footer={null} onCancel={onCancel} destroyOnClose>
      <Form layout="vertical" onFinish={(values) => void onSubmit(values)}>
        <Form.Item name="username" label="用户名" rules={[{ required: true, message: '请输入用户名' }]}>
          <Input />
        </Form.Item>
        <Form.Item name="password" label="密码" rules={[{ required: true, message: '请输入密码' }]}>
          <Input.Password />
        </Form.Item>
        <Form.Item name="is_admin" label="角色" initialValue={false}>
          <Segmented
            options={[
              { label: '普通用户', value: false },
              { label: '管理员', value: true },
            ]}
          />
        </Form.Item>
        <Button htmlType="submit" type="primary" block>
          创建用户
        </Button>
      </Form>
    </Modal>
  )
}
