'use client';

// ============================================================
// 실험 결과 + AI 추론 비교 페이지 — 쿼리 파라미터 방식 (/experiments/results?id=xxx)
// 페르소나별 추론 결과를 차트와 카드로 시각화
// ============================================================

import { useEffect, useState, useCallback, useRef, Suspense } from 'react';
import { useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { apiClient } from '@/lib/api-client';
import type { ExperimentDetail } from '@/lib/types';
import { FAULT_TYPE_LABELS } from '@/lib/types';
import ExperimentStatusBadge from '@/components/experiment-status-badge';
import PersonaComparisonChart from '@/components/persona-comparison-chart';
import RealtimeStatusIndicator from '@/components/realtime-status-indicator';

// 폴링 간격 (5초)
const POLL_INTERVAL_MS = 5000;

function ExperimentResultsContent() {
  const searchParams = useSearchParams();
  const id = searchParams.get('id') || '';

  const [experiment, setExperiment] = useState<ExperimentDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastPolledAt, setLastPolledAt] = useState<Date | null>(null);
  const [isPolling, setIsPolling] = useState(false);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // 실험 데이터 조회
  const fetchExperiment = useCallback(async () => {
    if (!id) return null;
    try {
      const data = await apiClient.experiments.get(id);
      setExperiment(data);
      setLastPolledAt(new Date());
      return data;
    } catch (err) {
      setError(err instanceof Error ? err.message : '조회에 실패했습니다.');
      return null;
    }
  }, [id]);

  // 초기 로딩
  useEffect(() => {
    if (!id) {
      setLoading(false);
      setError('실험 ID가 지정되지 않았습니다.');
      return;
    }
    fetchExperiment().finally(() => setLoading(false));
  }, [id, fetchExperiment]);

  // 폴링: running 상태일 때 5초 간격 업데이트
  useEffect(() => {
    if (experiment?.status === 'running') {
      setIsPolling(true);
      intervalRef.current = setInterval(async () => {
        const data = await fetchExperiment();
        if (data && data.status !== 'running') {
          if (intervalRef.current) clearInterval(intervalRef.current);
          setIsPolling(false);
        }
      }, POLL_INTERVAL_MS);
    } else {
      setIsPolling(false);
    }

    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [experiment?.status, fetchExperiment]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-gray-500">로딩 중...</div>
      </div>
    );
  }

  if (!experiment) {
    return (
      <div className="text-center py-10">
        <p className="text-gray-500">실험을 찾을 수 없습니다.</p>
      </div>
    );
  }

  // 실패한 추론 결과
  const failedInferences = experiment.persona_inferences.filter(
    (inf) => inf.status === 'inference_failed'
  );

  return (
    <div className="space-y-6">
      {/* 헤더 */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Link
            href={`/experiments/detail?id=${id}`}
            className="text-gray-400 hover:text-gray-600"
          >
            ← 실험 상세
          </Link>
          <h2 className="text-2xl font-bold text-gray-900">AI 추론 결과</h2>
          <ExperimentStatusBadge status={experiment.status} />
        </div>
        <RealtimeStatusIndicator
          status={experiment.status}
          lastPolledAt={lastPolledAt}
          isPolling={isPolling}
        />
      </div>

      {/* 에러 메시지 */}
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded text-sm">
          {error}
        </div>
      )}

      {/* 실험 요약 */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-5">
        <div className="flex items-center gap-6 text-sm text-gray-600">
          <span>
            실험: <strong className="text-gray-900">{experiment.name}</strong>
          </span>
          <span>
            장애 유형:{' '}
            <strong className="text-gray-900">
              {FAULT_TYPE_LABELS[experiment.fault_type]}
            </strong>
          </span>
          <span>
            대상: <code className="text-gray-900">{experiment.target_resource}</code>
          </span>
        </div>
      </div>

      {/* 페르소나 비교 차트 */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">
          페르소나별 비교 분석
        </h3>
        <PersonaComparisonChart inferences={experiment.persona_inferences} />
      </div>

      {/* 실패한 추론 결과 */}
      {failedInferences.length > 0 && (
        <div className="bg-yellow-50 rounded-xl border border-yellow-200 p-6">
          <h3 className="text-lg font-semibold text-yellow-800 mb-3">
            ⚠ 추론 실패 ({failedInferences.length}건)
          </h3>
          <div className="space-y-2">
            {failedInferences.map((inf) => (
              <div
                key={inf.id}
                className="text-sm text-yellow-700 bg-yellow-100 rounded px-3 py-2"
              >
                <strong>{inf.persona_type}</strong>:{' '}
                {inf.failure_reason || '알 수 없는 오류'}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 장애 주입 결과 상세 */}
      {experiment.results.length > 0 && (
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">
            장애 주입 결과 상세
          </h3>
          <div className="space-y-3">
            {experiment.results.map((result) => (
              <div
                key={result.id}
                className="border border-gray-100 rounded-lg p-4"
              >
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-medium text-gray-900">
                    {result.fault_type} → {result.target_resource}
                  </span>
                  <ExperimentStatusBadge status={result.status as any} />
                </div>
                <div className="grid grid-cols-2 gap-2 text-xs text-gray-500">
                  <span>
                    시작:{' '}
                    {result.chaos_started_at
                      ? new Date(result.chaos_started_at).toLocaleString('ko-KR')
                      : '-'}
                  </span>
                  <span>
                    종료:{' '}
                    {result.chaos_ended_at
                      ? new Date(result.chaos_ended_at).toLocaleString('ko-KR')
                      : '-'}
                  </span>
                </div>
                {result.error_detail && (
                  <div className="mt-2 text-xs text-red-600 bg-red-50 rounded px-2 py-1">
                    {result.error_detail}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export default function ExperimentResultsPage() {
  return (
    <Suspense fallback={<div className="flex items-center justify-center h-64"><div className="text-gray-500">로딩 중...</div></div>}>
      <ExperimentResultsContent />
    </Suspense>
  );
}
