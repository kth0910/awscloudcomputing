'use client';

// ============================================================
// 메트릭 시계열 차트 페이지
// 실험별 리소스 메트릭을 시각화
// ============================================================

import { useEffect, useState, Suspense } from 'react';
import { useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { apiClient } from '@/lib/api-client';
import type { Experiment, ResourceMetric } from '@/lib/types';
import MetricTimelineChart from '@/components/metric-timeline-chart';

function MetricsContent() {
  const searchParams = useSearchParams();
  const preselectedId = searchParams.get('experiment_id');

  const [experiments, setExperiments] = useState<Experiment[]>([]);
  const [selectedId, setSelectedId] = useState<string>(preselectedId || '');
  const [metrics, setMetrics] = useState<ResourceMetric[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // 실험 목록 로딩
  useEffect(() => {
    apiClient.experiments
      .list()
      .then(setExperiments)
      .catch((err) => setError(err.message));
  }, []);

  // 선택된 실험의 메트릭 로딩
  useEffect(() => {
    if (!selectedId) {
      setMetrics([]);
      return;
    }

    setLoading(true);
    setError(null);
    apiClient.metrics
      .get(selectedId)
      .then(setMetrics)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [selectedId]);

  // URL 파라미터로 전달된 실험 ID 자동 선택
  useEffect(() => {
    if (preselectedId) {
      setSelectedId(preselectedId);
    }
  }, [preselectedId]);

  return (
    <div className="space-y-6">
      {/* 헤더 */}
      <h2 className="text-2xl font-bold text-gray-900">메트릭 시각화</h2>

      {/* 실험 선택 */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-5">
        <label className="block text-sm font-medium text-gray-700 mb-2">
          실험 선택
        </label>
        <select
          value={selectedId}
          onChange={(e) => setSelectedId(e.target.value)}
          className="w-full max-w-md border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none"
        >
          <option value="">실험을 선택하세요</option>
          {experiments.map((exp) => (
            <option key={exp.id} value={exp.id}>
              {exp.name} ({exp.status})
            </option>
          ))}
        </select>
      </div>

      {/* 에러 메시지 */}
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded text-sm">
          {error}
        </div>
      )}

      {/* 로딩 */}
      {loading && (
        <div className="flex items-center justify-center h-32">
          <div className="text-gray-500">메트릭 로딩 중...</div>
        </div>
      )}

      {/* 메트릭 차트 */}
      {!loading && selectedId && (
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">
            리소스 메트릭 타임라인
          </h3>
          <MetricTimelineChart metrics={metrics} />
        </div>
      )}

      {/* 실험 미선택 안내 */}
      {!selectedId && !loading && (
        <div className="text-center py-10 text-gray-500 text-sm">
          실험을 선택하면 메트릭 차트가 표시됩니다.
        </div>
      )}
    </div>
  );
}

export default function MetricsPage() {
  return (
    <Suspense fallback={<div className="flex items-center justify-center h-64"><div className="text-gray-500">로딩 중...</div></div>}>
      <MetricsContent />
    </Suspense>
  );
}
