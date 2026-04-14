'use client';

// ============================================================
// 실험 생성 폼 페이지
// ExperimentForm 컴포넌트를 래핑하는 페이지
// ============================================================

import ExperimentForm from '@/components/experiment-form';

export default function NewExperimentPage() {
  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold text-gray-900">새 실험 생성</h2>
      <p className="text-sm text-gray-500">
        AWS 리소스에 장애를 주입하고 AI 페르소나를 통해 UX 임계점을 분석합니다.
      </p>
      <ExperimentForm />
    </div>
  );
}
