import { App as AntApp, Tabs } from 'antd'
import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'

import { AuditManagementSection } from '../components/admin/AuditManagementSection'
import { InspectionSystemsSection } from '../components/admin/InspectionSystemsSection'
import { CreateUserModal } from '../components/admin/CreateUserModal'
import { JobManagementSection } from '../components/admin/JobManagementSection'
import { ReportManagementSection } from '../components/admin/ReportManagementSection'
import { ResetPasswordModal } from '../components/admin/ResetPasswordModal'
import { UserManagementSection } from '../components/admin/UserManagementSection'
import { PageHeader } from '../components/common'
import { useAdminPageData, type AdminTabKey } from '../hooks/useAdminPageData'
import { request } from '../lib/api'
import type { User } from '../lib/types'

const TAB_KEYS: AdminTabKey[] = ['systems', 'users', 'jobs', 'reports', 'audits']

export function AdminPage({ localMode }: { localMode: boolean }) {
  const [params, setParams] = useSearchParams()
  const requested = params.get('tab') as AdminTabKey | null
  // 本地模式没有多用户体系，用户管理页没有意义
  const available = localMode ? TAB_KEYS.filter((key) => key !== 'users') : TAB_KEYS
  const initial = requested && available.includes(requested) ? requested : available[0]

  const [activeTab, setActiveTab] = useState<AdminTabKey>(initial)
  const [createUserOpen, setCreateUserOpen] = useState(false)
  const [passwordModal, setPasswordModal] = useState<{ open: boolean; user: User | null }>({ open: false, user: null })
  const { message } = AntApp.useApp()
  const {
    users,
    jobs,
    jobPage,
    jobTotal,
    jobStats,
    auditPage,
    announcement,
    reportDates,
    reportUsers,
    reportFiles,
    selectedDate,
    selectedUser,
    loading,
    setAnnouncement,
    setSelectedDate,
    setSelectedUser,
    loadUsersSection,
    loadJobsSection,
    loadAuditsSection,
    refreshReports,
  } = useAdminPageData(activeTab)

  const changeTab = (key: string) => {
    setActiveTab(key as AdminTabKey)
    setParams({ tab: key }, { replace: true })
  }

  const deleteJob = async (jobId: string) => {
    try {
      await request<{ ok: boolean }>(`/admin/jobs/${jobId}`, { method: 'DELETE' })
      message.success('任务已删除')
      await loadJobsSection(jobPage)
    } catch (error) {
      message.error(error instanceof Error ? error.message : '删除任务失败')
    }
  }

  const deleteReport = async (jobId: string, fileName: string) => {
    try {
      await request<{ ok: boolean }>(`/admin/reports/${jobId}/${encodeURIComponent(fileName)}`, { method: 'DELETE' })
      message.success('报告已删除')
      await refreshReports()
    } catch (error) {
      message.error(error instanceof Error ? error.message : '删除报告失败')
    }
  }

  const allItems = [
    {
      key: 'systems',
      label: '巡检系统',
      children: <InspectionSystemsSection />,
    },
    {
      key: 'users',
      label: '用户管理',
      children: (
        <UserManagementSection
          users={users}
          loading={loading.users}
          announcement={announcement}
          onOpenCreateUser={() => setCreateUserOpen(true)}
          onOpenResetPassword={(user) => setPasswordModal({ open: true, user })}
          onAnnouncementSaved={(content) => {
            setAnnouncement(content)
            message.success('公告已更新')
          }}
        />
      ),
    },
    {
      key: 'jobs',
      label: '任务管理',
      children: (
        <JobManagementSection
          jobs={jobs}
          loading={loading.jobs}
          page={jobPage}
          total={jobTotal}
          stats={jobStats}
          onPageChange={(nextPage) => void loadJobsSection(nextPage)}
          onDeleteJob={deleteJob}
        />
      ),
    },
    {
      key: 'reports',
      label: 'Word 报告',
      children: (
        <ReportManagementSection
          loading={loading.reports}
          reportDates={reportDates}
          reportUsers={reportUsers}
          reportFiles={reportFiles}
          selectedDate={selectedDate}
          selectedUser={selectedUser}
          onSelectDate={setSelectedDate}
          onSelectUser={setSelectedUser}
          onDeleteReport={deleteReport}
        />
      ),
    },
    {
      key: 'audits',
      label: '审计日志',
      children: (
        <AuditManagementSection
          auditPage={auditPage}
          loading={loading.audits}
          onPageChange={(nextPage) => void loadAuditsSection(nextPage)}
        />
      ),
    },
  ]

  return (
    <>
      <PageHeader title="系统管理" description="用户、任务、报告归档与审计" />
      <Tabs
        activeKey={activeTab}
        onChange={changeTab}
        items={allItems.filter((item) => available.includes(item.key as AdminTabKey))}
      />
      <CreateUserModal
        open={createUserOpen}
        onCancel={() => setCreateUserOpen(false)}
        onSubmit={async (values) => {
          await request<{ ok: boolean }>('/admin/users', { method: 'POST', body: JSON.stringify(values) })
          setCreateUserOpen(false)
          message.success('用户创建成功')
          await loadUsersSection()
        }}
      />
      <ResetPasswordModal
        open={passwordModal.open}
        user={passwordModal.user}
        onCancel={() => setPasswordModal({ open: false, user: null })}
        onSubmit={async (values) => {
          if (!passwordModal.user) return
          await request<{ ok: boolean }>(`/admin/users/${passwordModal.user.id}/password`, {
            method: 'PUT',
            body: JSON.stringify(values),
          })
          message.success('密码已重置')
          setPasswordModal({ open: false, user: null })
        }}
      />
    </>
  )
}
