export const LOCALES = ['pl', 'en'] as const;
export type Locale = (typeof LOCALES)[number];
export const DEFAULT_LOCALE: Locale = 'pl';

export const LOCALE_LABELS: Record<Locale, string> = {
  pl: 'Polski',
  en: 'English',
};

type Dictionary = {
  brand: { suffix: string };
  nav: {
    back: string;
    languageLabel: string;
  };
  dashboard: {
    title: string;
    titleAccent: string;
    subtitle: string;
    lastUpdated: string;
    loading: string;
    companiesCount: (n: number) => string;
    sortBy: string;
    sortRiskDesc: string;
    sortRiskAsc: string;
    sortName: string;
    statHigh: string;
    statMedium: string;
    statLow: string;
    statHelp: string;
    errorTitle: string;
    errorBody: string;
    errorRetry: string;
    emptyTitle: string;
    emptySubtitle: string;
  };
  search: {
    placeholder: string;
    noResults: (q: string) => string;
    hint: string;
  };
  card: {
    riskHigh: string;
    riskMedium: string;
    riskLow: string;
    nip: string;
    score: string;
    scoreOutOf: string;
  };
  detail: {
    addedOn: string;
    currentScore: string;
    exposureHigh: string;
    exposureMedium: string;
    exposureLow: string;
    statsTitle: string;
    statsMax: string;
    statsMin: string;
    statsCount: string;
    chartTitle: string;
    chartEmpty: string;
    categoriesTitle: string;
    categoriesEmpty: string;
    articlesTitle: string;
    articlesEmpty: string;
    articleSource: string;
    errorTitle: string;
    errorBody: string;
    errorBack: string;
  };
  alert: {
    title: string;
    body: (delta: string) => string;
    fallbackDelta: string;
    points: (n: number) => string;
  };
  categories: {
    corruption: string;
    sanctions: string;
    money_laundering: string;
    fraud: string;
    embezzlement: string;
    legal: string;
    regulatory: string;
    governance: string;
    other: string;
  };
};

export const DICTIONARIES: Record<Locale, Dictionary> = {
  pl: {
    brand: { suffix: 'Fraud' },
    nav: {
      back: 'Wróć',
      languageLabel: 'Język',
    },
    dashboard: {
      title: 'Monitor ryzyka',
      titleAccent: 'AML',
      subtitle:
        'Śledź reputację firm w czasie rzeczywistym na podstawie polskich źródeł medialnych.',
      lastUpdated: 'Aktualizacja',
      loading: 'Ładowanie…',
      companiesCount: (n) =>
        `${n} ${n === 1 ? 'firma' : n >= 2 && n <= 4 ? 'firmy' : 'firm'} w bazie`,
      sortBy: 'Sortuj',
      sortRiskDesc: 'Ryzyko ↑',
      sortRiskAsc: 'Ryzyko ↓',
      sortName: 'Nazwa',
      statHigh: 'Wysokie ryzyko',
      statMedium: 'Średnie ryzyko',
      statLow: 'Niskie ryzyko',
      statHelp: 'Podział firm wg poziomu scoringu',
      errorTitle: 'Brak połączenia',
      errorBody:
        'Nie udało się połączyć z API. Sprawdź, czy backend jest dostępny pod localhost:8000.',
      errorRetry: 'Spróbuj ponownie',
      emptyTitle: 'Brak firm w bazie',
      emptySubtitle: 'Dodaj pierwszą firmę, aby zacząć monitoring.',
    },
    search: {
      placeholder: 'Szukaj firmy po nazwie lub NIP…',
      noResults: (q) => `Brak wyników dla „${q}”.`,
      hint: 'Co najmniej 2 znaki',
    },
    card: {
      riskHigh: 'Wysokie ryzyko',
      riskMedium: 'Średnie ryzyko',
      riskLow: 'Niskie ryzyko',
      nip: 'NIP',
      score: 'Scoring reputacji',
      scoreOutOf: '/100',
    },
    detail: {
      addedOn: 'Dodano',
      currentScore: 'Aktualny scoring',
      exposureHigh: 'Wysoka ekspozycja',
      exposureMedium: 'Średnia ekspozycja',
      exposureLow: 'Niska ekspozycja',
      statsTitle: 'Statystyki',
      statsMax: 'Maksimum',
      statsMin: 'Minimum',
      statsCount: 'Liczba pomiarów',
      chartTitle: 'Historia scoringu',
      chartEmpty: 'Brak historii pomiarów.',
      categoriesTitle: 'Kategorie ryzyka',
      categoriesEmpty: 'Brak przypisanych kategorii w dostępnych pomiarach.',
      articlesTitle: 'Powiązane publikacje',
      articlesEmpty: 'Brak powiązanych artykułów.',
      articleSource: 'Źródło',
      errorTitle: 'Nie udało się załadować danych',
      errorBody: 'Sprawdź połączenie z API i spróbuj ponownie.',
      errorBack: 'Wróć do dashboardu',
    },
    alert: {
      title: 'Wykryto anomalię',
      body: (delta) =>
        `Scoring spadł o ${delta} w ciągu ostatnich 7 dni — to istotny wzrost ryzyka.`,
      fallbackDelta: 'ponad 20 pkt',
      points: (n) => `${n.toFixed(0)} pkt`,
    },
    categories: {
      corruption: 'Korupcja',
      sanctions: 'Sankcje',
      money_laundering: 'Pranie pieniędzy',
      fraud: 'Oszustwo',
      embezzlement: 'Defraudacja',
      legal: 'Postępowanie prawne',
      regulatory: 'Ryzyko regulacyjne',
      governance: 'Ład korporacyjny',
      other: 'Pozostałe',
    },
  },
  en: {
    brand: { suffix: 'Fraud' },
    nav: {
      back: 'Back',
      languageLabel: 'Language',
    },
    dashboard: {
      title: 'Risk monitor',
      titleAccent: 'AML',
      subtitle:
        'Track corporate reputation in real time across Polish media sources.',
      lastUpdated: 'Updated',
      loading: 'Loading…',
      companiesCount: (n) =>
        `${n} ${n === 1 ? 'company' : 'companies'} tracked`,
      sortBy: 'Sort',
      sortRiskDesc: 'Risk ↑',
      sortRiskAsc: 'Risk ↓',
      sortName: 'Name',
      statHigh: 'High risk',
      statMedium: 'Medium risk',
      statLow: 'Low risk',
      statHelp: 'Distribution by score level',
      errorTitle: 'Connection failed',
      errorBody:
        'Could not reach the API. Make sure the backend is running on localhost:8000.',
      errorRetry: 'Retry',
      emptyTitle: 'No companies yet',
      emptySubtitle: 'Add your first company to start monitoring.',
    },
    search: {
      placeholder: 'Search by name or VAT number…',
      noResults: (q) => `No results for “${q}”.`,
      hint: 'At least 2 characters',
    },
    card: {
      riskHigh: 'High risk',
      riskMedium: 'Medium risk',
      riskLow: 'Low risk',
      nip: 'VAT',
      score: 'Reputation score',
      scoreOutOf: '/100',
    },
    detail: {
      addedOn: 'Added',
      currentScore: 'Current score',
      exposureHigh: 'High exposure',
      exposureMedium: 'Medium exposure',
      exposureLow: 'Low exposure',
      statsTitle: 'Statistics',
      statsMax: 'Maximum',
      statsMin: 'Minimum',
      statsCount: 'Measurements',
      chartTitle: 'Score history',
      chartEmpty: 'No measurement history.',
      categoriesTitle: 'Risk categories',
      categoriesEmpty: 'No categories assigned in available measurements.',
      articlesTitle: 'Related coverage',
      articlesEmpty: 'No related articles.',
      articleSource: 'Source',
      errorTitle: 'Could not load company',
      errorBody: 'Check your API connection and try again.',
      errorBack: 'Back to dashboard',
    },
    alert: {
      title: 'Anomaly detected',
      body: (delta) =>
        `Score dropped by ${delta} in the last 7 days — a meaningful risk increase.`,
      fallbackDelta: 'more than 20 pts',
      points: (n) => `${n.toFixed(0)} pts`,
    },
    categories: {
      corruption: 'Corruption',
      sanctions: 'Sanctions',
      money_laundering: 'Money laundering',
      fraud: 'Fraud',
      embezzlement: 'Embezzlement',
      legal: 'Legal proceedings',
      regulatory: 'Regulatory risk',
      governance: 'Governance',
      other: 'Other',
    },
  },
};

export type { Dictionary };
