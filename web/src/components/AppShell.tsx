import { DashboardOutlined, LogoutOutlined, SafetyCertificateOutlined, UploadOutlined } from '@ant-design/icons'
import { Button, Layout, Tag, Typography } from 'antd'
import type { ReactNode } from 'react'
import { useMemo } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import type { User } from '../lib/types'

export function AppShell({
  user,
  onLogout,
  children,
}: {
  user: User
  onLogout: () => Promise<void>
  children: ReactNode
}) {
  const navigate = useNavigate()
  const location = useLocation()

  const menu = useMemo(
    () => [
      { key: '/dashboard', label: '任务中心', icon: <DashboardOutlined /> },
      { key: '/tasks/new', label: '新建任务', icon: <UploadOutlined /> },
      ...(user.is_admin ? [{ key: '/admin', label: '系统管理', icon: <SafetyCertificateOutlined /> }] : []),
    ],
    [user.is_admin],
  )

  const title = location.pathname.startsWith('/dashboard')
    ? '任务中心'
    : location.pathname.startsWith('/tasks/new')
      ? '新建任务'
      : location.pathname.startsWith('/tasks/')
        ? '任务详情'
        : '系统管理'

  return (
    <Layout className="app-layout">
      <Layout.Sider width={232} theme="light" className="app-sider">
        <div className="brand-block">
          <span className="brand-kicker">Inspection Cloud</span>
          <strong>华为巡检云平台</strong>
          <span>{user.username}</span>
        </div>
        <div className="nav-list">
          {menu.map((item) => (
            <button
              key={item.key}
              type="button"
              className={`nav-item${location.pathname.startsWith(item.key) ? ' active' : ''}`}
              onClick={() => navigate(item.key)}
            >
              {item.icon}
              <span>{item.label}</span>
            </button>
          ))}
        </div>
        <Button icon={<LogoutOutlined />} className="logout-btn" onClick={() => void onLogout()}>
          退出登录
        </Button>
      </Layout.Sider>
      <Layout>
        <Layout.Header className="app-header">
          <div>
            <Typography.Title level={4} style={{ margin: 0 }}>
              {title}
            </Typography.Title>
            <Typography.Text type="secondary">{user.is_admin ? '管理员视图' : '用户视图'}</Typography.Text>
          </div>
          <Tag color="geekblue">{user.role_label}</Tag>
        </Layout.Header>
        <Layout.Content className="app-content">{children}</Layout.Content>
      </Layout>
    </Layout>
  )
}
