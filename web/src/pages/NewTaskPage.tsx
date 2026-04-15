import { UploadOutlined } from '@ant-design/icons'
import { Alert, App as AntApp, Button, Card, List, Segmented, Space, Tag, Typography } from 'antd'
import type { DragEvent } from 'react'
import { useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { request } from '../lib/api'

type EntryWithPath = File & { webkitRelativePath?: string }

type FileEntry = {
  file: File
  relativePath: string
}

type DataTransferItemWithEntry = DataTransferItem & {
  webkitGetAsEntry?: () => FileSystemEntry | null
}

function withRelativePath(file: File, relativePath?: string): EntryWithPath {
  if (!relativePath) return file as EntryWithPath
  return Object.assign(file, { webkitRelativePath: relativePath }) as EntryWithPath
}

function dedupeFiles(files: EntryWithPath[]): EntryWithPath[] {
  const seen = new Set<string>()
  return files.filter((file) => {
    const key = `${file.webkitRelativePath || file.name}::${file.size}::${file.lastModified}`
    if (seen.has(key)) return false
    seen.add(key)
    return true
  })
}

async function readDirectory(entry: FileSystemEntry, prefix = ''): Promise<FileEntry[]> {
  if (entry.isFile) {
    const fileEntry = entry as FileSystemFileEntry
    const file = await new Promise<File>((resolve, reject) => {
      try {
        fileEntry.file(resolve, reject)
      } catch (error) {
        reject(error)
      }
    })
    const relativePath = [prefix, file.name].filter(Boolean).join('/')
    return [{ file, relativePath }]
  }

  if (!entry.isDirectory) {
    return []
  }

  const directoryEntry = entry as FileSystemDirectoryEntry
  const reader = directoryEntry.createReader()
  const children: FileSystemEntry[] = []
  while (true) {
    const batch = await new Promise<FileSystemEntry[]>((resolve, reject) => {
      try {
        reader.readEntries(resolve, reject)
      } catch (error) {
        reject(error)
      }
    })
    if (!batch.length) break
    children.push(...batch)
  }

  const folderName = entry.fullPath?.split('/').filter(Boolean).pop() || ''
  const nextPrefix = [prefix, folderName].filter(Boolean).join('/')
  const nested = await Promise.all(children.map((child) => readDirectory(child, nextPrefix)))
  return nested.flat()
}

async function filesFromDrop(dataTransfer: DataTransfer, mode: 'zip' | 'folder'): Promise<EntryWithPath[]> {
  const items = Array.from(dataTransfer.items || []) as DataTransferItemWithEntry[]
  if (mode === 'folder') {
    const entries = items
      .map((item) => item.webkitGetAsEntry?.() || null)
      .filter((entry): entry is FileSystemEntry => entry !== null)
    if (entries.length) {
      const nested = await Promise.all(entries.map((entry) => readDirectory(entry)))
      return dedupeFiles(nested.flat().map(({ file, relativePath }) => withRelativePath(file, relativePath)))
    }
  }

  return dedupeFiles(
    Array.from(dataTransfer.files || []).map((file) =>
      withRelativePath(file, (file as EntryWithPath).webkitRelativePath || undefined),
    ),
  )
}

function toUploadPart(file: EntryWithPath): { blob: Blob; filename: string } {
  const filename = (file.webkitRelativePath || file.name || '').replace(/^\/+/, '')
  if (!filename) {
    throw new Error('存在缺少文件名的上传项')
  }
  if (!(file instanceof Blob)) {
    throw new Error(`无效文件对象: ${filename}`)
  }
  return {
    // Re-wrap as a plain Blob so FormData.append always receives a native Blob/File payload.
    blob: file.slice(0, file.size, file.type),
    filename,
  }
}

export function NewTaskPage() {
  const filesRef = useRef<HTMLInputElement | null>(null)
  const folderRef = useRef<HTMLInputElement | null>(null)
  const [mode, setMode] = useState<'zip' | 'folder'>('zip')
  const [uploading, setUploading] = useState(false)
  const [selectedFiles, setSelectedFiles] = useState<EntryWithPath[]>([])
  const [dragging, setDragging] = useState(false)
  const { message } = AntApp.useApp()
  const navigate = useNavigate()
  const activeInputRef = mode === 'zip' ? filesRef : folderRef

  const syncFromInputs = () => {
    const files =
      mode === 'zip'
        ? filesRef.current?.files
          ? Array.from(filesRef.current.files)
          : []
        : folderRef.current?.files
          ? Array.from(folderRef.current.files)
          : []
    setSelectedFiles(dedupeFiles(files.map((file) => file as EntryWithPath)))
  }

  const selectedNames = selectedFiles.map((file) => file.webkitRelativePath || file.name)

  const handleDrop = async (event: DragEvent<HTMLButtonElement>) => {
    event.preventDefault()
    setDragging(false)
    const droppedFiles = await filesFromDrop(event.dataTransfer, mode)
    if (!droppedFiles.length) {
      message.error(mode === 'zip' ? '未检测到可上传文件' : '请拖入日志目录或目录中的文件')
      return
    }
    setSelectedFiles(droppedFiles)
  }

  const submit = async () => {
    const files = selectedFiles
    if (!files.length) {
      message.error('请先选择要上传的内容')
      return
    }
    const formData = new FormData()
    setUploading(true)
    try {
      files.forEach((file) => {
        const { blob, filename } = toUploadPart(file)
        formData.append('files', blob, filename)
      })
      const result = await request<{ ok: boolean; job_id: string }>('/jobs', {
        method: 'POST',
        body: formData,
      })
      message.success(`任务 ${result.job_id} 已创建`)
      navigate(`/tasks/${result.job_id}`)
    } catch (error) {
      console.error('Create job failed', error)
      if (error instanceof TypeError && /failed to/i.test(error.message)) {
        message.error('上传请求未发出，请刷新页面后重试；如果仍失败，请改用 ZIP 方式上传')
      } else {
        message.error(error instanceof Error ? error.message : '创建任务失败')
      }
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
              onChange={syncFromInputs}
              className="upload-input-hidden"
            />
            <input
              ref={folderRef}
              type="file"
              multiple
              onChange={syncFromInputs}
              className="upload-input-hidden"
              {...({ webkitdirectory: 'true', directory: 'true' } as Record<string, string>)}
            />
            <button
              type="button"
              className={`upload-panel${dragging ? ' dragging' : ''}`}
              onClick={() => activeInputRef.current?.click()}
              onDragEnter={(event) => {
                event.preventDefault()
                setDragging(true)
              }}
              onDragOver={(event) => {
                event.preventDefault()
                event.dataTransfer.dropEffect = 'copy'
                if (!dragging) setDragging(true)
              }}
              onDragLeave={(event) => {
                event.preventDefault()
                if (event.currentTarget === event.target) setDragging(false)
              }}
              onDrop={(event) => void handleDrop(event)}
            >
              <span className="upload-panel-icon">
                <UploadOutlined />
              </span>
              <div className="upload-panel-copy">
                <strong>{mode === 'zip' ? '点击选择 ZIP 或日志文件' : '点击选择整个日志目录'}</strong>
                <span>
                  {mode === 'zip'
                    ? '支持 ZIP、多日志文件混合上传，也支持直接拖拽文件到这里'
                    : '选择目录后会自动保留原始层级结构并上传，也支持直接拖拽目录到这里'}
                </span>
              </div>
              <div className="upload-panel-actions">
                <Button type="default">{mode === 'zip' ? '选择文件' : '选择目录'}</Button>
                <Tag color={selectedNames.length ? 'success' : dragging ? 'processing' : 'default'}>
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
