import { App as AntApp, ConfigProvider, Result, Spin } from 'antd'
import type { JSX } from 'react'
import { Suspense, lazy, useEffect, useState } from 'react'
import { BrowserRouter, Navigate, Route, Routes, useNavigate } from 'react-router-dom'
import { request } from './lib/api'
import type { User } from './lib/types'

const AppShell = lazy(async () => import('./components/AppShell').then((module) => ({ default: module.AppShell })))
const AdminPage = lazy(async () => import('./pages/AdminPage').then((module) => ({ default: module.AdminPage })))
const DashboardPage = lazy(async () =>
  import('./pages/DashboardPage').then((module) => ({ default: module.DashboardPage })),
)
const LoginPage = lazy(async () => import('./pages/LoginPage').then((module) => ({ default: module.LoginPage })))
const NewTaskPage = lazy(async () => import('./pages/NewTaskPage').then((module) => ({ default: module.NewTaskPage })))
const TaskDetailPage = lazy(async () =>
  import('./pages/TaskDetailPage').then((module) => ({ default: module.TaskDetailPage })),
)

function RouteLoading(): JSX.Element {
  return (
    <div className="route-loading">
      <Spin size="large" />
    </div>
  )
}

function ProtectedRoute({ user, children }: { user: User | null; children: JSX.Element }): JSX.Element {
  if (!user) {
    return <Navigate to="/login" replace />
  }
  return children
}

function AdminRoute({ user, children }: { user: User | null; children: JSX.Element }): JSX.Element {
  if (!user) return <Navigate to="/login" replace />
  if (!user.is_admin) return <Result status="403" title="无权限访问管理后台" />
  return children
}

function RouterApp(): JSX.Element {
  const [user, setUser] = useState<User | null>(null)
  const [booting, setBooting] = useState(true)
  const { message } = AntApp.useApp()
  const navigate = useNavigate()

  useEffect(() => {
    void request<User>('/auth/me')
      .then((data) => setUser(data))
      .catch(() => setUser(null))
      .finally(() => setBooting(false))
  }, [])

  const logout = async () => {
    try {
      await request<{ ok: boolean }>('/auth/logout', { method: 'POST' })
    } finally {
      setUser(null)
      navigate('/login', { replace: true })
      message.success('已退出登录')
    }
  }

  if (booting) {
    return (
      <div className="boot-screen">
        <Spin size="large" />
      </div>
    )
  }

  return (
    <Suspense fallback={<RouteLoading />}>
      <Routes>
        <Route path="/" element={<Navigate to="/login" replace />} />
        <Route path="/login" element={<LoginPage onLogin={setUser} user={user} />} />
        <Route
          path="/dashboard"
          element={
            <ProtectedRoute user={user}>
              <AppShell user={user!} onLogout={logout}>
                <DashboardPage user={user!} />
              </AppShell>
            </ProtectedRoute>
          }
        />
        <Route
          path="/tasks/new"
          element={
            <ProtectedRoute user={user}>
              <AppShell user={user!} onLogout={logout}>
                <NewTaskPage />
              </AppShell>
            </ProtectedRoute>
          }
        />
        <Route
          path="/tasks/:jobId"
          element={
            <ProtectedRoute user={user}>
              <AppShell user={user!} onLogout={logout}>
                <TaskDetailPage />
              </AppShell>
            </ProtectedRoute>
          }
        />
        <Route
          path="/admin"
          element={
            <AdminRoute user={user}>
              <AppShell user={user!} onLogout={logout}>
                <AdminPage />
              </AppShell>
            </AdminRoute>
          }
        />
        <Route path="*" element={<Result status="404" title="页面不存在" />} />
      </Routes>
    </Suspense>
  )
}

export default function App(): JSX.Element {
  return (
    <ConfigProvider
      theme={{
        token: {
          colorPrimary: '#0f766e',
          borderRadius: 14,
          colorBgBase: '#f3f6fb',
          fontFamily: '"PingFang SC","Noto Sans SC","Microsoft YaHei",sans-serif',
        },
      }}
    >
      <AntApp>
        <BrowserRouter basename="/app">
          <RouterApp />
        </BrowserRouter>
      </AntApp>
    </ConfigProvider>
  )
}
