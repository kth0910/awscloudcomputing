// ============================================================
// Core Engine API 클라이언트
// ALB 엔드포인트를 통해 Core Engine과 통신
// ============================================================

import type {
  Experiment,
  ExperimentCreate,
  ExperimentDetail,
  ExperimentResult,
  Persona,
  ResourceMetric,
  RunConfig,
  UserProfile,
  ProfileUpdate,
} from './types';

import { fetchAuthSession } from 'aws-amplify/auth';

// ALB DNS 엔드포인트 — 상대 경로 사용 (CloudFront에서 /api/* → ALB 프록시)
const API_BASE = process.env.NEXT_PUBLIC_API_URL || '';

/** 현재 세션의 ID 토큰을 가져온다 */
async function getIdToken(): Promise<string | null> {
  try {
    const session = await fetchAuthSession();
    return session.tokens?.idToken?.toString() ?? null;
  } catch {
    return null;
  }
}

/** 공통 fetch 래퍼 (에러 처리 + Bearer JWT 헤더 포함) */
async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };

  const idToken = await getIdToken();
  if (idToken) {
    headers['Authorization'] = `Bearer ${idToken}`;
  }

  const res = await fetch(`${API_BASE}${url}`, {
    headers,
    ...options,
  });

  if (!res.ok) {
    const errorBody = await res.text().catch(() => '');
    throw new Error(`API 오류 (${res.status}): ${errorBody || res.statusText}`);
  }

  // 204 No Content 등 빈 응답 처리
  if (res.status === 204 || res.status === 202) {
    return null as T;
  }

  return res.json();
}

/** API 클라이언트 */
export const apiClient = {
  // 실험 관련 API
  experiments: {
    /** 실험 목록 조회 */
    list: () => request<Experiment[]>('/api/experiments'),

    /** 실험 상세 조회 */
    get: (id: string) => request<ExperimentDetail>(`/api/experiments/${id}`),

    /** 실험 생성 */
    create: (data: ExperimentCreate) =>
      request<Experiment>('/api/experiments', {
        method: 'POST',
        body: JSON.stringify(data),
      }),

    /** 실험 실행 */
    run: (id: string, config?: RunConfig) =>
      request<null>(`/api/experiments/${id}/run`, {
        method: 'POST',
        body: config ? JSON.stringify(config) : undefined,
      }),

    /** 실험 삭제 */
    delete: (id: string) =>
      request<null>(`/api/experiments/${id}`, { method: 'DELETE' }),
  },

  // 실험 결과 API
  results: {
    /** 실험 결과 조회 */
    get: (experimentId: string) =>
      request<ExperimentResult[]>(`/api/experiments/${experimentId}/results`),
  },

  // 메트릭 API
  metrics: {
    /** 실험 메트릭 조회 */
    get: (experimentId: string) =>
      request<ResourceMetric[]>(`/api/experiments/${experimentId}/metrics`),
  },

  // 페르소나 API
  personas: {
    /** 페르소나 목록 조회 */
    list: () => request<Persona[]>('/api/personas'),
  },

  // 프로필 API
  profile: {
    /** 프로필 조회 */
    get: () => request<UserProfile>('/api/profile'),

    /** 프로필 등록/수정 */
    update: (data: ProfileUpdate) =>
      request<UserProfile>('/api/profile', {
        method: 'PUT',
        body: JSON.stringify(data),
      }),
  },
};
