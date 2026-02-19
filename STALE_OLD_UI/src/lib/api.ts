import { Env } from '../config/env';

/**
 * Standardized API Client
 * Handles relative paths, default headers, and error normalization.
 */
class ApiClient {
  private getBaseUrl(endpoint: string): string {
    if (endpoint.startsWith('/admin')) return Env.API_BASE_URL; // Admin routes are under /agent
    return Env.API_BASE_URL;
  }

  private async request<T>(
    method: 'GET' | 'POST' | 'PUT' | 'DELETE',
    path: string,
    body?: any,
    customHeaders: Record<string, string> = {}
  ): Promise<T> {
    const url = `${this.getBaseUrl(path)}${path}`;
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...customHeaders,
    };

    const config: RequestInit = {
      method,
      headers,
      signal: AbortSignal.timeout(Env.TIMEOUT_DEFAULT),
    };

    if (body) {
      config.body = JSON.stringify(body);
    }

    try {
      const response = await fetch(url, config);

      if (!response.ok) {
        const errorText = await response.text().catch(() => 'Unknown Error');
        throw new Error(`API Error (${response.status}): ${errorText}`);
      }

      // Handle empty responses (like 204 No Content)
      if (response.status === 204) return {} as T;

      return await response.json();
    } catch (error) {
      console.error(`[API] ${method} ${path} failed:`, error);
      throw error;
    }
  }

  get<T>(path: string, headers?: Record<string, string>) {
    return this.request<T>('GET', path, undefined, headers);
  }

  post<T>(path: string, body: any, headers?: Record<string, string>) {
    return this.request<T>('POST', path, body, headers);
  }

  put<T>(path: string, body: any, headers?: Record<string, string>) {
    return this.request<T>('PUT', path, body, headers);
  }

  delete<T>(path: string, headers?: Record<string, string>) {
    return this.request<T>('DELETE', path, undefined, headers);
  }
}

export const api = new ApiClient();
