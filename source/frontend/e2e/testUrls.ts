const TEST_HOST = process.env.PW_HOST || "127.0.0.1";
const FRONTEND_PORT = process.env.PW_FRONTEND_PORT || "5173";
const API_PORT = process.env.PW_API_PORT || "8000";
const DEBUG_PORT = process.env.PW_DEBUG_PORT || "8080";

export const APP_BASE = `http://${TEST_HOST}:${FRONTEND_PORT}`;
export const API_BASE = `http://${TEST_HOST}:${API_PORT}`;
export const DEBUG_BASE = `http://${TEST_HOST}:${DEBUG_PORT}`;
export const API_HEALTH_URL = `${API_BASE}/api/health`;
