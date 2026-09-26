/**
 * Typed OpenAPI Fetch Client for EduPulse API.
 * Uses schema.d.ts generated from docs/openapi.yaml.
 * Zero token storage in localStorage/sessionStorage (uses same-origin session cookies and in-memory CSRF token).
 */

import createClient from 'openapi-fetch';
import type { paths } from './schema';

let inMemoryCsrfToken: string | null = null;

export function getCsrfToken(): string | null {
  return inMemoryCsrfToken;
}

export function setCsrfToken(token: string | null): void {
  inMemoryCsrfToken = token;
}

/**
 * OpenApi fetch client configured with same-origin credentials and CSRF header handling.
 */
export const apiClient = createClient<paths>({
  baseUrl: '',
  fetch: async (request: Request) => {
    const method = request.method.toUpperCase();
    if (['POST', 'PUT', 'PATCH', 'DELETE'].includes(method)) {
      if (!inMemoryCsrfToken) {
        try {
          const res = await fetch('/api/v1/csrf/', { credentials: 'same-origin' });
          if (res.ok) {
            const data = await res.json();
            if (data?.csrfToken) {
              inMemoryCsrfToken = data.csrfToken;
            }
          }
        } catch {
          // Graceful fallback
        }
      }
      if (inMemoryCsrfToken) {
        request.headers.set('X-CSRFToken', inMemoryCsrfToken);
      }
    }
    return fetch(request);
  },
});

/**
 * Fetch and store CSRF token from the backend.
 */
export async function refreshCsrf(): Promise<string | null> {
  const { data, error } = await apiClient.GET('/api/v1/csrf/');
  if (data?.csrfToken) {
    inMemoryCsrfToken = data.csrfToken;
    return data.csrfToken;
  }
  if (error) {
    console.error('Failed fetching CSRF token:', error);
  }
  return null;
}
