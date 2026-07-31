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
  log_batch_id: string | null
  locked_versions: LockedSystemVersion[]
  error_message: string | null
  bundle_available: boolean
  bundle_download_url: string | null
  generated_files: JobFile[]
  timeline: JobTimeline[]
}

export type LockedSystemVersion = {
  batch_id: string
  version_id: number
  version: number
  system_key: string
  display_name: string
  recipients: string[]
}

export type InspectionSystem = {
  id: number
  system_key: string
  display_name: string
  current_version_id: number | null
  version: number | null
  status: string | null
  validation_json: string | null
}

export type InspectionCommand = { command: string; timeout_seconds: number; result_cell: unknown }
export type InspectionDevice = { order: number; name: string; ip: string; driver: 'huawei_vrp' | 'generic_show'; commands: InspectionCommand[]; table_index?: number }
export type InspectionVersion = {
  id: number
  system_id: number
  system_key: string
  display_name: string
  version: number
  status: 'draft' | 'built' | 'validating' | 'validated' | 'published' | 'retired'
  source_mode: string
  config: { system_key: string; display_name: string; template: string; devices: InspectionDevice[]; non_command_rules: unknown[] }
  recipients: string[]
  template_sha256: string | null
  vbs_sha256: string | null
  validation: { valid?: boolean; issues?: string[] }
  is_current: boolean
  created_at: string
  updated_at: string
}

export type AvailableInspectionSystem = { id: number; system_key: string; display_name: string; version_id: number; version: number }
export type LogBatch = {
  id: string
  status: 'collecting' | 'invalid' | 'validated'
  system_version_id: number | null
  system_key: string
  version: number | null
  validation: { valid?: boolean; issues?: string[]; devices?: { name: string; expected_commands: number; actual_commands: number; complete: boolean }[] }
  created_at: string
  updated_at: string
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
