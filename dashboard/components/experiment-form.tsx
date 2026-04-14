'use client';

// ============================================================
// 실험 생성/편집 폼 컴포넌트
// 새로운 Chaos 실험을 생성하기 위한 폼 UI
// ============================================================

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { apiClient } from '@/lib/api-client';
import type { ExperimentCreate, FaultType, PersonaType } from '@/lib/types';
import { FAULT_TYPE_LABELS, PERSONA_LABELS } from '@/lib/types';

// 장애 유형 옵션
const FAULT_OPTIONS: FaultType[] = ['ec2_stop', 'sg_port_block', 'rds_delay'];

// 페르소나 유형 옵션
const PERSONA_OPTIONS: PersonaType[] = ['impatient', 'meticulous', 'casual'];

export default function ExperimentForm() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // 폼 상태
  const [name, setName] = useState('');
  const [targetResource, setTargetResource] = useState('');
  const [faultType, setFaultType] = useState<FaultType>('ec2_stop');
  const [durationSeconds, setDurationSeconds] = useState(300);
  const [selectedPersonas, setSelectedPersonas] = useState<PersonaType[]>([
    'impatient',
    'meticulous',
    'casual',
  ]);

  // 페르소나 토글
  const togglePersona = (persona: PersonaType) => {
    setSelectedPersonas((prev) =>
      prev.includes(persona)
        ? prev.filter((p) => p !== persona)
        : [...prev, persona]
    );
  };

  // 폼 제출
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (selectedPersonas.length === 0) {
      setError('최소 1개의 페르소나를 선택해야 합니다.');
      return;
    }

    setLoading(true);
    try {
      const data: ExperimentCreate = {
        name,
        target_resource: targetResource,
        fault_type: faultType,
        duration_seconds: durationSeconds,
        persona_types: selectedPersonas,
      };
      const created = await apiClient.experiments.create(data);
      router.push(`/experiments/detail?id=${created.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : '실험 생성에 실패했습니다.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-6 max-w-2xl">
      {/* 에러 메시지 */}
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded text-sm">
          {error}
        </div>
      )}

      {/* 실험 이름 */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          실험 이름
        </label>
        <input
          type="text"
          required
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="예: EC2 중지 복원력 테스트"
          className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none"
        />
      </div>

      {/* 대상 리소스 */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          대상 AWS 리소스 ID
        </label>
        <input
          type="text"
          required
          value={targetResource}
          onChange={(e) => setTargetResource(e.target.value)}
          placeholder="예: i-0abc123def456"
          className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none"
        />
      </div>

      {/* 장애 유형 */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          장애 유형
        </label>
        <select
          value={faultType}
          onChange={(e) => setFaultType(e.target.value as FaultType)}
          className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none"
        >
          {FAULT_OPTIONS.map((ft) => (
            <option key={ft} value={ft}>
              {FAULT_TYPE_LABELS[ft]}
            </option>
          ))}
        </select>
      </div>

      {/* 지속 시간 */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          장애 지속 시간 (초)
        </label>
        <input
          type="number"
          min={1}
          max={3600}
          value={durationSeconds}
          onChange={(e) => setDurationSeconds(Number(e.target.value))}
          className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none"
        />
        <p className="text-xs text-gray-500 mt-1">
          기본 300초 (5분). 최대 3600초 (1시간).
        </p>
      </div>

      {/* 페르소나 선택 */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          AI 페르소나 선택
        </label>
        <div className="flex gap-3">
          {PERSONA_OPTIONS.map((persona) => (
            <button
              key={persona}
              type="button"
              onClick={() => togglePersona(persona)}
              className={`px-4 py-2 rounded-lg text-sm border transition-colors ${
                selectedPersonas.includes(persona)
                  ? 'bg-indigo-600 text-white border-indigo-600'
                  : 'bg-white text-gray-700 border-gray-300 hover:border-indigo-400'
              }`}
            >
              {PERSONA_LABELS[persona]}
            </button>
          ))}
        </div>
      </div>

      {/* 제출 버튼 */}
      <div className="flex gap-3">
        <button
          type="submit"
          disabled={loading}
          className="px-6 py-2.5 bg-indigo-600 text-white rounded-lg text-sm font-medium hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {loading ? '생성 중...' : '실험 생성'}
        </button>
        <button
          type="button"
          onClick={() => router.back()}
          className="px-6 py-2.5 bg-white text-gray-700 border border-gray-300 rounded-lg text-sm font-medium hover:bg-gray-50 transition-colors"
        >
          취소
        </button>
      </div>
    </form>
  );
}
