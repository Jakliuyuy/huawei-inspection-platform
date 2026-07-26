import { FileWordOutlined, MailOutlined, TableOutlined, UploadOutlined } from '@ant-design/icons'
import { App as AntApp, Button, Form, Input } from 'antd'
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { request } from '../lib/api'
import type { User } from '../lib/types'
import styles from './LoginPage.module.css'

const CAPABILITIES = [
  { icon: <UploadOutlined />, text: '支持 ZIP 压缩包与整个日志目录上传' },
  { icon: <TableOutlined />, text: '上传后按系统统计设备数，可只生成需要的部分' },
  { icon: <FileWordOutlined />, text: '输出标准 Word 巡检报告并打包下载' },
  { icon: <MailOutlined />, text: '按系统白名单分发邮件，收件人由服务端校验' },
]

export function LoginPage({ onLogin, user }: { onLogin: (user: User) => void; user: User | null }) {
  const { message } = AntApp.useApp()
  const navigate = useNavigate()
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (user) navigate('/dashboard', { replace: true })
  }, [user, navigate])

  const handleFinish = async (values: { username: string; password: string }) => {
    setLoading(true)
    try {
      const result = await request<{ ok: boolean; user: User }>('/auth/login', {
        method: 'POST',
        body: JSON.stringify(values),
      })
      onLogin(result.user)
      message.success('登录成功')
      navigate('/dashboard', { replace: true })
    } catch (error) {
      // 登录接口自身的 401 不触发全局登出，这里直接提示
      message.error(error instanceof Error ? error.message : '登录失败')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className={styles.shell}>
      <section className={styles.hero}>
        <div className={styles.heroBrand}>
          <span className={styles.heroMark} />
          巡检报告平台
        </div>
        <h1 className={styles.heroTitle}>华为设备巡检日志自动化报告生成</h1>
        <ul className={styles.heroList}>
          {CAPABILITIES.map((item) => (
            <li key={item.text} className={styles.heroItem}>
              <span className={styles.heroIcon}>{item.icon}</span>
              {item.text}
            </li>
          ))}
        </ul>
      </section>

      <section className={styles.panel}>
        <div className={styles.panelInner}>
          <h2 className={styles.panelTitle}>登录</h2>
          <p className={styles.panelHint}>使用账号进入任务中心</p>
          <Form layout="vertical" onFinish={handleFinish} requiredMark={false}>
            <Form.Item name="username" label="用户名" rules={[{ required: true, message: '请输入用户名' }]}>
              <Input size="large" autoComplete="username" autoFocus />
            </Form.Item>
            <Form.Item name="password" label="密码" rules={[{ required: true, message: '请输入密码' }]}>
              <Input.Password size="large" autoComplete="current-password" />
            </Form.Item>
            <Button type="primary" size="large" htmlType="submit" loading={loading} block>
              登录
            </Button>
          </Form>
          <div className={styles.panelFooter}>Huawei Inspection Platform</div>
        </div>
      </section>
    </div>
  )
}
