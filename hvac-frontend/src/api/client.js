import axios from "axios";

const client = axios.create({
  baseURL: "/api/v1",
  timeout: 30000,
  headers: { "Content-Type": "application/json" },
});

client.interceptors.request.use((config) => {
  const id =
    typeof crypto !== "undefined" && crypto.randomUUID
      ? crypto.randomUUID()
      : `req-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
  config.headers["X-Request-ID"] = id;
  return config;
});

client.interceptors.response.use(
  (response) => response.data,
  (error) => {
    const message =
      error.response?.data?.message ||
      error.response?.data?.detail ||
      error.message ||
      "Unknown error";
    const code = error.response?.data?.error || "NETWORK_ERROR";
    return Promise.reject({
      message,
      code,
      status: error.response?.status,
    });
  }
);

export default client;
