import axios from "axios";

const api = axios.create({
  baseURL: import.meta.env.PROD
    ? ""
    : (import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000"),
  withCredentials: true
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('clinora_access_token');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

api.interceptors.response.use((response) => response, async (error) => {
  const original = error.config;
  const isAuthRequest = String(original?.url || '').includes('/auth/');
  if (error.response?.status === 401 && original && !original._retry && !isAuthRequest) {
    original._retry = true;
    try {
      const refreshed = await api.post('/api/v1/auth/refresh');
      localStorage.setItem('clinora_access_token', refreshed.data.access_token);
      localStorage.setItem('clinora_role', refreshed.data.role);
      original.headers.Authorization = `Bearer ${refreshed.data.access_token}`;
      return api(original);
    } catch {
      localStorage.removeItem('clinora_access_token');
      localStorage.removeItem('clinora_role');
    }
  }
  return Promise.reject(error);
});

export default api;
export const messageOf = (error: any): string => {
  const detail = error?.response?.data?.detail;
  if (Array.isArray(detail)) return detail.map((item: any) => `${item.loc?.slice(-1)[0] || 'Field'}: ${item.msg}`).join(', ');
  return detail || error?.response?.data?.message || error?.message || 'Something went wrong. Please try again.';
};
