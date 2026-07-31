import { DownloadOutlined, EditOutlined, InboxOutlined, PlusOutlined, ReloadOutlined, RocketOutlined, SaveOutlined, UploadOutlined } from '@ant-design/icons'
import { App as AntApp, Button, Collapse, Drawer, Form, Input, Modal, Select, Space, Table, Tag, Upload, Typography } from 'antd'
import type { UploadFile } from 'antd'
import { useEffect, useEffectEvent, useState } from 'react'

import { API_PREFIX, request } from '../../lib/api'
import type { InspectionDevice, InspectionSystem, InspectionVersion } from '../../lib/types'
import styles from './InspectionSystemsSection.module.css'

const STATUS: Record<string, { text: string; color: string }> = {
  draft: { text: '草稿', color: 'default' }, built: { text: '已构建', color: 'processing' },
  validating: { text: '验证中', color: 'warning' }, validated: { text: '已验证', color: 'success' },
  published: { text: '已发布', color: 'green' }, retired: { text: '已退役', color: 'default' },
}

export function InspectionSystemsSection() {
  const { message } = AntApp.useApp()
  const [systems, setSystems] = useState<InspectionSystem[]>([])
  const [loading, setLoading] = useState(true)
  const [importOpen, setImportOpen] = useState(false)
  const [importSubmitting, setImportSubmitting] = useState(false)
  const [importForm] = Form.useForm()
  const [sourceFile, setSourceFile] = useState<UploadFile[]>([])
  const [selectedSystem, setSelectedSystem] = useState<InspectionSystem | null>(null)
  const [versions, setVersions] = useState<InspectionVersion[]>([])
  const [draft, setDraft] = useState<InspectionVersion | null>(null)
  const [validationFiles, setValidationFiles] = useState<UploadFile[]>([])

  const loadSystems = async () => {
    setLoading(true)
    try { setSystems((await request<{ systems: InspectionSystem[] }>('/admin/inspection-systems')).systems) }
    catch (error) { message.error(error instanceof Error ? error.message : '加载巡检系统失败') }
    finally { setLoading(false) }
  }
  const loadVersions = async (system: InspectionSystem, preferredId?: number) => {
    const data = await request<{ versions: InspectionVersion[] }>(`/admin/inspection-systems/${system.id}/versions`)
    setVersions(data.versions)
    const next = data.versions.find((item) => item.id === preferredId) ?? data.versions[0] ?? null
    setDraft(next ? structuredClone(next) : null)
  }
  const loadInitialSystems = useEffectEvent(() => { void loadSystems() })
  useEffect(() => { loadInitialSystems() }, [])

  const mutateDevice = (index: number, update: Partial<InspectionDevice>) => {
    if (!draft) return
    const devices = draft.config.devices.map((device, i) => i === index ? { ...device, ...update } : device)
    setDraft({ ...draft, config: { ...draft.config, devices } })
  }
  const save = async () => {
    if (!draft) return
    try {
      const result = await request<InspectionVersion>(`/admin/system-drafts/${draft.id}`, { method: 'PUT', body: JSON.stringify({ config: draft.config, recipients: draft.recipients }) })
      message.success('校对结果已保存'); setDraft(result); if (selectedSystem) await loadVersions(selectedSystem, result.id)
    } catch (error) { message.error(error instanceof Error ? error.message : '保存校对失败') }
  }
  const action = async (path: string, success: string) => {
    if (!draft) return
    try {
      await request(path, { method: 'POST' }); message.success(success)
      if (selectedSystem) { await loadVersions(selectedSystem, draft.id); await loadSystems() }
    } catch (error) { message.error(error instanceof Error ? error.message : '操作失败') }
  }
  const validate = async () => {
    if (!draft || validationFiles.length === 0) return
    const form = new FormData(); validationFiles.forEach((item) => item.originFileObj && form.append('files', item.originFileObj))
    try {
      const result = await request<{ status: string; validation: { valid: boolean; issues: string[] } }>(`/admin/system-drafts/${draft.id}/validation-files`, { method: 'POST', body: form })
      if (result.validation.valid) message.success('全部设备和命令验证通过')
      else message.error(result.validation.issues.join('；'))
      setValidationFiles([]); if (selectedSystem) await loadVersions(selectedSystem, draft.id)
    } catch (error) { message.error(error instanceof Error ? error.message : '严格验证失败') }
  }
  const createDraft = async () => {
    let values
    try { values = await importForm.validateFields() }
    catch { message.error('请完整填写导入信息'); return }
    const file = sourceFile[0]?.originFileObj
    if (!file) { message.error('请选择 DOCX'); return }
    const form = new FormData(); form.append('file', file); form.append('mode', values.mode); form.append('system_key', values.system_key ?? ''); form.append('display_name', values.display_name ?? '')
    if (values.system_id) form.append('system_id', String(values.system_id))
    setImportSubmitting(true)
    try {
      const result = await request<InspectionVersion>('/admin/system-drafts', { method: 'POST', body: form })
      message.success(`已解析 ${result.config.devices.length} 台设备`); setImportOpen(false); importForm.resetFields(); setSourceFile([]); await loadSystems()
      const system = systems.find((item) => item.id === result.system_id) ?? { id: result.system_id, system_key: result.system_key, display_name: result.display_name, current_version_id: null, version: null, status: null, validation_json: null }
      setSelectedSystem(system); await loadVersions(system, result.id)
    } catch (error) { message.error(error instanceof Error ? error.message : '解析并创建草稿失败') }
    finally { setImportSubmitting(false) }
  }

  const editable = draft?.status === 'draft' || draft?.status === 'built'
  return <>
    <div className={styles.toolbar}>
      <Space><Button type="primary" icon={<PlusOutlined />} onClick={() => setImportOpen(true)}>导入 DOCX</Button><Button icon={<ReloadOutlined />} onClick={() => void loadSystems()}>刷新</Button></Space>
      <Typography.Text type="secondary">最多 50 个系统，每个系统最多 100 台设备</Typography.Text>
    </div>
    <Table rowKey="id" loading={loading} dataSource={systems} pagination={false} columns={[
      { title: '系统标识', dataIndex: 'system_key' }, { title: '系统名称', dataIndex: 'display_name' },
      { title: '当前版本', render: (_, row) => row.version ? `v${row.version}` : '-' },
      { title: '状态', render: (_, row) => row.status ? <Tag color={STATUS[row.status]?.color}>{STATUS[row.status]?.text ?? row.status}</Tag> : <Tag>待发布</Tag> },
      { title: '操作', width: 110, render: (_, row) => <Button icon={<EditOutlined />} onClick={() => { setSelectedSystem(row); void loadVersions(row) }}>管理</Button> },
    ]} />

    <Modal title="导入巡检模板" open={importOpen} confirmLoading={importSubmitting} onCancel={() => setImportOpen(false)} onOk={() => void createDraft()} okText="解析并创建草稿">
      <Form form={importForm} layout="vertical" initialValues={{ mode: 'create' }}>
        <Form.Item name="mode" label="导入方式" rules={[{ required: true }]}><Select options={[{ value: 'create', label: '创建新系统' }, { value: 'incremental', label: '增量添加设备' }, { value: 'replace', label: '完整替换模板' }]} /></Form.Item>
        <Form.Item noStyle shouldUpdate>{({ getFieldValue }) => getFieldValue('mode') === 'create' ? <>
          <Form.Item name="system_key" label="系统标识" rules={[{ required: true }]}><Input placeholder="例如 IMS" /></Form.Item><Form.Item name="display_name" label="系统名称" rules={[{ required: true }]}><Input /></Form.Item>
        </> : <Form.Item name="system_id" label="目标系统" rules={[{ required: true }]}><Select options={systems.map((item) => ({ value: item.id, label: `${item.system_key} · ${item.display_name}` }))} /></Form.Item>}</Form.Item>
        <Upload.Dragger accept=".docx" maxCount={1} fileList={sourceFile} beforeUpload={() => false} onChange={({ fileList }) => setSourceFile(fileList)}><InboxOutlined /><p>选择一份 .docx 巡检模板</p></Upload.Dragger>
      </Form>
    </Modal>

    <Drawer width="min(1100px, 96vw)" title={selectedSystem ? `${selectedSystem.system_key} · 版本管理` : '版本管理'} open={Boolean(selectedSystem)} onClose={() => { setSelectedSystem(null); setDraft(null) }}>
      <div className={styles.versionBar}><Select className={styles.versionSelect} value={draft?.id} options={versions.map((item) => ({ value: item.id, label: `v${item.version} · ${STATUS[item.status]?.text ?? item.status}${item.is_current ? ' · 当前' : ''}` }))} onChange={(id) => { const item = versions.find((version) => version.id === id); setDraft(item ? structuredClone(item) : null) }} />
        {draft && <Space wrap><Button icon={<DownloadOutlined />} href={`${API_PREFIX}/admin/system-drafts/${draft.id}/files/docx`}>草稿 DOCX</Button>{draft.vbs_sha256 && <Button icon={<DownloadOutlined />} href={`${API_PREFIX}/admin/system-drafts/${draft.id}/files/vbs`}>VBS</Button>}{editable && <Button icon={<SaveOutlined />} onClick={() => void save()}>保存校对</Button>}{draft.status === 'draft' && <Button type="primary" icon={<RocketOutlined />} onClick={() => void action(`/admin/system-drafts/${draft.id}/build`, '构建完成')}>构建</Button>}{draft.status === 'validated' && <Button type="primary" onClick={() => void action(`/admin/system-drafts/${draft.id}/publish`, '发布完成')}>发布</Button>}{draft.status === 'retired' && <Button onClick={() => void action(`/admin/inspection-systems/${draft.system_id}/versions/${draft.version}/activate`, '已回滚到该版本')}>回滚到此版本</Button>}</Space>}
      </div>
      {draft && <>
        <div className={styles.meta}><Tag color={STATUS[draft.status]?.color}>{STATUS[draft.status]?.text}</Tag><Typography.Text code>{draft.template_sha256}</Typography.Text>{draft.vbs_sha256 && <Typography.Text code>{draft.vbs_sha256}</Typography.Text>}</div>
        <Form layout="vertical"><Form.Item label="收件人白名单"><Select mode="tags" disabled={!editable} value={draft.recipients} onChange={(recipients) => setDraft({ ...draft, recipients })} tokenSeparators={[',', ';']} /></Form.Item></Form>
        <Table rowKey="order" pagination={false} scroll={{ x: 900 }} dataSource={draft.config.devices} columns={[
          { title: '顺序', width: 72, render: (_, row, index) => <Input type="number" disabled={!editable} value={row.order} onChange={(event) => mutateDevice(index, { order: Number(event.target.value) })} /> },
          { title: '设备名称', width: 210, render: (_, row, index) => <Input disabled={!editable} value={row.name} onChange={(event) => mutateDevice(index, { name: event.target.value })} /> },
          { title: '管理 IP', width: 160, render: (_, row, index) => <Input disabled={!editable} value={row.ip} onChange={(event) => mutateDevice(index, { ip: event.target.value })} /> },
          { title: '驱动', width: 150, render: (_, row, index) => <Select disabled={!editable} value={row.driver} options={[{ value: 'huawei_vrp', label: 'Huawei VRP' }, { value: 'generic_show', label: '通用 show' }]} onChange={(driver) => mutateDevice(index, { driver })} /> },
          { title: '命令与超时（每行：秒 | 命令）', render: (_, row, index) => <Input.TextArea disabled={!editable} autoSize={{ minRows: 2, maxRows: 8 }} value={row.commands.map((item) => `${item.timeout_seconds} | ${item.command}`).join('\n')} onChange={(event) => mutateDevice(index, { commands: event.target.value.split('\n').filter(Boolean).map((line, commandIndex) => { const [timeout, ...command] = line.split('|'); return { timeout_seconds: Number(timeout.trim()) || 120, command: command.join('|').trim(), result_cell: row.commands[commandIndex]?.result_cell ?? null } }) })} /> },
        ]} />
        <Collapse className={styles.advanced} items={[{ key: 'mapping', label: '高级回填映射与非命令规则', children: <Input.TextArea key={`${draft.id}-${draft.updated_at}`} disabled={!editable} defaultValue={JSON.stringify(draft.config, null, 2)} autoSize={{ minRows: 10, maxRows: 24 }} onBlur={(event) => { try { const config = JSON.parse(event.target.value) as InspectionVersion['config']; setDraft({ ...draft, config }); message.success('高级配置已载入，点击“保存校对”生效') } catch { message.error('高级配置不是有效 JSON') } }} /> }]} />
        {draft.status === 'built' && <div className={styles.validation}><Upload multiple accept=".zip,.log,.tsv" fileList={validationFiles} beforeUpload={() => false} onChange={({ fileList }) => setValidationFiles(fileList)}><Button icon={<UploadOutlined />}>选择真实试运行 ZIP/LOG/清单</Button></Upload><Button type="primary" disabled={!validationFiles.length} onClick={() => void validate()}>严格验证</Button></div>}
        {draft.validation.issues?.length ? <Typography.Paragraph type="danger">{draft.validation.issues.join('；')}</Typography.Paragraph> : null}
      </>}
    </Drawer>
  </>
}
