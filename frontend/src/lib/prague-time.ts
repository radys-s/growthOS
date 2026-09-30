/** Europe/Prague wall-clock helpers for <input type="datetime-local">, DST-aware. */

export function localInput(iso: string | null) {
  if (!iso) return "";
  const parts = new Intl.DateTimeFormat("sv-SE", {
    timeZone: "Europe/Prague",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  }).format(new Date(iso));
  return parts.replace(" ", "T");
}

export function pragueTime(value: string, choice: string): string | null {
  if (!value) return null;
  const candidates = ["+02:00", "+01:00"]
    .map((offset) => value + ":00" + offset)
    .filter((iso) => localInput(iso) === value);
  if (!candidates.length) throw new Error("Tento čas v Praze neexistuje kvůli změně na letní čas.");
  if (candidates.length === 2 && !choice)
    throw new Error("Tento čas nastává dvakrát. Vyber letní nebo zimní čas.");
  return new Date(candidates.find((iso) => iso.endsWith(choice)) ?? candidates[0]).toISOString();
}
