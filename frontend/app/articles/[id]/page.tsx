'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import Header from '@/components/Header';
import LocaleFade from '@/components/LocaleFade';
import { getArticle, type Article } from '@/lib/api';
import { useI18n } from '@/lib/i18n/I18nProvider';

function splitParagraphs(content: string | null | undefined): string[] {
  if (!content) return [];
  return content
    .split(/\n{2,}/)
    .map((part) => part.trim())
    .filter(Boolean);
}

export default function ArticlePage() {
  const params = useParams();
  const router = useRouter();
  const { t, formatDate, locale } = useI18n();
  const id = params.id as string;

  const [article, setArticle] = useState<Article | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchArticle = async () => {
      try {
        setLoading(true);
        setError(null);
        setArticle(await getArticle(Number(id)));
      } catch (e) {
        setError(locale === 'pl' ? 'Nie udalo sie zaladowac artykulu.' : 'Could not load article.');
        console.error(e);
      } finally {
        setLoading(false);
      }
    };

    fetchArticle();
  }, [id, locale]);

  const paragraphs = useMemo(() => splitParagraphs(article?.content), [article?.content]);

  const backButton = (
    <button
      onClick={() => router.back()}
      className="inline-flex items-center gap-1.5 text-[12px] uppercase tracking-[0.08em] font-semibold text-[var(--ink)] hover:text-[var(--link)] transition-colors"
    >
      <svg xmlns="http://www.w3.org/2000/svg" className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
      </svg>
      {t.nav.back}
    </button>
  );

  if (loading) {
    return (
      <div className="min-h-screen flex flex-col">
        <Header leftSlot={backButton} />
        <main className="flex-1 max-w-4xl mx-auto w-full px-4 sm:px-6 lg:px-8 py-10 space-y-5">
          <div className="h-8 skeleton" />
          <div className="h-20 skeleton" />
          <div className="h-96 skeleton" />
        </main>
      </div>
    );
  }

  if (error || !article) {
    return (
      <div className="min-h-screen flex flex-col">
        <Header leftSlot={backButton} />
        <main className="flex-1 max-w-4xl mx-auto w-full px-4 sm:px-6 lg:px-8 py-10">
          <div
            className="border border-[var(--risk-high-rule)] p-6"
            style={{ background: 'var(--risk-high-bg)' }}
          >
            <p className="font-semibold text-[12px] uppercase tracking-[0.12em]" style={{ color: 'var(--crimson-2)' }}>
              {locale === 'pl' ? 'Nie udalo sie zaladowac danych' : 'Could not load data'}
            </p>
            <p className="text-sm text-[var(--ink-2)] mt-1">{error ?? t.detail.errorBody}</p>
            <Link href="/" className="doc-btn doc-btn--primary mt-4 no-underline">
              {t.detail.errorBack}
            </Link>
          </div>
        </main>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex flex-col">
      <Header leftSlot={backButton} />

      <LocaleFade>
        <main className="flex-1">
          <section className="bg-[var(--surface)] border-b border-[var(--border)]">
            <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8 sm:py-10">
              <div className="gov-panel">
                <div className="gov-section-header">
                  <span>{locale === 'pl' ? 'Publikacja zrodlowa' : 'Source publication'} · #{article.id}</span>
                  <span>{article.processed ? locale === 'pl' ? 'Przetworzony' : 'Processed' : locale === 'pl' ? 'Oczekuje' : 'Pending'}</span>
                </div>
                <div className="p-5 sm:p-7">
                  <p className="eyebrow mb-3">
                    {locale === 'pl' ? 'Material dowodowy w profilu ryzyka' : 'Evidence material in risk profile'}
                  </p>
                  <h1 className="text-3xl sm:text-[38px] font-extrabold tracking-tight text-[var(--ink)] leading-[1.08]">
                    {article.title || (locale === 'pl' ? 'Artykul bez tytulu' : 'Untitled article')}
                  </h1>
                  <div className="grid grid-cols-1 sm:grid-cols-3 border border-[var(--border)] mt-6">
                    <div className="gov-meta-row sm:block">
                      <div className="gov-meta-label">{t.detail.articleSource}</div>
                      <div className="gov-meta-value font-mono">{article.source ?? '—'}</div>
                    </div>
                    <div className="gov-meta-row sm:block">
                      <div className="gov-meta-label">{locale === 'pl' ? 'Data' : 'Date'}</div>
                      <div className="gov-meta-value tnum">
                        {article.published_at
                          ? formatDate(article.published_at, { day: '2-digit', month: 'short', year: 'numeric' })
                          : '—'}
                      </div>
                    </div>
                    <div className="gov-meta-row sm:block">
                      <div className="gov-meta-label">{locale === 'pl' ? 'Status' : 'Status'}</div>
                      <div className="gov-meta-value">
                        <span
                          className="px-2 py-1 border font-extrabold uppercase tracking-[0.1em] text-[10px]"
                          style={{
                            background: article.processed ? 'var(--risk-low-bg)' : 'var(--risk-medium-bg)',
                            borderColor: article.processed ? 'var(--risk-low-rule)' : 'var(--risk-medium-rule)',
                            color: article.processed ? 'var(--risk-low)' : 'var(--risk-medium)',
                          }}
                        >
                          {article.processed
                            ? locale === 'pl' ? 'Przetworzony' : 'Processed'
                            : locale === 'pl' ? 'Nieprzetworzony' : 'Pending'}
                        </span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </section>

          <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-10 space-y-8">
            <section className="gov-panel">
              <div className="px-5 sm:px-7 py-6 border-b border-[var(--rule)] flex items-center justify-between gap-4 flex-wrap">
                <h2 className="section-title !mb-0 !pb-0 !border-0">
                  {locale === 'pl' ? 'Tresc artykulu' : 'Article text'}
                </h2>
                {article.url && (
                  <a
                    href={article.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="doc-btn no-underline"
                  >
                    {locale === 'pl' ? 'Otworz zrodlo' : 'Open source'}
                    <svg xmlns="http://www.w3.org/2000/svg" className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4m-4-4l8-8m0 0H8m8 0v8" />
                    </svg>
                  </a>
                )}
              </div>

              {paragraphs.length > 0 ? (
                <article className="px-5 sm:px-7 py-7 space-y-5 text-[15px] leading-7 text-[var(--ink-2)]">
                  {paragraphs.map((paragraph, index) => (
                    <p key={index}>{paragraph}</p>
                  ))}
                </article>
              ) : (
                <div className="px-5 sm:px-7 py-7">
                  <p className="text-sm text-[var(--ink-muted)]">
                    {locale === 'pl'
                      ? 'Dla tego wpisu nie ma zapisanej pelnej tresci w bazie. Mozesz otworzyc oryginalne zrodlo, jesli URL jest dostepny.'
                      : 'This record has no full text stored in the database. You can open the original source when a URL is available.'}
                  </p>
                </div>
              )}
            </section>
          </div>
        </main>
      </LocaleFade>
    </div>
  );
}
