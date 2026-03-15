import { App as AntApp } from 'antd'
import { useEffect, useState } from 'react'
import { request } from '../lib/api'
import type { Announcement, AuditPage, Job, ReportDate, ReportFile, ReportUser, User } from '../lib/types'

export type AdminTabKey = 'users' | 'jobs' | 'reports' | 'audits'

export function useAdminPageData(activeTab: AdminTabKey) {
  const [users, setUsers] = useState<User[]>([])
  const [jobs, setJobs] = useState<Job[]>([])
  const [auditPage, setAuditPage] = useState<AuditPage | null>(null)
  const [announcement, setAnnouncement] = useState('')
  const [reportDates, setReportDates] = useState<ReportDate[]>([])
  const [reportUsers, setReportUsers] = useState<ReportUser[]>([])
  const [reportFiles, setReportFiles] = useState<ReportFile[]>([])
  const [selectedDate, setSelectedDate] = useState<string | null>(null)
  const [selectedUser, setSelectedUser] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const { message } = AntApp.useApp()

  const loadUsersSection = async () => {
    try {
      const [usersData, announcementData] = await Promise.all([
        request<User[]>('/admin/users'),
        request<Announcement>('/announcements'),
      ])
      setUsers(usersData)
      setAnnouncement(announcementData.content)
    } catch (error) {
      message.error(error instanceof Error ? error.message : '加载用户数据失败')
    } finally {
      setLoading(false)
    }
  }

  const loadJobsSection = async () => {
    try {
      setJobs(await request<Job[]>('/admin/jobs'))
    } catch (error) {
      message.error(error instanceof Error ? error.message : '加载任务数据失败')
    } finally {
      setLoading(false)
    }
  }

  const loadReportsSection = async () => {
    try {
      setReportDates(await request<ReportDate[]>('/admin/reports/dates'))
    } catch (error) {
      message.error(error instanceof Error ? error.message : '加载报告数据失败')
    } finally {
      setLoading(false)
    }
  }

  const loadReportUsers = async (date: string) => {
    try {
      const data = await request<ReportUser[]>(`/admin/reports/users?date=${encodeURIComponent(date)}`)
      setReportUsers(data)
      setReportFiles([])
      setSelectedUser(null)
    } catch (error) {
      message.error(error instanceof Error ? error.message : '加载报告用户失败')
    }
  }

  const loadReportFiles = async (date: string, user: string) => {
    try {
      setReportFiles(
        await request<ReportFile[]>(
          `/admin/reports/files?date=${encodeURIComponent(date)}&user=${encodeURIComponent(user)}`,
        ),
      )
    } catch (error) {
      message.error(error instanceof Error ? error.message : '加载报告文件失败')
    }
  }

  const loadAuditsSection = async (page = 1) => {
    try {
      setAuditPage(await request<AuditPage>(`/admin/audits?page=${page}&page_size=20`))
    } catch (error) {
      message.error(error instanceof Error ? error.message : '加载审计日志失败')
    } finally {
      setLoading(false)
    }
  }

  const refreshReports = async () => {
    await loadReportsSection()
    if (selectedDate) {
      await loadReportUsers(selectedDate)
    }
    if (selectedDate && selectedUser) {
      await loadReportFiles(selectedDate, selectedUser)
    }
  }

  useEffect(() => {
    setLoading(true)
    if (activeTab === 'users') {
      void loadUsersSection()
      return
    }
    if (activeTab === 'jobs') {
      void loadJobsSection()
      return
    }
    if (activeTab === 'reports') {
      void loadReportsSection()
      return
    }
    void loadAuditsSection()
  }, [activeTab])

  useEffect(() => {
    if (!selectedDate) {
      setReportUsers([])
      setReportFiles([])
      setSelectedUser(null)
      return
    }
    void loadReportUsers(selectedDate)
  }, [selectedDate])

  useEffect(() => {
    if (!selectedDate || !selectedUser) {
      setReportFiles([])
      return
    }
    void loadReportFiles(selectedDate, selectedUser)
  }, [selectedDate, selectedUser])

  return {
    users,
    jobs,
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
  }
}
