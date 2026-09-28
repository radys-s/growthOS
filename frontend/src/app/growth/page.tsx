import { Suspense } from "react";
import GrowthWorkspace from "@/components/GrowthWorkspace";
type Query = Promise<Record<string, string | string[] | undefined>>;
async function Workspace({ query }: { query: Query }) {
  const q = await query;
  const value = (key: string) =>
    typeof q[key] === "string" ? (q[key] as string) : "";
  const tab = value("tab") || "imports";
  return (
    <GrowthWorkspace
      key={`${tab}:${value("target")}`}
      initialTab={tab}
      target={{
        id: value("target"),
        type: value("type") === "opportunity" ? "opportunity" : "action",
        title: value("title"),
      }}
    />
  );
}
export default function GrowthPage({ searchParams }: { searchParams: Query }) {
  return (
    <Suspense fallback={<p className="p-8">Načítání pracovního prostoru…</p>}>
      <Workspace query={searchParams} />
    </Suspense>
  );
}
