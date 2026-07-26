export const API_PREFIX = '/api'

export class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

export function isUnauthorized(error: unknown): boolean {
  return error instanceof ApiError && error.status === 401
}

let unauthorizedHandler: (() => void) | null = null

export function setUnauthorizedHandler(handler: (() => void) | null): void {
  unauthorizedHandler = handler
}

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_PREFIX}${path}`, {
    credentials: 'include',
    ...init,
    headers: {
      ...(init?.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }),
      ...(init?.headers ?? {}),
    },
  })

  if (!response.ok) {
    const data = await response.json().catch(() => ({ detail: '请求失败' }))
    // 登录接口自身的 401 属于凭据错误，交给调用方提示，不触发全局登出。
    if (response.status === 401 && !path.startsWith('/auth/')) {
      unauthorizedHandler?.()
    }
    throw new ApiError(response.status, data.detail || '请求失败')
  }

  const contentType = response.headers.get('content-type') || ''
  if (contentType.includes('application/json')) {
    return response.json() as Promise<T>
  }

  return null as T
}

/** 上传请求根本没发出去（网络断开、被扩展拦截等）时的提示，fetch 与 XHR 两条路径共用 */
export const UPLOAD_TRANSPORT_HINT =
  '上传请求未发出，请刷新页面后重试；如果仍失败，请改用 ZIP 方式上传'

export class UploadTransportError extends Error {
  constructor() {
    super(UPLOAD_TRANSPORT_HINT)
    this.name = 'UploadTransportError'
  }
}

export type UploadProgress = { loaded: number; total: number; percent: number }

/**
 * 带进度的上传。fetch 拿不到上传进度，而目录上传动辄几百个文件、几百 MB，
 * 没有进度条会被当成卡死，所以这条路径必须用 XHR。
 *
 * ⚠️ 绝不能 setRequestHeader('Content-Type', ...) —— multipart 的 boundary
 * 必须由浏览器自己生成，这与 request() 里对 FormData 跳过该头是同一个道理。
 */
export function uploadWithProgress<T>(
  path: string,
  form: FormData,
  onProgress?: (progress: UploadProgress) => void,
): { promise: Promise<T>; abort: () => void } {
  const xhr = new XMLHttpRequest()
  let aborted = false

  const promise = new Promise<T>((resolve, reject) => {
    xhr.open('POST', `${API_PREFIX}${path}`)
    xhr.withCredentials = true

    xhr.upload.onprogress = (event) => {
      if (!event.lengthComputable || !onProgress) return
      onProgress({
        loaded: event.loaded,
        total: event.total,
        percent: Math.round((event.loaded / event.total) * 100),
      })
    }

    xhr.onload = () => {
      let data: { detail?: string } = {}
      try {
        data = JSON.parse(xhr.responseText || '{}')
      } catch {
        data = {}
      }
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(data as T)
        return
      }
      if (xhr.status === 401 && !path.startsWith('/auth/')) {
        unauthorizedHandler?.()
      }
      reject(new ApiError(xhr.status, data.detail || '上传失败'))
    }

    xhr.onerror = () => reject(new UploadTransportError())
    xhr.ontimeout = () => reject(new UploadTransportError())
    xhr.onabort = () => {
      aborted = true
      reject(new DOMException('Aborted', 'AbortError'))
    }

    xhr.send(form)
  })

  return {
    promise,
    abort: () => {
      if (!aborted) xhr.abort()
    },
  }
}
