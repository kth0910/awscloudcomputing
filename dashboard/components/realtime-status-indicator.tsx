'use client';

// ============================================================
// 실시간 상태 표시기 컴포넌트
// 실험이 실행 중일 때 폴링 상태를 시각적으로 표시
// ============================================================

import type { ExperimentStatus } from '@/lib/types';

interface Props {
  status: ExperimentStatus;
  /** 마지막 폴링 시각 */
  lastPolledAt: Date | null;
  /** 폴링 활성 여부 */
  isPolling: boolean;
}

export default function RealtimeStatusIndicator({
  status,
  lastPolledAt,
  isPolling,
}: Props) {
  // 실행 중이 아니면 폴링 불필요
  if (status !== 'running') {
    return null;
  }

  return (
    <div className="flex items-center gap-2 text-xs text-blue-600 bg-blue-50 px-3 py-1.5 rounded-full">
      {/* 깜빡이는 점 */}
      <span className="relative flex h-2 w-2">
        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75" />
        <span className="relative inline-flex rounded-full h-2 w-2 bg-blue-500" />
      </span>

      <span>
        {isPolling ? '실시간 업데이트 중' : '폴링 대기 중'}
        {lastPolledAt && (
          <span className="text-blue-400 ml-1">
            (마지막: {lastPolledAt.toLocaleTimeString('ko-KR')})
          </span>
        )}
      </span>
    </div>
  );
}
