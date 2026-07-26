import { App as AntApp, Result, Spin } from 'antd'
import type { JSX } from 'react'
import { Suspense, lazy, useCallback, useEffect, useRef, useState } from 'react'
import { BrowserRouter, Navigate, Route, Routes, useNavigate } from 'react-router-dom'

import { request, setUnauthorizedHandler } from './lib/api'
import type { User } from './lib/types'
import { ThemeProvider } from './theme/ThemeProvider'
import './styles/global.css'

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

/** 本地模式下后端在 /auth/me 上带回 auth_mode=local，前端据此隐藏登录/登出 */
type MeResponse = User & { auth_mode?: 'local' | 'session' }

function CenteredSpin(): JSX.Element {
  return (
    <div style={{ display: 'grid', placeItems: 'center', minHeight: '60vh' }}>
      <Spin size="large" />
    </div>
  )
}

function RouterApp(): JSX.Element {
  const [user, setUser] = useState<User | null>(null)
  const [localMode, setLocalMode] = useState(false)
  const [booting, setBooting] = useState(true)
  const { message } = AntApp.useApp()
  const navigate = useNavigate()
  const expiredNotified = useRef(false)

  useEffect(() => {
    void request<MeResponse>('/auth/me')
      .then((data) => {
        setUser(data)
        setLocalMode(data.auth_mode === 'local')
      })
      .catch(() => setUser(null))
      .finally(() => setBooting(false))
  }, [])

  useEffect(() => {
    setUnauthorizedHandler(() => {
      // 只提示一次，否则两个页面的轮询会连环弹窗
      if (expiredNotified.current) return
      expiredNotified.current = true
      setUser(null)
      navigate('/login', { replace: true })
      message.warning('登录状态已失效，请重新登录')
    })
    return () => setUnauthorizedHandler(null)
  }, [message, navigate])

  const handleLogin = (nextUser: User) => {
    expiredNotified.current = false
    setUser(nextUser)
  }

  const logout = useCallback(async () => {
    try {
      await request<{ ok: boolean }>('/auth/logout', { method: 'POST' })
    } finally {
      setUser(null)
      navigate('/login', { replace: true })
      message.success('已退出登录')
    }
  }, [message, navigate])

  if (booting) return <CenteredSpin />

  const authed = localMode || !!user
  const isAdmin = localMode || !!user?.is_admin

  const shell = (children: JSX.Element) => (
    <AppShell user={user} localMode={localMode} onLogout={logout}>
      {children}
    </AppShell>
  )

  const guard = (children: JSX.Element, adminOnly = false) => {
    if (!authed) return <Navigate to="/login" replace />
    if (adminOnly && !isAdmin) return <Result status="403" title="无权限访问管理后台" />
    return shell(children)
  }

  return (
    <Suspense fallback={<CenteredSpin />}>
      <Routes>
        <Route path="/" element={<Navigate to={authed ? '/dashboard' : '/login'} replace />} />
        <Route
          path="/login"
          element={
            // 本地模式没有登录页，老书签直接落到看板
            localMode ? <Navigate to="/dashboard" replace /> : <LoginPage onLogin={handleLogin} user={user} />
          }
        />
        <Route path="/dashboard" element={guard(<DashboardPage user={user} localMode={localMode} />)} />
        <Route path="/tasks/new" element={guard(<NewTaskPage />)} />
        <Route path="/tasks/:jobId" element={guard(<TaskDetailPage />)} />
        <Route path="/admin" element={guard(<AdminPage localMode={localMode} />, true)} />
        <Route path="*" element={<Result status="404" title="页面不存在" />} />
      </Routes>
    </Suspense>
  )
}

export default function App(): JSX.Element {
  return (
    <ThemeProvider>
      {/* base 与 basename 单一来源，改 vite base 时不会失配 */}
      <BrowserRouter basename={import.meta.env.BASE_URL.replace(/\/$/, '') || '/'}>
        <RouterApp />
      </BrowserRouter>
    </ThemeProvider>
  )
}
