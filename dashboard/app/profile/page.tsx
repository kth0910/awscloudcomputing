'use client';

import { useEffect, useState } from 'react';
import { apiClient } from '../../lib/api-client';
import type { UserProfile, ProfileUpdate } from '../../lib/types';

export default function ProfilePage() {
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const [awsAccountId, setAwsAccountId] = useState('');
  const [roleArn, setRoleArn] = useState('');
  const [probeEndpoint, setProbeEndpoint] = useState('');

  useEffect(() => {
    loadProfile();
  }, []);

  async function loadProfile() {
    try {
      const data = await apiClient.profile.get();
      setProfile(data);
      setAwsAccountId(data.aws_account_id ?? '');
      setRoleArn(data.cross_account_role_arn ?? '');
      setProbeEndpoint(data.probe_endpoint ?? '');
    } catch (e) {
      setError('프로필을 불러올 수 없습니다.');
    } finally {
      setLoading(false);
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSuccess(null);
    setSaving(true);

    try {
      const update: ProfileUpdate = {
        aws_account_id: awsAccountId,
        cross_account_role_arn: roleArn,
        probe_endpoint: probeEndpoint || undefined,
      };
      const data = await apiClient.profile.update(update);
      setProfile(data);
      setSuccess('프로필이 저장되었습니다.');
    } catch (e: any) {
      setError(e.message || '프로필 저장에 실패했습니다.');
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return <div className="text-gray-500">로딩 중...</div>;
  }

  return (
    <div className="max-w-2xl">
      <h2 className="text-xl font-bold mb-6">프로필 설정</h2>

      {profile?.role_verified && (
        <div className="mb-4 p-3 bg-green-50 border border-green-200 rounded text-green-700 text-sm">
          ✅ Cross-Account Role이 검증되었습니다.
        </div>
      )}

      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded text-red-700 text-sm">
          {error}
        </div>
      )}

      {success && (
        <div className="mb-4 p-3 bg-blue-50 border border-blue-200 rounded text-blue-700 text-sm">
          {success}
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-5">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            AWS Account ID (12자리)
          </label>
          <input
            type="text"
            value={awsAccountId}
            onChange={(e) => setAwsAccountId(e.target.value)}
            pattern="\d{12}"
            maxLength={12}
            required
            className="w-full border border-gray-300 rounded px-3 py-2 text-sm"
            placeholder="123456789012"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Cross-Account Role ARN
          </label>
          <input
            type="text"
            value={roleArn}
            onChange={(e) => setRoleArn(e.target.value)}
            required
            className="w-full border border-gray-300 rounded px-3 py-2 text-sm"
            placeholder="arn:aws:iam::123456789012:role/ChaosTwin-ChaosAccess"
          />
          <p className="mt-1 text-xs text-gray-500">
            Role 이름은 <code>ChaosTwin-</code> 접두사로 시작해야 합니다.
          </p>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Probe Endpoint (선택)
          </label>
          <input
            type="url"
            value={probeEndpoint}
            onChange={(e) => setProbeEndpoint(e.target.value)}
            className="w-full border border-gray-300 rounded px-3 py-2 text-sm"
            placeholder="https://your-service.example.com/health"
          />
          <p className="mt-1 text-xs text-gray-500">
            장애 주입 전/중/후에 프로빙하여 UX 메트릭을 수집합니다.
          </p>
        </div>

        <button
          type="submit"
          disabled={saving}
          className="bg-indigo-600 text-white px-4 py-2 rounded text-sm hover:bg-indigo-700 disabled:opacity-50"
        >
          {saving ? '저장 중...' : '저장'}
        </button>
      </form>

      <div className="mt-8 p-4 bg-gray-50 border border-gray-200 rounded text-sm text-gray-600">
        <h3 className="font-medium mb-2">Trust Policy 설정 안내</h3>
        <p className="mb-2">
          대상 AWS 계정에서 아래 trust policy를 가진 IAM Role을 생성하세요:
        </p>
        <pre className="bg-gray-900 text-green-400 p-3 rounded text-xs overflow-x-auto">
{`{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "AWS": "<Chaos Injector Lambda Role ARN>"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}`}
        </pre>
      </div>
    </div>
  );
}
