type SectionProps = {
  title: string;
  subtitle?: string;
  action?: React.ReactNode;
  className?: string;
  children: React.ReactNode;
};

export function Section({ title, subtitle, action, className = "", children }: SectionProps) {
  return (
    <section
      className={`flex flex-col rounded-2xl border border-white/10 bg-zinc-900/60 p-5 sm:p-6 ${className}`}
    >
      <header className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold tracking-tight text-zinc-50">{title}</h2>
          {subtitle && <p className="text-sm text-zinc-400">{subtitle}</p>}
        </div>
        {action}
      </header>
      {children}
    </section>
  );
}

export function EmptyState({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex flex-1 items-center justify-center rounded-xl border border-dashed border-white/10 p-8 text-center text-sm text-zinc-500">
      {children}
    </div>
  );
}

export function SectionSkeleton({ rows = 3 }: { rows?: number }) {
  return (
    <div className="flex flex-col gap-3" aria-hidden>
      {Array.from({ length: rows }, (_, i) => (
        <div key={i} className="h-20 animate-pulse rounded-xl bg-white/5" />
      ))}
    </div>
  );
}
