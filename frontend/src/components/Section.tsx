type SectionProps = {
  title: string;
  subtitle: string;
  emptyText: string;
  className?: string;
};

export function Section({ title, subtitle, emptyText, className = "" }: SectionProps) {
  return (
    <section
      className={`flex flex-col rounded-2xl border border-white/10 bg-zinc-900/60 p-6 ${className}`}
    >
      <header className="mb-4">
        <h2 className="text-lg font-semibold tracking-tight text-zinc-50">{title}</h2>
        <p className="text-sm text-zinc-400">{subtitle}</p>
      </header>
      <div className="flex flex-1 items-center justify-center rounded-xl border border-dashed border-white/10 p-8 text-center text-sm text-zinc-500">
        {emptyText}
      </div>
    </section>
  );
}
