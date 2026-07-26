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

export type EmailSuggestion = { name: string; recipients: string[] }

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
  report_date: string | null
  /** 空数组表示全部系统 */
  selected_systems: string[]
  error_message: string | null
  bundle_available: boolean
  bundle_download_url: string | null
  generated_files: JobFile[]
  timeline: JobTimeline[]
}

export type SystemInfo = {
  key: string
  display_name: string
  template: string
  host_count: number
  /** 含 {date} 占位符，由前端替换；命名规则的真相在后端 */
  output_name_template: string
}

export type SystemStat = {
  key: string
  display_name: string
  expected: number
  actual: number
  missing: number
  has_logs: boolean
  output_name_template: string
}

export type UploadPreview = {
  upload_id: string
  log_root_label: string
  detected: boolean
  log_file_count: number
  suggested_report_date: string
  systems: SystemStat[]
}

export type JobStats = {
  total: number
  active: number
  completed: number
  failed: number
}

export type JobPage = {
  items: Job[]
  page: number
  page_size: number
  total: number
  total_pages: number
  stats: JobStats
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
