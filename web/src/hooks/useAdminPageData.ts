import { App as AntApp } from 'antd'
import { useEffect, useEffectEvent, useState } from 'react'
import { request } from '../lib/api'
import type { Announcement, AuditPage, Job, JobPage, JobStats, ReportDate, ReportFile, ReportUser, User } from '../lib/types'

export type AdminTabKey = 'users' | 'jobs' | 'reports' | 'audits'

export function useAdminPageData(activeTab: AdminTabKey) {
  const [users, setUsers] = useState<User[]>([])
  const [jobs, setJobs] = useState<Job[]>([])
  const [jobPage, setJobPage] = useState(1)
  const [jobTotal, setJobTotal] = useState(0)
  const [jobStats, setJobStats] = useState<JobStats>({ total: 0, active: 0, completed: 0, failed: 0 })
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

  const loadJobsSection = async (page = 1) => {
    try {
      const data = await request<JobPage>(`/admin/jobs?page=${page}&page_size=20`)
      setJobs(data.items)
      setJobPage(data.page)
      setJobTotal(data.total)
      setJobStats(data.stats)
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

  const loadActiveTab = useEffectEvent(() => {
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
  })

  const loadUsersForDate = useEffectEvent((date: string) => {
    void loadReportUsers(date)
  })

  const loadFilesForSelection = useEffectEvent((date: string, user: string) => {
    void loadReportFiles(date, user)
  })

  useEffect(() => {
    setLoading(true)
    loadActiveTab()
  }, [activeTab])

  useEffect(() => {
    if (!selectedDate) {
      setReportUsers([])
      setReportFiles([])
      setSelectedUser(null)
      return
    }
    loadUsersForDate(selectedDate)
  }, [selectedDate])

  useEffect(() => {
    if (!selectedDate || !selectedUser) {
      setReportFiles([])
      return
    }
    loadFilesForSelection(selectedDate, selectedUser)
  }, [selectedDate, selectedUser])

  return {
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
  }
}
