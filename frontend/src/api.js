// src/api.js — Axios instance with JWT interceptor
import axios from "axios";

const BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

const api = axios.create({ baseURL: BASE_URL });

// ── Request interceptor: attach Bearer token ──────────────────────────────
api.interceptors.request.use((config) => {
  const token = localStorage.getItem("token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// ── Response interceptor: auto-logout on 401 ─────────────────────────────
api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem("token");
      window.location.href = "/";
    }
    return Promise.reject(err);
  }
);

// ── Auth ──────────────────────────────────────────────────────────────────
export const login = (username, password) =>
  api.post("/auth/login", { username, password });

export const register = (username, password) =>
  api.post("/auth/register", { username, password });

// ── Market ────────────────────────────────────────────────────────────────
export const getPrices = (symbols = "BTCUSDT,ETHUSDT") =>
  api.get(`/market/prices?symbols=${symbols}`);

export const getPrice = (symbol) =>
  api.get(`/market/price/${symbol}`);

// ── Trade ─────────────────────────────────────────────────────────────────
export const placeTrade = (symbol, side, quantity) =>
  api.post("/trade", { symbol, side, quantity: parseFloat(quantity) });

// ── Account ───────────────────────────────────────────────────────────────
export const getBalance = () => api.get("/account/balance");

export default api;
