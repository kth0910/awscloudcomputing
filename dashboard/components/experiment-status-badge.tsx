'use client';

// ============================================================
// 실험 상태 뱃지 컴포넌트
// 실험 상태에 따라 색상이 다른 뱃지를 렌더링
// ============================================================

import type { ExperimentStatus } from '@/lib/types';
import { STATUS_LABELS } from '@/lib/types';

// 상태별 스타일 매핑
const STATUS_STYLES: Record<ExperimentStatus, string> = {
  created: 'bg-gray-100 text-gray-700',
  running: 'bg-blue-100 text-blue-700 animate-pulse',
  completed: 'bg-green-100 text-green-700',
  failed: 'bg-red-100 text-red-700',
  cancelled: 'bg-yellow-100 text-yellow-700',
  probe_failed: 'bg-orange-100 text-orange-700',
};

interface Props {
  status: ExperimentStatus;
}

export default function ExperimentStatusBadge({ status }: Props) {
  return (
    <span
      className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
        STATUS_STYLES[status] || 'bg-gray-100 text-gray-700'
      }`}
    >
      {STATUS_LABELS[status] || status}
    </span>
  );
}
