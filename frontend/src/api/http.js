import axios from "axios";

const BASE_PATH = "/ovpnmanager";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE || "http://192.168.1.182:8000/api",
  timeout: 8000,
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (resp) => resp,
  (error) => {
    const message = error?.response?.data?.detail || error.message || "请求失败";
    if (error?.response?.status === 401) {
      localStorage.removeItem("token");
      window.location.href = `${BASE_PATH}/login`;
    }
    return Promise.reject(new Error(message));
  },
);

export default api;
