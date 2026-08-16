import axios from "axios"

// API 基地址可通过 VITE_API_BASE 环境变量覆盖（部署/容器场景）。
const request = axios.create({
  baseURL: import.meta.env.VITE_API_BASE || "http://127.0.0.1:8000",
  timeout: 30000,
})

export default request
