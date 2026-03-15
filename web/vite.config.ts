import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  base: '/app/',
  plugins: [react()],
  build: {
    chunkSizeWarningLimit: 800,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes('node_modules')) return
          if (
            id.includes('/antd/es/table') ||
            id.includes('/antd/es/tabs') ||
            id.includes('/antd/es/list') ||
            id.includes('/antd/es/descriptions') ||
            id.includes('/antd/es/pagination') ||
            id.includes('/antd/es/progress') ||
            id.includes('/antd/es/statistic') ||
            id.includes('/rc-table') ||
            id.includes('/rc-tabs') ||
            id.includes('/rc-pagination') ||
            id.includes('/rc-virtual-list')
          ) {
            return 'antd-data'
          }
          if (
            id.includes('/antd/es/form') ||
            id.includes('/antd/es/input') ||
            id.includes('/antd/es/modal') ||
            id.includes('/antd/es/segmented') ||
            id.includes('/rc-field-form') ||
            id.includes('/rc-input') ||
            id.includes('/rc-textarea') ||
            id.includes('/rc-dialog') ||
            id.includes('/rc-segmented')
          ) {
            return 'antd-form'
          }
          if (id.includes('antd')) return 'antd-core'
          if (id.includes('@ant-design')) return 'ant-icons'
          if (id.includes('react-router')) return 'router'
          if (id.includes('dayjs')) return 'dayjs'
          if (id.includes('react') || id.includes('scheduler')) return 'react-vendor'
        },
      },
    },
  },
})
