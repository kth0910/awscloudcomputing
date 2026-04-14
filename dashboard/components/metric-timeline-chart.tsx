'use client';

// ============================================================
// 메트릭 시계열 차트 컴포넌트
// CSS 기반 바 차트로 before/during/after 단계별 메트릭 시각화
// ============================================================

import type { ResourceMetric, MetricPhase } from '@/lib/types';

interface Props {
  metrics: ResourceMetric[];
}

// 단계별 색상 매핑
const PHASE_STYLES: Record<MetricPhase, { bar: string; label: string }> = {
  before: { bar: 'bg-blue-400', label: '장애 주입 전' },
  during: { bar: 'bg-red-400', label: '장애 주입 중' },
  after: { bar: 'bg-green-400', label: '장애 주입 후' },
};

// 단계 순서
const PHASE_ORDER: MetricPhase[] = ['before', 'during', 'after'];

export default function MetricTimelineChart({ metrics }: Props) {
  if (metrics.length === 0) {
    return (
      <div className="text-center text-gray-500 text-sm py-8">
        수집된 메트릭이 없습니다.
      </div>
    );
  }

  // 메트릭 이름별로 그룹화
  const grouped = metrics.reduce<Record<string, ResourceMetric[]>>((acc, m) => {
    const key = `${m.metric_name} (${m.resource_id})`;
    if (!acc[key]) acc[key] = [];
    acc[key].push(m);
    return acc;
  }, {});

  // 각 그룹 내에서 최대값 계산 (바 차트 스케일링용)
  const getMaxValue = (items: ResourceMetric[]) =>
    Math.max(...items.map((m) => m.value), 1);

  return (
    <div className="space-y-8">
      {/* 범례 */}
      <div className="flex items-center gap-4">
        {PHASE_ORDER.map((phase) => (
          <div key={phase} className="flex items-center gap-1.5">
            <div className={`w-3 h-3 rounded ${PHASE_STYLES[phase].bar}`} />
            <span className="text-xs text-gray-600">{PHASE_STYLES[phase].label}</span>
          </div>
        ))}
      </div>

      {/* 메트릭별 차트 */}
      {Object.entries(grouped).map(([metricKey, items]) => {
        const maxVal = getMaxValue(items);

        // 단계별로 정렬
        const sorted = [...items].sort(
          (a, b) =>
            PHASE_ORDER.indexOf(a.phase) - PHASE_ORDER.indexOf(b.phase)
        );

        return (
          <div key={metricKey}>
            <h4 className="text-sm font-semibold text-gray-700 mb-3">
              {metricKey}
            </h4>
            <div className="space-y-2">
              {sorted.map((m) => {
                const pct = (m.value / maxVal) * 100;
                const style = PHASE_STYLES[m.phase];

                return (
                  <div key={m.id} className="flex items-center gap-3">
                    <span className="text-xs text-gray-500 w-24 shrink-0">
                      {style.label}
                    </span>
                    <div className="flex-1 h-7 bg-gray-100 rounded overflow-hidden">
                      <div
                        className={`h-full rounded ${style.bar} transition-all duration-500 flex items-center px-2`}
                        style={{ width: `${Math.max(pct, 2)}%` }}
                      >
                        {pct > 15 && (
                          <span className="text-xs text-white font-medium">
                            {m.value.toFixed(1)}
                          </span>
                        )}
                      </div>
                    </div>
                    <span className="text-xs text-gray-600 w-20 text-right">
                      {m.value.toFixed(2)} {m.unit}
                    </span>
                  </div>
                );
              })}
            </div>

            {/* 시계열 타임라인 (수집 시각 표시) */}
            <div className="mt-2 flex gap-4 text-xs text-gray-400">
              {sorted.map((m) => (
                <span key={`time-${m.id}`}>
                  {PHASE_STYLES[m.phase].label}:{' '}
                  {new Date(m.collected_at).toLocaleTimeString('ko-KR')}
                </span>
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}
