export type User = {
  id: number
  username: string
  is_admin: boolean
  role_label: string
  created_at: string
  last_login_at: string | null
}

export type Announcement = { content: string }

export type JobFile = { name: string; download_url: string }

export type JobTimeline = {
  step: number
  title: string
  description: string
  active: boolean
}

export type Job = {
  id: string
  status: string
  status_label: string
  progress: number
  status_detail: string
  created_at: string
  started_at: string | null
  finished_at: string | null
  username: string
  log_root: string | null
  error_message: string | null
  bundle_available: boolean
  bundle_download_url: string | null
  generated_files: JobFile[]
  timeline: JobTimeline[]
}

export type AuditRecord = {
  id: number
  created_at: string
  username: string
  action: string
  detail: string
  ip_address: string
}

export type AuditPage = {
  items: AuditRecord[]
  page: number
  page_size: number
  total: number
  total_pages: number
}

export type ReportDate = { report_date: string; count: number }

export type ReportUser = { username: string; count: number }

export type ReportFile = {
  job_id: string
  username: string
  report_date: string
  name: string
  size: string
  modified_at: string
  download_url: string
}
