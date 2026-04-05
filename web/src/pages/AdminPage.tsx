import { App as AntApp, Spin, Tabs } from 'antd'
import { useState } from 'react'
import { AuditManagementSection } from '../components/admin/AuditManagementSection'
import { CreateUserModal } from '../components/admin/CreateUserModal'
import { JobManagementSection } from '../components/admin/JobManagementSection'
import { ReportManagementSection } from '../components/admin/ReportManagementSection'
import { ResetPasswordModal } from '../components/admin/ResetPasswordModal'
import { UserManagementSection } from '../components/admin/UserManagementSection'
import { useAdminPageData } from '../hooks/useAdminPageData'
import { request } from '../lib/api'
import type { User } from '../lib/types'

export function AdminPage() {
  const [activeTab, setActiveTab] = useState<'users' | 'jobs' | 'reports' | 'audits'>('users')
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

  const deleteJob = async (jobId: string) => {
    try {
      await request<{ ok: boolean }>(`/admin/jobs/${jobId}`, { method: 'DELETE' })
      message.success('任务已删除')
      await loadJobsSection()
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

  if (loading) return <Spin size="large" />

  return (
    <>
      <Tabs
        defaultActiveKey="users"
        activeKey={activeTab}
        onChange={(key) => setActiveTab(key as 'users' | 'jobs' | 'reports' | 'audits')}
        items={[
          {
            key: 'users',
            label: '用户管理',
            children: (
              <UserManagementSection
                users={users}
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
            children: <AuditManagementSection auditPage={auditPage} onPageChange={loadAuditsSection} />,
          },
        ]}
      />

      <CreateUserModal
        open={createUserOpen}
        onCancel={() => setCreateUserOpen(false)}
        onSubmit={async (values) => {
          try {
            await request<{ ok: boolean }>('/admin/users', {
              method: 'POST',
              body: JSON.stringify(values),
            })
            setCreateUserOpen(false)
            message.success('用户创建成功')
            await loadUsersSection()
          } catch (error) {
            message.error(error instanceof Error ? error.message : '创建用户失败')
          }
        }}
      />

      <ResetPasswordModal
        open={passwordModal.open}
        user={passwordModal.user}
        onCancel={() => setPasswordModal({ open: false, user: null })}
        onSubmit={async (values) => {
          if (!passwordModal.user) return
          try {
            await request<{ ok: boolean }>(`/admin/users/${passwordModal.user.id}/password`, {
              method: 'PUT',
              body: JSON.stringify(values),
            })
            message.success('密码已重置')
            setPasswordModal({ open: false, user: null })
          } catch (error) {
            message.error(error instanceof Error ? error.message : '重置密码失败')
          }
        }}
      />
    </>
  )
}
