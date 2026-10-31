"use client";
import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, XCircle } from "lucide-react";
import { Badge, Skeleton, statusTone } from "@/components/ui";
import { api } from "@/lib/api";

const STATUS_HELP: Record<string, string> = {
  supported: "The saved source response contains this exact value for this exact record.",
  unsupported: "The value could not be found in the cited record. Do not rely on this claim.",
  unverified: "No saved source was available to check this claim.",
  stale: "Retrieved long ago; refresh before relying on it.",
  conflicting: "Two sources disagree about this value.",
};

export function SourceViewer({ missionId, evidenceId }: { missionId: string; evidenceId: string }) {
  const q = useQuery({ queryKey: ["source", missionId, evidenceId], queryFn: () => api.source(missionId, evidenceId) });
  if (q.isLoading) return <Skeleton className="h-32" />;
  if (q.error || !q.data) return <div className="text-sm text-bad">Could not load the source record.</div>;
  const s = q.data;
  const found = s.value_in_source?.map(String) ?? [];
  const match = s.claimed_value != null && found.some((f) => f === s.claimed_value || Number(f) === Number(s.claimed_value));
  return (
    <div className="space-y-3 text-sm" data-testid="source-viewer">
      <div className="flex flex-wrap items-center gap-2"><Badge tone={statusTone(s.status)}>{s.status}</Badge><span className="text-xs text-muted">{STATUS_HELP[s.status]}</span></div>
      <div className="font-medium">{s.claim}</div>
      <dl className="grid grid-cols-[9rem_1fr] gap-x-3 gap-y-1.5 rounded-lg bg-surface-2 p-3 text-xs">
        <dt className="text-muted">Field path</dt><dd className="font-mono">{s.field_path ?? "n/a"}</dd>
        <dt className="text-muted">Retrieved at</dt><dd>{new Date(s.retrieved_at_utc).toLocaleString()}</dd>
        <dt className="text-muted">Claimed value</dt><dd className="font-mono">{s.claimed_value ?? "n/a"}</dd>
        <dt className="text-muted">Value in saved source</dt>
        <dd className="flex items-center gap-1.5 font-mono">{found.length ? found.join(", ") : <span className="text-warn">{s.note ?? "not found"}</span>}
          {found.length > 0 && (match ? <CheckCircle2 size={14} className="text-good" aria-label="matches" /> : <XCircle size={14} className="text-bad" aria-label="differs" />)}</dd>
        <dt className="text-muted">Source file</dt><dd className="break-all font-mono">{s.raw_file ? s.raw_file.split("/").slice(-3).join("/") : "none recorded"}</dd>
      </dl>
      {s.notes && <p className="text-xs text-muted">{s.notes}</p>}
    </div>
  );
}
