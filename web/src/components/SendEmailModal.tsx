import { Alert, App as AntApp, Button, Input, Modal, Space, Table, Tag, Typography } from 'antd'
import { useEffect, useState } from 'react'
import { isUnauthorized, request } from '../lib/api'
import type { EmailSuggestion, JobFile } from '../lib/types'

const EMAIL_PATTERN = /^[^\s@,;，；]+@[^\s@,;，；]+\.[^\s@,;，；]+$/

type FileEntry = {
  key: string
  name: string
  allowed: string[]
  recipients: string[]
  invalidRecipients: string[]
  disallowedRecipients: string[]
  recipientInput: string
}

function parseRecipients(input: string): { recipients: string[]; invalidRecipients: string[] } {
  const tokens = input.split(/[,;，；\s]+/).filter(Boolean)
  return {
    recipients: tokens.filter((token) => EMAIL_PATTERN.test(token)),
    invalidRecipients: tokens.filter((token) => !EMAIL_PATTERN.test(token)),
  }
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
  const { message, notification } = AntApp.useApp()
  const [entries, setEntries] = useState<FileEntry[]>([])
  const [loading, setLoading] = useState(false)
  const [suggestionFailed, setSuggestionFailed] = useState(false)
  const [sending, setSending] = useState(false)
  const [failedNames, setFailedNames] = useState<string[]>([])

  useEffect(() => {
    if (!open) return
    let cancelled = false

    const buildEntries = (suggestions: EmailSuggestion[]): FileEntry[] => {
      const byName = new Map(suggestions.map((item) => [item.name, item.recipients || []]))
      return files.map((file) => {
        const allowed = byName.get(file.name) || []
        return {
          key: file.name,
          name: file.name,
          allowed,
          recipients: allowed,
          invalidRecipients: [],
          disallowedRecipients: [],
          recipientInput: allowed.join(', '),
        }
      })
    }

    async function load() {
      setLoading(true)
      setFailedNames([])
      setSuggestionFailed(false)
      try {
        const data = await request<{ suggestions: EmailSuggestion[] }>(`/jobs/${jobId}/email-suggestions`)
        if (cancelled) return
        setEntries(buildEntries(data.suggestions || []))
      } catch {
        if (cancelled) return
        setEntries(buildEntries([]))
        setSuggestionFailed(true)
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    void load()

    return () => {
      cancelled = true
    }
  }, [open, jobId, files])

  const updateRecipients = (key: string, input: string) => {
    setEntries((prev) =>
      prev.map((e) => {
        if (e.key !== key) return e
        const { recipients, invalidRecipients } = parseRecipients(input)
        const allowedSet = new Set(e.allowed)
        return {
          ...e,
          recipientInput: input,
          // 服务端只接受配置内收件人的子集，这里同步过滤以免提交后被 403 拒绝。
          recipients: recipients.filter((addr) => allowedSet.has(addr)),
          invalidRecipients,
          disallowedRecipients: recipients.filter((addr) => !allowedSet.has(addr)),
        }
      }),
    )
  }

  const missingEntries = entries.filter((e) => e.allowed.length === 0)
  const invalidEntries = entries.filter((e) => e.invalidRecipients.length > 0)
  const disallowedEntries = entries.filter((e) => e.disallowedRecipients.length > 0)

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
      const result = await request<{ ok: boolean; sent: unknown[]; errors: { name: string; error: string }[] }>(
        `/jobs/${jobId}/send-email`,
        { method: 'POST', body: JSON.stringify({ files: payload }) },
      )
      const errors = result.errors || []
      if (errors.length > 0) {
        // 后端会把同一组收件人的多个文件合并为一条错误，名称用 / 连接。
        setFailedNames(errors.flatMap((e) => e.name.split('/').map((name) => name.trim())))
        notification.warning({
          message: '部分文件发送失败',
          description: (
            <div>
              {errors.map((e) => (
                <div key={e.name}>{`${e.name}: ${e.error}`}</div>
              ))}
            </div>
          ),
          duration: 0,
        })
        return
      }
      setFailedNames([])
      message.success(`成功发送 ${result.sent?.length || 0} 封邮件`)
      onCancel()
    } catch (err) {
      if (!isUnauthorized(err)) {
        message.error(err instanceof Error ? err.message : '发送失败')
      }
    } finally {
      setSending(false)
    }
  }

  const columns = [
    {
      title: '报告文件',
      dataIndex: 'name',
      key: 'name',
      render: (name: string) => (
        <Typography.Text type={failedNames.includes(name) ? 'danger' : undefined}>{name}</Typography.Text>
      ),
    },
    {
      title: '收件人',
      dataIndex: 'recipientInput',
      key: 'recipientInput',
      render: (_: string, record: FileEntry) => (
        <Input
          placeholder="可删减收件人，多个用逗号分隔"
          value={record.recipientInput}
          status={record.invalidRecipients.length > 0 ? 'error' : undefined}
          onChange={(e) => updateRecipients(record.key, e.target.value)}
        />
      ),
    },
    {
      title: '解析',
      key: 'count',
      width: 130,
      render: (_: unknown, record: FileEntry) => {
        if (record.invalidRecipients.length > 0) {
          return <Tag color="red">邮箱格式有误</Tag>
        }
        if (record.disallowedRecipients.length > 0) {
          return <Tag color="red">超出允许范围</Tag>
        }
        if (record.allowed.length === 0) {
          return <Tag color="orange">未配置收件人</Tag>
        }
        if (record.recipients.length === 0) {
          return <Tag color="orange">未选择</Tag>
        }
        return <Tag color="green">{record.recipients.length}个</Tag>
      },
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
      closable={!sending}
      maskClosable={false}
      keyboard={!sending}
    >
      <Space direction="vertical" size={12} style={{ width: '100%' }}>
        <Typography.Text type="secondary">
          收件人由服务端按系统配置自动填入。可以删减收件人，但不能添加配置之外的地址。
        </Typography.Text>
        {suggestionFailed && (
          <Alert type="warning" showIcon message="未能获取收件人配置，请关闭弹窗后重试；若仍然失败请联系管理员" />
        )}
        {missingEntries.length > 0 && (
          <Alert
            type="warning"
            showIcon
            message="以下文件在系统配置中没有收件人，发送时会被跳过，请联系管理员补充配置"
            description={missingEntries.map((e) => e.name).join('、')}
          />
        )}
        {disallowedEntries.length > 0 && (
          <Alert
            type="error"
            showIcon
            message="以下收件人不在该文件的允许范围内，请删除后再发送"
            description={disallowedEntries.map((e) => e.disallowedRecipients.join('、')).join('；')}
          />
        )}
        {invalidEntries.length > 0 && (
          <Alert
            type="error"
            showIcon
            message="存在格式不正确的收件人邮箱，请修正后再发送"
            description={invalidEntries.map((e) => e.invalidRecipients.join('、')).join('；')}
          />
        )}
        {failedNames.length > 0 && (
          <Alert
            type="error"
            showIcon
            message="标红的文件上次发送失败，可修改收件人后重新发送"
          />
        )}
        <Table
          dataSource={entries}
          columns={columns}
          loading={loading}
          pagination={false}
          size="small"
          scroll={{ y: 360 }}
        />
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
          <Button onClick={onCancel} disabled={sending}>取消</Button>
          <Button
            type="primary"
            loading={sending}
            disabled={loading || invalidEntries.length > 0 || disallowedEntries.length > 0}
            onClick={() => void handleSend()}
          >
            发送
          </Button>
        </div>
      </Space>
    </Modal>
  )
}
