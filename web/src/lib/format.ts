import dayjs from 'dayjs'

export function formatTime(value: string | null | undefined): string {
  if (!value) return '-'
  return dayjs(value).format('YYYY-MM-DD HH:mm:ss')
}

export function statusColor(status: string): 'success' | 'error' | 'processing' {
  if (status === 'completed') return 'success'
  if (status === 'failed') return 'error'
  return 'processing'
}
