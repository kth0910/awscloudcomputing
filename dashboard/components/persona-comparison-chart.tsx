'use client';

// ============================================================
// 페르소나별 비교 차트 컴포넌트
// CSS 기반 바 차트로 이탈 확률, 불만 지수를 시각화
// ============================================================

import type { PersonaInference } from '@/lib/types';
import { PERSONA_LABELS } from '@/lib/types';

interface Props {
  inferences: PersonaInference[];
}

// 페르소나별 색상 매핑
const PERSONA_COLORS: Record<string, { bar: string; bg: string }> = {
  impatient: { bar: 'bg-red-500', bg: 'bg-red-100' },
  meticulous: { bar: 'bg-blue-500', bg: 'bg-blue-100' },
  casual: { bar: 'bg-green-500', bg: 'bg-green-100' },
};

export default function PersonaComparisonChart({ inferences }: Props) {
  // 성공한 추론 결과만 필터링
  const completed = inferences.filter((inf) => inf.status === 'completed');

  if (completed.length === 0) {
    return (
      <div className="text-center text-gray-500 text-sm py-8">
        비교할 추론 결과가 없습니다.
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {/* 이탈 확률 비교 */}
      <div>
        <h4 className="text-sm font-semibold text-gray-700 mb-3">
          이탈 확률 (Churn Probability)
        </h4>
        <div className="space-y-3">
          {completed.map((inf) => {
            const colors = PERSONA_COLORS[inf.persona_type] || {
              bar: 'bg-gray-500',
              bg: 'bg-gray-100',
            };
            const pct = (inf.churn_probability ?? 0) * 100;

            return (
              <div key={`churn-${inf.id}`} className="flex items-center gap-3">
                <span className="text-xs text-gray-600 w-28 shrink-0">
                  {PERSONA_LABELS[inf.persona_type] || inf.persona_type}
                </span>
                <div className={`flex-1 h-6 rounded-full ${colors.bg} overflow-hidden`}>
                  <div
                    className={`h-full rounded-full ${colors.bar} transition-all duration-500`}
                    style={{ width: `${pct}%` }}
                  />
                </div>
                <span className="text-xs font-medium text-gray-700 w-12 text-right">
                  {pct.toFixed(0)}%
                </span>
              </div>
            );
          })}
        </div>
      </div>

      {/* 불만 지수 비교 */}
      <div>
        <h4 className="text-sm font-semibold text-gray-700 mb-3">
          불만 지수 (Frustration Index, 1~10)
        </h4>
        <div className="space-y-3">
          {completed.map((inf) => {
            const colors = PERSONA_COLORS[inf.persona_type] || {
              bar: 'bg-gray-500',
              bg: 'bg-gray-100',
            };
            const pct = ((inf.frustration_index ?? 0) / 10) * 100;

            return (
              <div key={`frust-${inf.id}`} className="flex items-center gap-3">
                <span className="text-xs text-gray-600 w-28 shrink-0">
                  {PERSONA_LABELS[inf.persona_type] || inf.persona_type}
                </span>
                <div className={`flex-1 h-6 rounded-full ${colors.bg} overflow-hidden`}>
                  <div
                    className={`h-full rounded-full ${colors.bar} transition-all duration-500`}
                    style={{ width: `${pct}%` }}
                  />
                </div>
                <span className="text-xs font-medium text-gray-700 w-12 text-right">
                  {inf.frustration_index ?? '-'}/10
                </span>
              </div>
            );
          })}
        </div>
      </div>

      {/* 감정 상태 + 추론 근거 카드 */}
      <div>
        <h4 className="text-sm font-semibold text-gray-700 mb-3">
          감정 상태 및 추론 근거
        </h4>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {completed.map((inf) => {
            const colors = PERSONA_COLORS[inf.persona_type] || {
              bar: 'bg-gray-500',
              bg: 'bg-gray-100',
            };

            return (
              <div
                key={`card-${inf.id}`}
                className={`rounded-lg border p-4 ${colors.bg} border-gray-200`}
              >
                <div className="text-xs text-gray-500 mb-1">
                  {PERSONA_LABELS[inf.persona_type] || inf.persona_type}
                </div>
                <div className="text-lg font-bold text-gray-900 mb-2">
                  {inf.emotion || '-'}
                </div>
                <p className="text-xs text-gray-600 leading-relaxed">
                  {inf.reasoning || '추론 근거 없음'}
                </p>
                {inf.api_latency_ms != null && (
                  <div className="mt-2 text-xs text-gray-400">
                    API 응답: {inf.api_latency_ms.toFixed(0)}ms
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
