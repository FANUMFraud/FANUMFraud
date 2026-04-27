interface Props {
  show: boolean;
  scoreDelta?: number;
}

export default function AlertBanner({ show, scoreDelta }: Props) {
  if (!show) return null;

  return (
    <div className="animate-pulse-glow rounded-2xl border border-red-500/40 bg-red-500/8 p-5 flex gap-4 items-start">
      {/* Icon */}
      <div className="shrink-0 mt-0.5 w-10 h-10 rounded-full bg-red-500/15 flex items-center justify-center">
        <svg
          xmlns="http://www.w3.org/2000/svg"
          className="w-5 h-5 text-red-400"
          fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}
        >
          <path strokeLinecap="round" strokeLinejoin="round"
            d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z"
          />
        </svg>
      </div>

      {/* Text */}
      <div>
        <p className="text-red-400 font-bold text-base uppercase tracking-wide">
          Anomalia wykryta
        </p>
        <p className="text-red-300/80 text-sm mt-1 leading-relaxed">
          Score firmy wzrósł o{' '}
          <span className="font-bold text-red-400">
            {scoreDelta != null ? `${scoreDelta.toFixed(0)} pkt` : 'ponad 20 pkt'}
          </span>{' '}
          w ciągu ostatnich 7 dni — co oznacza gwałtowny wzrost ryzyka.
        </p>
      </div>
    </div>
  );
}
