import { useEffect, useEffectEvent } from 'react'

export function usePolling(callback: () => void | Promise<void>, enabled: boolean, delay: number): void {
  const onPoll = useEffectEvent(() => {
    void callback()
  })

  useEffect(() => {
    if (!enabled) return
    onPoll()
    const timer = window.setInterval(() => {
      onPoll()
    }, delay)
    return () => window.clearInterval(timer)
  }, [delay, enabled])
}
