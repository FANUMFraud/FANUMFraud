'use client';

import { useI18n } from '@/lib/i18n/I18nProvider';

interface Props {
  show: boolean;
  scoreDelta?: number;
}

export default function AlertBanner({ show, scoreDelta }: Props) {
  const { t } = useI18n();
  if (!show) return null;

  const deltaText =
    scoreDelta != null ? t.alert.points(scoreDelta) : t.alert.fallbackDelta;

  return (
    <aside
      role="status"
      className="border-l-4 flex gap-4 items-start"
      style={{
        borderLeftColor: 'var(--crimson)',
        background: 'var(--crimson-soft)',
        borderTop: '1px solid var(--risk-high-rule)',
        borderRight: '1px solid var(--risk-high-rule)',
        borderBottom: '1px solid var(--risk-high-rule)',
        padding: '14px 18px',
      }}
    >
      <div className="shrink-0 mt-0.5">
        <svg
          xmlns="http://www.w3.org/2000/svg"
          className="w-5 h-5"
          style={{ color: 'var(--crimson)' }}
          fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.2}
        >
          <path strokeLinecap="round" strokeLinejoin="round"
            d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z"
          />
        </svg>
      </div>
      <div>
        <p
          className="font-semibold text-[12px] uppercase tracking-[0.14em]"
          style={{ color: 'var(--crimson-2)' }}
        >
          {t.alert.title}
        </p>
        <p className="text-sm mt-1 leading-relaxed" style={{ color: 'var(--ink-2)' }}>
          {t.alert.body(deltaText)}
        </p>
      </div>
    </aside>
  );
}
