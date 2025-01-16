import axios from "axios"
import { store } from "@/store"
import { setAuthenticated } from "@/store/reducers/authReducer"

const AGENT_SERVER_URL = process.env.NEXT_PUBLIC_AGENT_SERVER_URL;

console.log(`server url: ${AGENT_SERVER_URL}`)

const api = axios.create({
  baseURL: AGENT_SERVER_URL
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
  async (error) => {
    if (error.response) {
      const { status } = error.response;
      if (status === 401) {
        localStorage.removeItem("authToken");
        store.dispatch(setAuthenticated(false));
        window.location.href = "/login";
      }
      return Promise.reject(new Error(`Request failed with status ${status}`));
    }
    return Promise.reject(error);
  }
)

export default api
