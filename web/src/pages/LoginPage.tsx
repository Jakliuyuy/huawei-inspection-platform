import { Card, Form, Input, Button, Space, Statistic, Typography, App as AntApp } from 'antd'
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { request } from '../lib/api'
import type { User } from '../lib/types'

export function LoginPage({ onLogin, user }: { onLogin: (user: User) => void; user: User | null }) {
  const [loading, setLoading] = useState(false)
  const { message } = AntApp.useApp()
  const navigate = useNavigate()

  useEffect(() => {
    if (user) navigate('/dashboard', { replace: true })
  }, [navigate, user])

  const handleFinish = async (values: { username: string; password: string }) => {
    setLoading(true)
    try {
      const data = await request<{ ok: boolean; user: User }>('/auth/login', {
        method: 'POST',
        body: JSON.stringify(values),
      })
      onLogin(data.user)
      navigate('/dashboard', { replace: true })
      message.success('登录成功')
    } catch (error) {
      message.error(error instanceof Error ? error.message : '登录失败')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="auth-shell">
      <div className="auth-hero">
        <span className="auth-kicker">Huawei Inspection Cloud</span>
        <h1>巡检日志上云，任务与报告统一管理</h1>
        <p>支持 ZIP、文件夹上传，自动生成 Word 巡检文档，管理员可集中查看用户、任务、审计与报告。</p>
        <div className="auth-stats">
          <Card>
            <Statistic title="上传支持" value="ZIP / 文件夹" />
          </Card>
          <Card>
            <Statistic title="输出格式" value="Word" />
          </Card>
          <Card>
            <Statistic title="运行方式" value="Docker" />
          </Card>
        </div>
      </div>
      <Card className="auth-card" bordered={false}>
        <Space direction="vertical" size={4} style={{ width: '100%' }}>
          <Typography.Title level={3} style={{ margin: 0 }}>
            登录平台
          </Typography.Title>
          <Typography.Text type="secondary">使用账号进入任务中心和系统管理。</Typography.Text>
        </Space>
        <Form layout="vertical" onFinish={handleFinish} style={{ marginTop: 24 }}>
          <Form.Item label="用户名" name="username" rules={[{ required: true, message: '请输入用户名' }]}>
            <Input size="large" placeholder="请输入用户名" />
          </Form.Item>
          <Form.Item label="密码" name="password" rules={[{ required: true, message: '请输入密码' }]}>
            <Input.Password size="large" placeholder="请输入密码" />
          </Form.Item>
          <Button type="primary" htmlType="submit" size="large" block loading={loading}>
            登录平台
          </Button>
        </Form>
      </Card>
    </div>
  )
}
