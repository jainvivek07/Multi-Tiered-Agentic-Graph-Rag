import { apiFetch } from './client';
import type { DashboardMetrics } from '../types/api';

const PREFIX = '/api/v1/admin';
const ORIGIN = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';

export const adminApi = {
  getMetrics: (): Promise<DashboardMetrics> =>
    apiFetch<DashboardMetrics>(`${PREFIX}/metrics`),

  uploadDocument: async (
    file: File,
    category: string,
  ): Promise<{ document_id: string; status: string }> => {
    const form = new FormData();
    form.append('file', file);
    form.append('category', category);

    const res = await fetch(`${ORIGIN}${PREFIX}/ingest`, {
      method: 'POST',
      credentials: 'include',
      body: form,
      // Do NOT set Content-Type — browser sets it with the correct multipart boundary.
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error((err as { detail?: string }).detail ?? `HTTP ${res.status}`);
    }
    return res.json();
  },

  getUsers: () => apiFetch<any[]>(`${PREFIX}/users`),
  
  updateUserStatus: async (userId: string, isActive: boolean) => {
    const form = new FormData();
    form.append('is_active', isActive.toString());

    const res = await fetch(`${ORIGIN}${PREFIX}/users/${userId}/active`, {
      method: 'PUT',
      credentials: 'include',
      body: form,
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error((err as { detail?: string }).detail ?? `HTTP ${res.status}`);
    }
    return res.json();
  },

  updateUserRole: async (userId: string, role: string) => {
    const form = new FormData();
    form.append('role', role);

    const res = await fetch(`${ORIGIN}${PREFIX}/users/${userId}/role`, {
      method: 'PUT',
      credentials: 'include',
      body: form,
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error((err as { detail?: string }).detail ?? `HTTP ${res.status}`);
    }
    return res.json();
  },

  deleteCategory: async (category: string) => {
    const res = await fetch(`${ORIGIN}${PREFIX}/categories/${encodeURIComponent(category)}`, {
      method: 'DELETE',
      credentials: 'include',
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error((err as { detail?: string }).detail ?? `HTTP ${res.status}`);
    }
    return res.json();
  },

  getGraph: (category?: string) => 
    apiFetch<any>(`${PREFIX}/graph${category ? `?category=${category}` : ''}`),

  listCategoryDocuments: (category: string): Promise<any[]> =>
    apiFetch<any[]>(`${PREFIX}/categories/${encodeURIComponent(category)}/documents`),

  deleteDocument: async (docId: string): Promise<{ message: string }> => {
    const res = await fetch(`${ORIGIN}${PREFIX}/documents/${docId}`, {
      method: 'DELETE',
      credentials: 'include',
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error((err as { detail?: string }).detail ?? `HTTP ${res.status}`);
    }
    return res.json();
  },

  /** Returns the URL to open/stream the original uploaded file (admin-only, cookie-auth). */
  getDocumentFileUrl: (docId: string): string =>
    `${ORIGIN}${PREFIX}/documents/${docId}/file`,
};
