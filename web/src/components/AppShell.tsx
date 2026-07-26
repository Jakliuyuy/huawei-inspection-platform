import {
  DashboardOutlined,
  DownOutlined,
  LogoutOutlined,
  MenuOutlined,
  SafetyCertificateOutlined,
  UploadOutlined,
} from '@ant-design/icons'
import { Button, Drawer, Dropdown, Grid, Layout, Menu, Tag } from 'antd'
import type { ReactNode } from 'react'
import { useEffect, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'

import { ThemeToggle } from './common'
import { resolveNavKey } from '../lib/job'
import type { User } from '../lib/types'
import styles from './AppShell.module.css'

const SIDER_STORAGE_KEY = 'inspection.sider'

const NAV_ITEMS = [
  { key: '/dashboard', icon: <DashboardOutlined />, label: '任务中心', adminOnly: false },
  { key: '/tasks/new', icon: <UploadOutlined />, label: '新建任务', adminOnly: false },
  { key: '/admin', icon: <SafetyCertificateOutlined />, label: '系统管理', adminOnly: true },
]

export function AppShell({
  user,
  localMode,
  onLogout,
  children,
}: {
  user: User | null
  localMode: boolean
  onLogout: () => Promise<void>
  children: ReactNode
}) {
  const location = useLocation()
  const navigate = useNavigate()
  const screens = Grid.useBreakpoint()
  const isNarrow = !screens.lg
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [collapsed, setCollapsed] = useState(() => {
    try {
      return localStorage.getItem(SIDER_STORAGE_KEY) === '1'
    } catch {
      return false
    }
  })

  useEffect(() => {
    try {
      localStorage.setItem(SIDER_STORAGE_KEY, collapsed ? '1' : '0')
    } catch {
      /* 忽略写入失败 */
    }
  }, [collapsed])

  // 本地模式没有账号体系，管理端直接可用
  const isAdmin = localMode || !!user?.is_admin
  const items = NAV_ITEMS.filter((item) => !item.adminOnly || isAdmin).map(({ key, icon, label }) => ({
    key,
    icon,
    label,
  }))

  const go = (key: string) => {
    navigate(key)
    setDrawerOpen(false)
  }

  const nav = (
    <Menu
      mode="inline"
      selectedKeys={[resolveNavKey(location.pathname)]}
      items={items}
      onClick={({ key }) => go(key)}
      style={{ borderInlineEnd: 'none' }}
    />
  )

  return (
    <Layout className={styles.layout}>
      {!isNarrow && (
        <Layout.Sider
          className={styles.sider}
          theme="light"
          width={224}
          collapsedWidth={56}
          collapsible
          collapsed={collapsed}
          onCollapse={setCollapsed}
        >
          <div className={styles.brand}>
            <span className={styles.brandMark} />
            {!collapsed && <span className={styles.brandName}>巡检报告平台</span>}
          </div>
          <div className={styles.nav}>{nav}</div>
          {!collapsed && (
            <div className={styles.siderFooter}>
              <span>{localMode ? '本地模式' : (user?.role_label ?? '')}</span>
            </div>
          )}
        </Layout.Sider>
      )}

      <Drawer
        placement="left"
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        width={240}
        styles={{ body: { padding: 0 } }}
        title="巡检报告平台"
      >
        {nav}
      </Drawer>

      <Layout>
        <Layout.Header className={styles.header}>
          {isNarrow ? (
            <Button
              type="text"
              icon={<MenuOutlined />}
              onClick={() => setDrawerOpen(true)}
              aria-label="打开导航"
              className={styles.mobileTrigger}
            />
          ) : (
            <span />
          )}
          <div className={styles.headerRight}>
            <ThemeToggle />
            {localMode ? (
              <Tag bordered={false}>本地模式</Tag>
            ) : (
              user && (
                <Dropdown
                  menu={{
                    items: [
                      { key: 'role', label: user.role_label, disabled: true },
                      { type: 'divider' },
                      { key: 'logout', icon: <LogoutOutlined />, label: '退出登录' },
                    ],
                    onClick: ({ key }) => {
                      if (key === 'logout') void onLogout()
                    },
                  }}
                >
                  <button type="button" className={styles.userButton}>
                    {user.username}
                    <DownOutlined style={{ fontSize: 10 }} />
                  </button>
                </Dropdown>
              )
            )}
          </div>
        </Layout.Header>
        <Layout.Content>
          <div className={styles.content}>{children}</div>
        </Layout.Content>
      </Layout>
    </Layout>
  )
}
