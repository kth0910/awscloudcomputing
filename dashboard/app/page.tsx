'use client';

// ============================================================
// 대시보드 홈 페이지
// 실험 요약 통계 및 최근 실험 목록 표시
// ============================================================

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { apiClient } from '@/lib/api-client';
import type { Experiment, ExperimentStatus } from '@/lib/types';
import { FAULT_TYPE_LABELS } from '@/lib/types';
import ExperimentStatusBadge from '@/components/experiment-status-badge';

export default function DashboardHome() {
  const [experiments, setExperiments] = useState<Experiment[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiClient.experiments
      .list()
      .then(setExperiments)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  // 상태별 실험 수 집계
  const statusCounts = experiments.reduce<Record<string, number>>((acc, exp) => {
    acc[exp.status] = (acc[exp.status] || 0) + 1;
    return acc;
  }, {});

  // 요약 카드 데이터
  const summaryCards = [
    { label: '전체 실험', value: experiments.length, color: 'bg-indigo-500' },
    { label: '실행 중', value: statusCounts['running'] || 0, color: 'bg-blue-500' },
    { label: '완료', value: statusCounts['completed'] || 0, color: 'bg-green-500' },
    { label: '실패', value: statusCounts['failed'] || 0, color: 'bg-red-500' },
  ];

  // 최근 5개 실험
  const recentExperiments = [...experiments]
    .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
    .slice(0, 5);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-gray-500">로딩 중...</div>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {/* 페이지 제목 */}
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold text-gray-900">대시보드</h2>
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

      {/* 요약 카드 */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {summaryCards.map((card) => (
          <div
            key={card.label}
            className="bg-white rounded-xl shadow-sm border border-gray-200 p-5"
          >
            <div className="flex items-center gap-3">
              <div className={`w-3 h-3 rounded-full ${card.color}`} />
              <span className="text-sm text-gray-500">{card.label}</span>
            </div>
            <div className="mt-2 text-3xl font-bold text-gray-900">{card.value}</div>
          </div>
        ))}
      </div>

      {/* 최근 실험 목록 */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200">
        <div className="px-5 py-4 border-b border-gray-200">
          <h3 className="text-lg font-semibold text-gray-900">최근 실험</h3>
        </div>
        {recentExperiments.length === 0 ? (
          <div className="px-5 py-10 text-center text-gray-500 text-sm">
            아직 생성된 실험이 없습니다.{' '}
            <Link href="/experiments/new" className="text-indigo-600 hover:underline">
              첫 실험을 생성해보세요.
            </Link>
          </div>
        ) : (
          <table className="w-full">
            <thead>
              <tr className="text-left text-xs text-gray-500 uppercase border-b border-gray-100">
                <th className="px-5 py-3">실험 이름</th>
                <th className="px-5 py-3">장애 유형</th>
                <th className="px-5 py-3">상태</th>
                <th className="px-5 py-3">생성일</th>
              </tr>
            </thead>
            <tbody>
              {recentExperiments.map((exp) => (
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
                  <td className="px-5 py-3 text-sm text-gray-600">
                    {FAULT_TYPE_LABELS[exp.fault_type]}
                  </td>
                  <td className="px-5 py-3">
                    <ExperimentStatusBadge status={exp.status} />
                  </td>
                  <td className="px-5 py-3 text-sm text-gray-500">
                    {new Date(exp.created_at).toLocaleDateString('ko-KR')}
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
