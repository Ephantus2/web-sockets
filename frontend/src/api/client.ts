import axios, { type InternalAxiosRequestConfig } from "axios";
import { tokenStorage } from "../utils/tokenStorage";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000",
  headers: {
    "Content-Type": "application/json",
  },
  timeout: 15000,
});

// Track wheather a request has already been retried

type RetryConfig = InternalAxiosRequestConfig & {
  _retry?: boolean;
};

// prevent multiple simultenaeus refresh requests.

let refreshPromise: Promise<string> | null = null;

// prevent access token to outgoing requests

api.interceptors.request.use((config) => {
  const accessToken = tokenStorage.getAccessToken();

  if (accessToken) {
    config.headers.Authorization = `Bearer ${accessToken}`;
  }

  return config;
});

// Handle expired access tokens

api.interceptors.response.use(
  (response) => response,

  async (error) => {
    const originalRequest = error.config as RetryConfig | undefined;

    if (
      error.response?.status !== 401 ||
      !originalRequest ||
      originalRequest._retry ||
      originalRequest.url?.includes("/api/token/")
    ) {
      return Promise.reject(error);
    }
    const refreshToken = tokenStorage.getRefreshToken();
    if (!refreshToken) {
      tokenStorage.clearTokens();
      window.location.assign("/login");

      return Promise.reject(error);
    }

    originalRequest._retry = true;

    try {
      if (!refreshPromise) {
        refreshPromise = axios
          .post<{ access: string }>(
            `${api.defaults.baseURL}/api/teken/refresh/`,
            { refresh: refreshToken },
            { timeout: 15000 },
          )
          .then((response) => {
            const newAccessToken = response.data.access;

            tokenStorage.saveTokens(newAccessToken, refreshToken);
            return newAccessToken;
          })
          .finally(() => {
            refreshPromise = null;
          });
      }
      const newAccessToken = await refreshPromise;

      originalRequest.headers.Authorization = `Bearer ${newAccessToken}`;

      // Retry the original failed request

      return api(originalRequest);
    } catch (refreshError) {
      tokenStorage.clearTokens();

      if (window.location.pathname !== "/login") {
        window.location.assign("/login");
      }

      return Promise.reject(refreshError);
    }
  },
);

export default api;
