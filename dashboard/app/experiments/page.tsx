'use client';

// ============================================================
// 실험 목록 페이지
// 모든 Chaos 실험을 테이블 형태로 표시
// ============================================================

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { apiClient } from '@/lib/api-client';
import type { Experiment } from '@/lib/types';
import { FAULT_TYPE_LABELS } from '@/lib/types';
import ExperimentStatusBadge from '@/components/experiment-status-badge';

export default function ExperimentsPage() {
  const [experiments, setExperiments] = useState<Experiment[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchExperiments = () => {
    setLoading(true);
    apiClient.experiments
      .list()
      .then(setExperiments)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchExperiments();
  }, []);

  // 실험 삭제
  const handleDelete = async (id: string, name: string) => {
    if (!confirm(`"${name}" 실험을 삭제하시겠습니까?`)) return;
    try {
      await apiClient.experiments.delete(id);
      setExperiments((prev) => prev.filter((e) => e.id !== id));
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

  return (
    <div className="space-y-6">
      {/* 헤더 */}
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold text-gray-900">실험 관리</h2>
        <Link
          href="/experiments/new"
          className="px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm font-medium hover:bg-indigo-700 transition-colors"
        >
          + 새 실험 생성
        </Link>
      </div>

      {/* 에러 메시지 */}
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded text-sm">
          {error}
        </div>
      )}

      {/* 실험 테이블 */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
        {experiments.length === 0 ? (
          <div className="px-5 py-10 text-center text-gray-500 text-sm">
            아직 생성된 실험이 없습니다.
          </div>
        ) : (
          <table className="w-full">
            <thead>
              <tr className="text-left text-xs text-gray-500 uppercase bg-gray-50 border-b border-gray-200">
                <th className="px-5 py-3">실험 이름</th>
                <th className="px-5 py-3">대상 리소스</th>
                <th className="px-5 py-3">장애 유형</th>
                <th className="px-5 py-3">지속 시간</th>
                <th className="px-5 py-3">상태</th>
                <th className="px-5 py-3">생성일</th>
                <th className="px-5 py-3">작업</th>
              </tr>
            </thead>
            <tbody>
              {experiments.map((exp) => (
                <tr
                  key={exp.id}
                  className="border-b border-gray-50 hover:bg-gray-50 transition-colors"
                >
                  <td className="px-5 py-3">
                    <Link
                      href={`/experiments/detail?id=${exp.id}`}
                      className="text-sm font-medium text-indigo-600 hover:underline"
                    >
                      {exp.name}
                    </Link>
                  </td>
                  <td className="px-5 py-3 text-sm text-gray-600 font-mono">
                    {exp.target_resource}
                  </td>
                  <td className="px-5 py-3 text-sm text-gray-600">
                    {FAULT_TYPE_LABELS[exp.fault_type]}
                  </td>
                  <td className="px-5 py-3 text-sm text-gray-600">
                    {exp.duration_seconds}초
                  </td>
                  <td className="px-5 py-3">
                    <ExperimentStatusBadge status={exp.status} />
                  </td>
                  <td className="px-5 py-3 text-sm text-gray-500">
                    {new Date(exp.created_at).toLocaleDateString('ko-KR')}
                  </td>
                  <td className="px-5 py-3">
                    <button
                      onClick={() => handleDelete(exp.id, exp.name)}
                      className="text-sm text-red-600 hover:text-red-800 transition-colors"
                    >
                      삭제
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
