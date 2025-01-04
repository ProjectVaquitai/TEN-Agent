import axios from "axios"
import { store } from "@/store"
import { setAuthenticated } from "@/store/reducers/authReducer"

const api = axios.create({
  baseURL: "http://localhost:8080",
})

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("authToken")
  if (token) {
    config.headers.Authorization = `${token}`
  }
  return config
})

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem("authToken")
      store.dispatch(setAuthenticated(false))
      window.location.href = "/login"
    }
    return Promise.reject(error)
  },
)

export default api
