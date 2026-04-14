'use client';

import './globals.css';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { ReactNode, useState } from 'react';

// 사이드바 네비게이션 항목 정의
const NAV_ITEMS = [
  { href: '/', label: '대시보드', icon: '📊' },
  { href: '/experiments', label: '실험 관리', icon: '🧪' },
  { href: '/personas', label: '페르소나', icon: '👤' },
  { href: '/metrics', label: '메트릭', icon: '📈' },
];

export default function RootLayout({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const [sidebarOpen, setSidebarOpen] = useState(true);

  return (
    <html lang="ko">
      <body className="min-h-screen flex">
        {/* 사이드바 */}
        <aside
          className={`${
            sidebarOpen ? 'w-60' : 'w-16'
          } bg-gray-900 text-white flex flex-col transition-all duration-200 shrink-0`}
        >
          {/* 로고 영역 */}
          <div className="h-14 flex items-center justify-between px-4 border-b border-gray-700">
            {sidebarOpen && (
              <span className="font-bold text-lg tracking-tight">Chaos Twin</span>
            )}
            <button
              onClick={() => setSidebarOpen(!sidebarOpen)}
              className="text-gray-400 hover:text-white"
              aria-label="사이드바 토글"
            >
              {sidebarOpen ? '◀' : '▶'}
            </button>
          </div>

          {/* 네비게이션 */}
          <nav className="flex-1 py-4 space-y-1">
            {NAV_ITEMS.map((item) => {
              const isActive =
                item.href === '/'
                  ? pathname === '/'
                  : pathname.startsWith(item.href);

              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={`flex items-center gap-3 px-4 py-2.5 text-sm transition-colors ${
                    isActive
                      ? 'bg-indigo-600 text-white'
                      : 'text-gray-300 hover:bg-gray-800 hover:text-white'
                  }`}
                >
                  <span className="text-lg">{item.icon}</span>
                  {sidebarOpen && <span>{item.label}</span>}
                </Link>
              );
            })}
          </nav>

          {/* 하단 정보 */}
          {sidebarOpen && (
            <div className="px-4 py-3 border-t border-gray-700 text-xs text-gray-500">
              AI-Powered Chaos Twin v0.1
            </div>
          )}
        </aside>

        {/* 메인 콘텐츠 영역 */}
        <div className="flex-1 flex flex-col min-h-screen">
          {/* 헤더 */}
          <header className="h-14 bg-white border-b border-gray-200 flex items-center justify-between px-6 shrink-0">
            <h1 className="text-sm font-medium text-gray-600">
              AI-Powered Chaos Engineering Platform
            </h1>
            <div className="flex items-center gap-4">
              <span className="text-xs text-gray-400">
                API: {process.env.NEXT_PUBLIC_API_URL || 'CloudFront Proxy'}
              </span>
              <div className="w-8 h-8 rounded-full bg-indigo-100 flex items-center justify-center text-indigo-600 text-sm font-bold">
                O
              </div>
            </div>
          </header>

          {/* 페이지 콘텐츠 */}
          <main className="flex-1 p-6 overflow-auto">{children}</main>
        </div>
      </body>
    </html>
  );
}
