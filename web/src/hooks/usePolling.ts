import { useEffect } from 'react'

export function usePolling(callback: () => void | Promise<void>, enabled: boolean, delay: number): void {
  useEffect(() => {
    if (!enabled) return
    void callback()
    const timer = window.setInterval(() => {
      void callback()
    }, delay)
    return () => window.clearInterval(timer)
  }, [callback, delay, enabled])
}
