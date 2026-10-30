import base from './vite.config.ts'
const target = 'http://127.0.0.1:8766'
const proxy = Object.fromEntries(['/jobs', '/batches', '/models', '/openrouter-key', '/audio'].map((p) => [p, target]))
export default { ...base, server: { host: '127.0.0.1', port: 5199, strictPort: true, proxy } }
