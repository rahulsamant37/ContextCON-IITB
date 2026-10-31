"use client";
import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, XCircle } from "lucide-react";
import { Pill, Skeleton } from "@/components/ui";
import { api } from "@/lib/api";
import { SOURCE_STATUS } from "@/lib/format";

const HELP: Record<string, string> = {
  supported: "We re-opened the saved data and found exactly this value for this company.",
  unsupported: "The value could not be found in the saved data. Don't rely on it.",
  unverified: "There was no saved data to check this against.",
  stale: "This data is old; refresh before relying on it.",
  conflicting: "Two sources disagree about this value.",
};

export function SourceViewer({ missionId, evidenceId }: { missionId: string; evidenceId: string }) {
  const q = useQuery({ queryKey: ["source", missionId, evidenceId], queryFn: () => api.source(missionId, evidenceId) });
  if (q.isLoading) return <Skeleton className="h-28" />;
  if (q.error || !q.data) return <p className="text-sm text-bad">Couldn&apos;t load this source.</p>;
  const s = q.data;
  const found = s.value_in_source?.map(String) ?? [];
  const match = s.claimed_value != null && found.some((f) => f === s.claimed_value || Number(f) === Number(s.claimed_value));
  const st = SOURCE_STATUS[s.status];
  return (
    <div className="space-y-3 text-sm" data-testid="source-viewer">
      <div className="flex items-center gap-2"><Pill tone={st?.tone}>{st?.label}</Pill><span className="text-[13px] text-muted">{HELP[s.status]}</span></div>
      <dl className="grid grid-cols-[8.5rem_1fr] gap-x-4 gap-y-2 rounded-md bg-subtle p-4 text-[13px]">
        <dt className="text-muted">Fact</dt><dd className="text-ink">{s.claim}</dd>
        <dt className="text-muted">Value we used</dt><dd className="tabular font-medium text-ink">{s.claimed_value ?? "—"}</dd>
        <dt className="text-muted">Value in source</dt>
        <dd className="flex items-center gap-1.5 font-medium text-ink">{found.length ? found.join(", ") : <span className="text-warn">{s.note ?? "Not found"}</span>}
          {found.length > 0 && (match ? <CheckCircle2 size={15} className="text-ok" aria-label="Matches" /> : <XCircle size={15} className="text-bad" aria-label="Does not match" />)}</dd>
        <dt className="text-muted">Data source</dt><dd>Crustdata · <span className="font-mono text-xs">{s.field_path ?? "—"}</span></dd>
        <dt className="text-muted">Retrieved</dt><dd>{new Date(s.retrieved_at_utc).toLocaleString()}</dd>
      </dl>
    </div>
  );
}
