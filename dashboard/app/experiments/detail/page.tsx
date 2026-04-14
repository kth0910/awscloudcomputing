'use client';

// ============================================================
// 실험 상세 페이지 — 쿼리 파라미터 방식 (/experiments/detail?id=xxx)
// ============================================================

import { useEffect, useState, useCallback, useRef, Suspense } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { apiClient } from '@/lib/api-client';
import type { ExperimentDetail } from '@/lib/types';
import { FAULT_TYPE_LABELS } from '@/lib/types';
import ExperimentStatusBadge from '@/components/experiment-status-badge';
import RealtimeStatusIndicator from '@/components/realtime-status-indicator';

// 폴링 간격 (5초)
const POLL_INTERVAL_MS = 5000;

function ExperimentDetailContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const id = searchParams.get('id') || '';

  const [experiment, setExperiment] = useState<ExperimentDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
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

  // 폴링: 실험이 running 상태일 때 5초 간격으로 업데이트
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

  // 실험 실행
  const handleRun = async () => {
    setRunning(true);
    setError(null);
    try {
      await apiClient.experiments.run(id);
      await fetchExperiment();
    } catch (err) {
      setError(err instanceof Error ? err.message : '실행에 실패했습니다.');
    } finally {
      setRunning(false);
    }
  };

  // 실험 삭제
  const handleDelete = async () => {
    if (!confirm('이 실험을 삭제하시겠습니까?')) return;
    try {
      await apiClient.experiments.delete(id);
      router.push('/experiments');
    } catch (err) {
      setError(err instanceof Error ? err.message : '삭제에 실패했습니다.');
    }
  };

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
        <Link href="/experiments" className="text-indigo-600 hover:underline text-sm mt-2 inline-block">
          실험 목록으로 돌아가기
        </Link>
      </div>
    );
  }

  // 페르소나 목록 파싱
  let personaTypes: string[] = [];
  try {
    personaTypes = JSON.parse(experiment.persona_types_json);
  } catch {
    personaTypes = [];
  }

  return (
    <div className="space-y-6">
      {/* 헤더 */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Link href="/experiments" className="text-gray-400 hover:text-gray-600">
            ← 목록
          </Link>
          <h2 className="text-2xl font-bold text-gray-900">{experiment.name}</h2>
          <ExperimentStatusBadge status={experiment.status} />
        </div>
        <div className="flex items-center gap-3">
          <RealtimeStatusIndicator
            status={experiment.status}
            lastPolledAt={lastPolledAt}
            isPolling={isPolling}
          />
          {experiment.status === 'created' && (
            <button
              onClick={handleRun}
              disabled={running}
              className="px-4 py-2 bg-green-600 text-white rounded-lg text-sm font-medium hover:bg-green-700 disabled:opacity-50 transition-colors"
            >
              {running ? '실행 중...' : '▶ 실험 실행'}
            </button>
          )}
          <button
            onClick={handleDelete}
            className="px-4 py-2 bg-white text-red-600 border border-red-300 rounded-lg text-sm font-medium hover:bg-red-50 transition-colors"
          >
            삭제
          </button>
        </div>
      </div>

      {/* 에러 메시지 */}
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded text-sm">
          {error}
        </div>
      )}

      {/* 실험 정보 카드 */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">실험 정보</h3>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
          <InfoItem label="대상 리소스" value={experiment.target_resource} mono />
          <InfoItem label="장애 유형" value={FAULT_TYPE_LABELS[experiment.fault_type]} />
          <InfoItem label="지속 시간" value={`${experiment.duration_seconds}초`} />
          <InfoItem
            label="생성일"
            value={new Date(experiment.created_at).toLocaleString('ko-KR')}
          />
          <InfoItem
            label="시작일"
            value={
              experiment.started_at
                ? new Date(experiment.started_at).toLocaleString('ko-KR')
                : '-'
            }
          />
          <InfoItem
            label="종료일"
            value={
              experiment.ended_at
                ? new Date(experiment.ended_at).toLocaleString('ko-KR')
                : '-'
            }
          />
          <InfoItem label="페르소나" value={personaTypes.join(', ') || '-'} />
        </div>
      </div>

      {/* 장애 주입 결과 */}
      {experiment.results.length > 0 && (
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">장애 주입 결과</h3>
          <div className="space-y-3">
            {experiment.results.map((result) => (
              <div
                key={result.id}
                className="border border-gray-100 rounded-lg p-4 flex items-center justify-between"
              >
                <div>
                  <span className="text-sm font-medium text-gray-900">
                    {FAULT_TYPE_LABELS[result.fault_type as keyof typeof FAULT_TYPE_LABELS] || result.fault_type}
                  </span>
                  <span className="text-xs text-gray-500 ml-2">
                    {result.target_resource}
                  </span>
                </div>
                <ExperimentStatusBadge status={result.status as any} />
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 결과 페이지 링크 */}
      {(experiment.status === 'completed' || experiment.persona_inferences.length > 0) && (
        <div className="flex gap-3">
          <Link
            href={`/experiments/results?id=${id}`}
            className="px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm font-medium hover:bg-indigo-700 transition-colors"
          >
            📊 AI 추론 결과 보기
          </Link>
          <Link
            href={`/metrics?experiment_id=${id}`}
            className="px-4 py-2 bg-white text-indigo-600 border border-indigo-300 rounded-lg text-sm font-medium hover:bg-indigo-50 transition-colors"
          >
            📈 메트릭 보기
          </Link>
        </div>
      )}
    </div>
  );
}

/** 정보 항목 컴포넌트 */
function InfoItem({
  label,
  value,
  mono,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div>
      <div className="text-xs text-gray-500 mb-0.5">{label}</div>
      <div className={`text-sm text-gray-900 ${mono ? 'font-mono' : ''}`}>
        {value}
      </div>
    </div>
  );
}

export default function ExperimentDetailPage() {
  return (
    <Suspense fallback={<div className="flex items-center justify-center h-64"><div className="text-gray-500">로딩 중...</div></div>}>
      <ExperimentDetailContent />
    </Suspense>
  );
}
