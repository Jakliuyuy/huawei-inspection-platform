import { App as AntApp, Button, Input, Modal, Space, Table, Tag, Typography } from 'antd'
import { useEffect, useState } from 'react'
import { request } from '../lib/api'
import type { JobFile } from '../lib/types'

type FileEntry = {
  key: string
  name: string
  recipients: string[]
  recipientInput: string
}

export function SendEmailModal({
  open,
  jobId,
  files,
  onCancel,
}: {
  open: boolean
  jobId: string
  files: JobFile[]
  onCancel: () => void
}) {
  const { message } = AntApp.useApp()
  const [entries, setEntries] = useState<FileEntry[]>([])
  const [sending, setSending] = useState(false)

  useEffect(() => {
    if (!open) return
    async function load() {
      try {
        const config = await request<Record<string, string[]>>('/email-config')
        const items: FileEntry[] = files.map((file) => {
          const recipients = guessRecipients(file.name, config) || []
          return {
            key: file.name,
            name: file.name,
            recipients,
            recipientInput: recipients.join(', '),
          }
        })
        setEntries(items)
      } catch {
        const items: FileEntry[] = files.map((file) => ({
          key: file.name,
          name: file.name,
          recipients: [],
          recipientInput: '',
        }))
        setEntries(items)
      }
    }
    load()
  }, [open, files])

  const updateRecipients = (key: string, input: string) => {
    setEntries((prev) =>
      prev.map((e) =>
        e.key === key
          ? { ...e, recipientInput: input, recipients: input.split(/[,;，；\s]+/).filter(Boolean) }
          : e,
      ),
    )
  }

  const handleSend = async () => {
    const payload = entries
      .filter((e) => e.recipients.length > 0)
      .map((e) => ({ name: e.name, recipients: e.recipients }))

    if (payload.length === 0) {
      message.warning('请至少为一个文件设置收件人')
      return
    }

    setSending(true)
    try {
      const result = await request<{ ok: boolean; sent: unknown[]; errors: unknown[] }>(
        `/jobs/${jobId}/send-email`,
        { method: 'POST', body: JSON.stringify({ files: payload }) },
      )
      if (result.errors?.length) {
        const errorList = (result.errors as { name: string; error: string }[])
          .map((e) => `${e.name}: ${e.error}`)
          .join('\n')
        message.warning(`部分文件发送失败:\n${errorList}`)
      } else {
        message.success(`成功发送 ${result.sent?.length || 0} 封邮件`)
      }
      onCancel()
    } catch (err) {
      message.error(err instanceof Error ? err.message : '发送失败')
    } finally {
      setSending(false)
    }
  }

  const columns = [
    {
      title: '报告文件',
      dataIndex: 'name',
      key: 'name',
      render: (name: string) => <Typography.Text>{name}</Typography.Text>,
    },
    {
      title: '收件人',
      dataIndex: 'recipientInput',
      key: 'recipientInput',
      render: (_: string, record: FileEntry) => (
        <Input
          placeholder="多个收件人用逗号分隔"
          value={record.recipientInput}
          onChange={(e) => updateRecipients(record.key, e.target.value)}
        />
      ),
    },
    {
      title: '解析',
      key: 'count',
      width: 70,
      render: (_: unknown, record: FileEntry) => (
        <Tag color={record.recipients.length > 0 ? 'green' : 'default'}>
          {record.recipients.length}个
        </Tag>
      ),
    },
  ]

  return (
    <Modal
      title="发送邮件"
      open={open}
      onCancel={onCancel}
      footer={null}
      width={700}
      destroyOnClose
    >
      <Space direction="vertical" size={12} style={{ width: '100%' }}>
        <Typography.Text type="secondary">
          为每个报告文件指定收件人邮箱，多个收件人请用逗号或分号分隔。
        </Typography.Text>
        <Table
          dataSource={entries}
          columns={columns}
          pagination={false}
          size="small"
          scroll={{ y: 360 }}
        />
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
          <Button onClick={onCancel} disabled={sending}>取消</Button>
          <Button type="primary" loading={sending} onClick={() => void handleSend()}>
            发送
          </Button>
        </div>
      </Space>
    </Modal>
  )
}

function guessRecipients(
  fileName: string,
  config: Record<string, string[]>,
): string[] | null {
  const nameUpper = fileName.toUpperCase().replace(/\.DOCX$/i, '').replace(/\.DOC$/i, '')
  const keys = ['TOC', 'TOB', 'GPRS', 'SMS', 'SOFTSWITCH', 'INTELLIGENTNET', 'NM1', 'NM2', 'NM3']
  for (const key of keys) {
    if (nameUpper.includes(key)) {
      return config[key] || null
    }
  }
  return null
}
