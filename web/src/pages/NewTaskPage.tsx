import { UploadOutlined } from '@ant-design/icons'
import { Alert, App as AntApp, Button, Card, List, Segmented, Space, Tag, Typography } from 'antd'
import { useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { request } from '../lib/api'

export function NewTaskPage() {
  const filesRef = useRef<HTMLInputElement | null>(null)
  const folderRef = useRef<HTMLInputElement | null>(null)
  const [mode, setMode] = useState<'zip' | 'folder'>('zip')
  const [uploading, setUploading] = useState(false)
  const [selectedNames, setSelectedNames] = useState<string[]>([])
  const { message } = AntApp.useApp()
  const navigate = useNavigate()
  const activeInputRef = mode === 'zip' ? filesRef : folderRef

  const syncNames = () => {
    const files = [
      ...(filesRef.current?.files ? Array.from(filesRef.current.files) : []),
      ...(folderRef.current?.files ? Array.from(folderRef.current.files) : []),
    ]
    setSelectedNames(files.map((file) => (file as File & { webkitRelativePath?: string }).webkitRelativePath || file.name))
  }

  const submit = async () => {
    const files =
      mode === 'zip'
        ? filesRef.current?.files
          ? Array.from(filesRef.current.files)
          : []
        : folderRef.current?.files
          ? Array.from(folderRef.current.files)
          : []
    if (!files.length) {
      message.error('请先选择要上传的内容')
      return
    }
    const formData = new FormData()
    files.forEach((file) => {
      const relative = (file as File & { webkitRelativePath?: string }).webkitRelativePath
      formData.append('files', file, relative || file.name)
    })
    setUploading(true)
    try {
      const result = await request<{ ok: boolean; job_id: string }>('/jobs', {
        method: 'POST',
        body: formData,
      })
      message.success(`任务 ${result.job_id} 已创建`)
      navigate(`/tasks/${result.job_id}`)
    } catch (error) {
      message.error(error instanceof Error ? error.message : '创建任务失败')
    } finally {
      setUploading(false)
    }
  }

  return (
    <div className="task-create-grid">
      <Card className="compact-card">
        <Space direction="vertical" size={20} style={{ width: '100%' }}>
          <div>
            <Typography.Title level={4} style={{ marginTop: 0 }}>
              创建巡检任务
            </Typography.Title>
            <Typography.Text type="secondary">
              支持 ZIP 压缩包和整个日志目录上传，后端会保留层级并自动识别日志根目录。
            </Typography.Text>
          </div>
          <Segmented
            block
            value={mode}
            onChange={(value) => setMode(value as 'zip' | 'folder')}
            options={[
              { label: 'ZIP / 文件', value: 'zip' },
              { label: '日志目录', value: 'folder' },
            ]}
          />
          <div className="upload-box">
            <input
              ref={filesRef}
              type="file"
              multiple
              accept=".zip,.log,application/zip,application/x-zip-compressed"
              onChange={syncNames}
              className="upload-input-hidden"
            />
            <input
              ref={folderRef}
              type="file"
              multiple
              onChange={syncNames}
              className="upload-input-hidden"
              {...({ webkitdirectory: 'true', directory: 'true' } as Record<string, string>)}
            />
            <button
              type="button"
              className="upload-panel"
              onClick={() => activeInputRef.current?.click()}
            >
              <span className="upload-panel-icon">
                <UploadOutlined />
              </span>
              <div className="upload-panel-copy">
                <strong>{mode === 'zip' ? '点击选择 ZIP 或日志文件' : '点击选择整个日志目录'}</strong>
                <span>
                  {mode === 'zip'
                    ? '支持 ZIP、多日志文件混合上传，保留原始文件名'
                    : '选择目录后会自动保留原始层级结构并上传'}
                </span>
              </div>
              <div className="upload-panel-actions">
                <Button type="default">{mode === 'zip' ? '选择文件' : '选择目录'}</Button>
                <Tag color={selectedNames.length ? 'success' : 'default'}>
                  {selectedNames.length ? `已选 ${selectedNames.length} 项` : '尚未选择'}
                </Tag>
              </div>
            </button>
          </div>
          <Button type="primary" icon={<UploadOutlined />} loading={uploading} onClick={() => void submit()}>
            提交任务
          </Button>
        </Space>
      </Card>
      <Card className="compact-card">
        <Typography.Title level={5} style={{ marginTop: 0 }}>
          当前选择
        </Typography.Title>
        {selectedNames.length ? (
          <List
            size="small"
            className="select-list"
            dataSource={selectedNames.slice(0, 15)}
            renderItem={(item) => <List.Item>{item}</List.Item>}
            footer={selectedNames.length > 15 ? `还有 ${selectedNames.length - 15} 个文件未展开` : null}
          />
        ) : (
          <Typography.Text type="secondary">当前未选择文件</Typography.Text>
        )}
        <div className="hint-stack">
          <Alert message="推荐方式" description="优先上传完整日志目录；如果上传 ZIP，建议保留日期和系统子目录。" type="info" showIcon />
          <Alert message="处理流程" description="上传后进入排队，识别日志结构，生成 Word，最后自动打包下载。" type="success" showIcon />
        </div>
      </Card>
    </div>
  )
}
