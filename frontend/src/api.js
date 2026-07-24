/**
 * Em dev/ngrok, o Vite faz proxy de /api → backend (mesma origem = sem CORS).
 * Em produção, defina VITE_BACKEND_URL com a URL pública do backend.
 */
export const API_BASE = import.meta.env.VITE_BACKEND_URL || '/api'

/** Headers extras para o aviso do ngrok free e preflights. */
export const API_HEADERS = {
  'ngrok-skip-browser-warning': 'true',
}

export function apiFetch(path, options = {}) {
  const headers = {
    ...API_HEADERS,
    ...(options.headers || {}),
  }
  return fetch(`${API_BASE}${path}`, { ...options, headers })
}
