import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import fs from 'node:fs'
import path from 'node:path'

const staticDir = path.resolve(__dirname, '../static')

const types = { '.webp': 'image/webp', '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.svg': 'image/svg+xml' }

function serveProjectStatic() {
  return {
    name: 'serve-project-static',
    configureServer(server) {
      server.middlewares.use('/static', (req, res, next) => {
        const file = path.join(staticDir, decodeURIComponent(req.url.split('?')[0]))
        if (!file.startsWith(staticDir) || !fs.existsSync(file) || fs.statSync(file).isDirectory()) return next()
        res.setHeader('Content-Type', types[path.extname(file)] || 'application/octet-stream')
        fs.createReadStream(file).pipe(res)
      })
    }
  }
}

export default defineConfig({
  plugins: [react(), serveProjectStatic()],
  server: { port: 5173 }
})
