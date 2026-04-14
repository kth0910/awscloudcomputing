'use client';

// ============================================================
// 페르소나 관리 페이지
// AI 페르소나 목록 및 상세 정보 표시
// ============================================================

import { useEffect, useState } from 'react';
import { apiClient } from '@/lib/api-client';
import type { Persona, PersonaType } from '@/lib/types';
import { PERSONA_LABELS } from '@/lib/types';

// 페르소나별 아이콘/색상 매핑
const PERSONA_STYLES: Record<
  PersonaType,
  { icon: string; color: string; bgColor: string }
> = {
  impatient: {
    icon: '⚡',
    color: 'text-red-700',
    bgColor: 'bg-red-50 border-red-200',
  },
  meticulous: {
    icon: '🔍',
    color: 'text-blue-700',
    bgColor: 'bg-blue-50 border-blue-200',
  },
  casual: {
    icon: '😊',
    color: 'text-green-700',
    bgColor: 'bg-green-50 border-green-200',
  },
};

// API 실패 시 기본 페르소나 데이터 (오프라인 폴백)
const DEFAULT_PERSONAS: Persona[] = [
  {
    type: 'impatient',
    name: '성격 급한 유저',
    traits: '매우 참을성이 없고, 즉각적인 응답을 기대함',
    tech_level: '중급',
    patience_level: '매우 낮음 (3초 이상 대기 시 불만)',
    expected_response_time: '1초 이내',
  },
  {
    type: 'meticulous',
    name: '꼼꼼한 유저',
    traits: '체계적이고 세밀하며, 오류 메시지를 꼼꼼히 읽음',
    tech_level: '고급',
    patience_level: '보통 (10초까지 대기 가능)',
    expected_response_time: '5초 이내',
  },
  {
    type: 'casual',
    name: '일반 유저',
    traits: '가볍게 서비스를 이용하며, 기술적 세부사항에 관심 없음',
    tech_level: '초급',
    patience_level: '보통 (5초까지 대기 가능)',
    expected_response_time: '3초 이내',
  },
];

export default function PersonasPage() {
  const [personas, setPersonas] = useState<Persona[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiClient.personas
      .list()
      .then(setPersonas)
      .catch(() => {
        // API 실패 시 기본 데이터 사용
        setPersonas(DEFAULT_PERSONAS);
      })
      .finally(() => setLoading(false));
  }, []);

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
      <div>
        <h2 className="text-2xl font-bold text-gray-900">AI 페르소나 관리</h2>
        <p className="text-sm text-gray-500 mt-1">
          Gemini AI 기반 가상 사용자 페르소나. 장애 상황에서의 사용자 심리 상태를
          추론합니다.
        </p>
      </div>

      {/* 페르소나 카드 목록 */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {personas.map((persona) => {
          const style = PERSONA_STYLES[persona.type] || {
            icon: '👤',
            color: 'text-gray-700',
            bgColor: 'bg-gray-50 border-gray-200',
          };

          return (
            <div
              key={persona.type}
              className={`rounded-xl border p-6 ${style.bgColor}`}
            >
              {/* 아이콘 + 이름 */}
              <div className="flex items-center gap-3 mb-4">
                <span className="text-3xl">{style.icon}</span>
                <div>
                  <h3 className={`text-lg font-bold ${style.color}`}>
                    {persona.name}
                  </h3>
                  <span className="text-xs text-gray-500 uppercase">
                    {persona.type}
                  </span>
                </div>
              </div>

              {/* 특성 정보 */}
              <div className="space-y-3">
                <InfoRow label="성격 특성" value={persona.traits} />
                <InfoRow label="기술 숙련도" value={persona.tech_level} />
                <InfoRow label="인내심 수준" value={persona.patience_level} />
                <InfoRow
                  label="기대 응답 시간"
                  value={persona.expected_response_time}
                />
              </div>
            </div>
          );
        })}
      </div>

      {/* 설명 */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-3">
          페르소나 시스템 안내
        </h3>
        <div className="text-sm text-gray-600 space-y-2">
          <p>
            각 페르소나는 Chaos 실험 실행 시 Gemini AI에 전달되는 프롬프트
            템플릿을 기반으로 동작합니다.
          </p>
          <p>
            장애 상황의 컨텍스트(서비스명, 장애 유형, 지속 시간, 영향 범위)와
            페르소나의 성격 특성을 결합하여 심리 상태를 추론합니다.
          </p>
          <p>
            추론 결과에는 감정 상태, 이탈 확률(0.0~1.0), 불만 지수(1~10), 추론
            근거가 포함됩니다.
          </p>
        </div>
      </div>
    </div>
  );
}

/** 정보 행 컴포넌트 */
function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-xs text-gray-500">{label}</div>
      <div className="text-sm text-gray-800">{value}</div>
    </div>
  );
}
