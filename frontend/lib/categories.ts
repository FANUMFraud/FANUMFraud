export type CanonicalCategory =
  | 'corruption'
  | 'sanctions'
  | 'money_laundering'
  | 'fraud'
  | 'embezzlement'
  | 'legal'
  | 'regulatory'
  | 'governance'
  | 'other';

type CategoryMeta = {
  label: string;
  cardClass: string;
};

export const CATEGORY_ORDER: CanonicalCategory[] = [
  'corruption',
  'sanctions',
  'money_laundering',
  'fraud',
  'embezzlement',
  'legal',
  'regulatory',
  'governance',
  'other',
];

export const CATEGORY_META: Record<CanonicalCategory, CategoryMeta> = {
  corruption: {
    label: 'Korupcja',
    cardClass: 'bg-red-500/8 border-red-500/20 text-red-400',
  },
  sanctions: {
    label: 'Sankcje',
    cardClass: 'bg-fuchsia-500/8 border-fuchsia-500/20 text-fuchsia-400',
  },
  money_laundering: {
    label: 'Pranie pieniędzy',
    cardClass: 'bg-yellow-500/8 border-yellow-500/20 text-yellow-400',
  },
  fraud: {
    label: 'Oszustwo',
    cardClass: 'bg-pink-500/8 border-pink-500/20 text-pink-400',
  },
  embezzlement: {
    label: 'Defraudacja',
    cardClass: 'bg-rose-500/8 border-rose-500/20 text-rose-400',
  },
  legal: {
    label: 'Postępowanie prawne',
    cardClass: 'bg-orange-500/8 border-orange-500/20 text-orange-400',
  },
  regulatory: {
    label: 'Ryzyko regulacyjne',
    cardClass: 'bg-cyan-500/8 border-cyan-500/20 text-cyan-400',
  },
  governance: {
    label: 'Ład korporacyjny',
    cardClass: 'bg-indigo-500/8 border-indigo-500/20 text-indigo-400',
  },
  other: {
    label: 'Pozostałe',
    cardClass: 'bg-emerald-500/8 border-emerald-500/20 text-emerald-400',
  },
};

const CATEGORY_ALIASES: Record<string, CanonicalCategory> = {
  corruption: 'corruption',
  korupcja: 'corruption',
  bribery: 'corruption',
  lapowka: 'corruption',

  sanctions: 'sanctions',
  sanction: 'sanctions',
  sankcje: 'sanctions',

  money_laundering: 'money_laundering',
  money_laundering_signal: 'money_laundering',
  money_laundering_case: 'money_laundering',
  pranie_pieniedzy: 'money_laundering',
  aml: 'money_laundering',

  fraud: 'fraud',
  oszustwo: 'fraud',
  scam: 'fraud',
  wyludzenie: 'fraud',

  embezzlement: 'embezzlement',
  defraudacja: 'embezzlement',
  malwersacja: 'embezzlement',

  legal: 'legal',
  zarzuty_karne: 'legal',
  zarzuty: 'legal',
  prosecution: 'legal',

  regulatory: 'regulatory',
  regulacyjne: 'regulatory',
  compliance: 'regulatory',

  governance: 'governance',
  corporate_governance: 'governance',
  zarzad: 'governance',

  other: 'other',
  neutralny: 'other',
  neutral: 'other',
  general: 'other',
  low: 'other',
  medium: 'other',
  high: 'other',
  critical: 'other',
};

export function normalizeCategory(value: string | null | undefined): CanonicalCategory {
  if (!value) return 'other';
  const normalized = normalizeCategoryKey(value);
  return CATEGORY_ALIASES[normalized] ?? 'other';
}

function normalizeCategoryKey(value: string): string {
  return value
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .trim()
    .toLowerCase()
    .replace(/[\s\-/]+/g, '_')
    .replace(/[^a-z0-9_]/g, '');
}
