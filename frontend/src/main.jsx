import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'

// createRoot 是 React 18 的入口 API，把整个应用挂到 index.html 的 #root 容器里。
// StrictMode 在开发环境会额外挂载/卸载一次组件，用来暴露副作用隐患（生产环境无影响）。
createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
