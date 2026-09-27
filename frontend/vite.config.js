import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/auth': 'http://localhost:8000',
      '/waste-analytics': 'http://localhost:8000',
      '/recommendations': 'http://localhost:8000',
      '/pipeline': 'http://localhost:8000',
      '/alerts': 'http://localhost:8000',
      '/greenops': 'http://localhost:8000',
      '/assistant': 'http://localhost:8000',
      '/anomalies': 'http://localhost:8000',
      '/forecasting': 'http://localhost:8000',
      '/ingest': 'http://localhost:8000',
      '/health': 'http://localhost:8000',
      '/remediation': 'http://localhost:8000',
      '/gpu-optimizer': 'http://localhost:8000',
      '/cost-grouping': 'http://localhost:8000',
    },
  },
})
