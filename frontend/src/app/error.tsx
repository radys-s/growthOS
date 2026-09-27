"use client";

import { useEffect } from "react";

export default function Error({
  error,
  retry,
}: {
  error: Error & { digest?: string };
  retry: () => void;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <main className="mx-auto flex w-full max-w-xl flex-1 flex-col items-center justify-center gap-4 px-4 py-20 text-center">
      <h1 className="text-xl font-semibold text-zinc-50">Něco se nepovedlo</h1>
      <p className="text-sm text-zinc-400">
        Backend akci odmítl nebo neodpovídá. Zkontroluj, že běží na portu 8000.
      </p>
      <button
        onClick={() => retry()}
        className="rounded-md border border-white/10 px-4 py-1.5 text-sm text-zinc-200 hover:bg-white/5"
      >
        Zkusit znovu
      </button>
    </main>
  );
}
