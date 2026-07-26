import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  // 与 App.tsx 的 BrowserRouter basename 单一来源（那边读 import.meta.env.BASE_URL）。
  // 不要改成 './' —— 相对 base 在深层路由刷新时会把资源解析到 /app/tasks/assets/…
  base: process.env.VITE_BASE ?? '/app/',
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: process.env.VITE_API_TARGET ?? 'http://127.0.0.1:8080',
        changeOrigin: false,
        configure(proxy) {
          // 本地 dev 走 http，后端若给会话 Cookie 打了 Secure，浏览器会直接丢弃，
          // 表现为「登录成功但下一个请求就 401」。这里剥掉该属性。
          proxy.on('proxyRes', (res) => {
            const cookies = res.headers['set-cookie']
            if (cookies) {
              res.headers['set-cookie'] = cookies.map((cookie) => cookie.replace(/;\s*Secure/gi, ''))
            }
          })
        },
      },
    },
  },
  build: {
    // 六个路由与 AppShell 都是 React.lazy，构建器沿动态 import 边界自然分包。
    // 之前手写的 manualChunks 按 antd 子路径分组，规则本身已不自洽
    // （modal/progress/tabs 在多个分支重复，先匹配先赢），且每次增删组件都要同步维护。
    chunkSizeWarningLimit: 900,
  },
})
