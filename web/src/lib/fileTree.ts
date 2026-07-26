/**
 * 浏览器端文件与目录处理。
 *
 * ⚠️ DO NOT SIMPLIFY —— 这五个函数是从原 NewTaskPage 原样搬过来的，
 * 每一处怪异写法都对应一个真实的浏览器行为：
 *
 * - readDirectory 必须循环调用 readEntries 直到返回空批次：Chrome 每批
 *   最多给 100 项，只调一次会静默丢掉超出的文件。
 * - toUploadPart 用 file.slice() 重新包一个原生 Blob 再交给 FormData：
 *   带 webkitRelativePath 的 File 在部分浏览器里直接 append 会丢文件名。
 * - dedupeFiles 的键是 路径::size::lastModified：拖入的目录和手选的文件
 *   可能重叠，仅按名字去重会误删同名不同目录的日志。
 * - filesFromDrop 在目录模式下优先 webkitGetAsEntry，否则拿不到层级。
 */

export type UploadMode = 'zip' | 'folder'

type FileWithPath = File & { webkitRelativePath: string }

export function withRelativePath(file: File, relativePath: string): File {
  Object.defineProperty(file, 'webkitRelativePath', {
    value: relativePath,
    configurable: true,
  })
  return file
}

export function dedupeFiles(files: File[]): File[] {
  const seen = new Set<string>()
  const result: File[] = []
  for (const file of files) {
    const path = (file as FileWithPath).webkitRelativePath || file.name
    const key = `${path}::${file.size}::${file.lastModified}`
    if (seen.has(key)) continue
    seen.add(key)
    result.push(file)
  }
  return result
}

async function readDirectory(entry: FileSystemDirectoryEntry, prefix: string): Promise<File[]> {
  const reader = entry.createReader()
  const collected: File[] = []

  // Chrome 每批最多返回 100 项，必须读到空批次为止
  for (;;) {
    const batch = await new Promise<FileSystemEntry[]>((resolve, reject) => {
      reader.readEntries(resolve, reject)
    })
    if (batch.length === 0) break

    for (const child of batch) {
      const childPath = prefix ? `${prefix}/${child.name}` : child.name
      if (child.isDirectory) {
        collected.push(...(await readDirectory(child as FileSystemDirectoryEntry, childPath)))
      } else {
        const file = await new Promise<File>((resolve, reject) => {
          ;(child as FileSystemFileEntry).file(resolve, reject)
        })
        collected.push(withRelativePath(file, childPath))
      }
    }
  }
  return collected
}

export async function filesFromDrop(dataTransfer: DataTransfer, mode: UploadMode): Promise<File[]> {
  if (mode === 'folder' && dataTransfer.items?.length) {
    const entries: FileSystemEntry[] = []
    for (const item of Array.from(dataTransfer.items)) {
      const entry = item.webkitGetAsEntry?.()
      if (entry) entries.push(entry)
    }
    if (entries.length) {
      const collected: File[] = []
      for (const entry of entries) {
        if (entry.isDirectory) {
          collected.push(...(await readDirectory(entry as FileSystemDirectoryEntry, entry.name)))
        } else {
          const file = await new Promise<File>((resolve, reject) => {
            ;(entry as FileSystemFileEntry).file(resolve, reject)
          })
          collected.push(withRelativePath(file, entry.name))
        }
      }
      return dedupeFiles(collected)
    }
  }
  return dedupeFiles(Array.from(dataTransfer.files ?? []))
}

export function toUploadPart(file: File): { blob: Blob; filename: string } {
  const rawName = (file as FileWithPath).webkitRelativePath || file.name
  const filename = rawName.replace(/^\/+/, '')
  if (!filename) throw new Error('文件缺少名称')
  // 重新包成原生 Blob，确保 FormData 拿到的是干净对象
  const blob = file.slice(0, file.size, file.type)
  if (!(blob instanceof Blob)) throw new Error('文件内容不可读')
  return { blob, filename }
}

export function buildUploadForm(files: File[]): FormData {
  const form = new FormData()
  for (const file of files) {
    const { blob, filename } = toUploadPart(file)
    form.append('files', blob, filename)
  }
  return form
}

export function displayPath(file: File): string {
  return (file as FileWithPath).webkitRelativePath || file.name
}
