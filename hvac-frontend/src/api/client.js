import axios from "axios";

const client = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "",
  timeout: 15_000,
  headers: { "Content-Type": "application/json" },
});

client.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error.response?.status;
    const detail = error.response?.data?.detail ?? error.message;

    if (status === 422) {
      console.error("[API] Validation error:", detail);
    } else if (status >= 500) {
      console.error("[API] Server error:", detail);
    }

    return Promise.reject(error);
  }
);

export default client;
