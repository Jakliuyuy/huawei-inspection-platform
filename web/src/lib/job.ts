import type { Job } from './types'

export const ACTIVE_STATUSES = ['queued', 'running']

export function isActiveStatus(status: string): boolean {
  return ACTIVE_STATUSES.includes(status)
}

/** 处理中的任务不可删除。看板与管理端共用，避免两处字面量各自漂移。 */
export function canDeleteJob(job: Pick<Job, 'status'>): boolean {
  return !isActiveStatus(job.status)
}

export function resolveNavKey(pathname: string): string {
  if (pathname.startsWith('/tasks/new')) return '/tasks/new'
  if (pathname.startsWith('/admin')) return '/admin'
  // 任务详情归属任务中心
  if (pathname.startsWith('/tasks')) return '/dashboard'
  return '/dashboard'
}

export function fillOutputName(template: string, date: string): string {
  return template.replace('{date}', date)
}
