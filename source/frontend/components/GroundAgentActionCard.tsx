import { useState } from "react";
import { getApiBaseUrl } from "../utils/telemetry";
import type { LocationBbox, LocationPreviewTile } from "../types/location";
import { buildPreviewTiles } from "../utils/locationPreviewTiles";

export type AgentAction = {
  name: string;
  status: "ok" | "error" | string;
  result?: Record<string, unknown>;
};

export type GroundAgentProposal = {
  id: string;
  kind: "load_replay" | "rescan_replay" | "start_mission_pack" | "start_custom_mission" | "navigate_map_location" | "set_link_state" | string;
  title: string;
  summary: string;
  details: Record<string, unknown>;
  confirm_label: string;
  cancel_label: string;
  risk_level: "low" | "medium" | "high" | string;
};

export type ChatResponse = {
  reply?: unknown;
  actions?: AgentAction[];
  proposals?: GroundAgentProposal[];
  suggestions?: string[];
};

type GroundAgentActionCardProps = {
  proposal: GroundAgentProposal;
  onConfirmed: (response: ChatResponse) => void | Promise<void>;
  onCancelled: (proposal: GroundAgentProposal) => void;
};

async function readAgentError(response: Response, fallback: string): Promise<string> {
  try {
    const payload = await response.json() as { error?: unknown; detail?: unknown };
    if (typeof payload.error === "string" && payload.error.trim()) return payload.error;
    if (typeof payload.detail === "string" && payload.detail.trim()) return payload.detail;
  } catch {
    return fallback;
  }
  return fallback;
}

function detailLabel(key: string): string {
  return key.replace(/_/g, " ");
}

function detailValue(value: unknown): string {
  if (typeof value === "boolean") return value ? "yes" : "no";
  if (Array.isArray(value)) {
    return value
      .map((entry) => entry && typeof entry === "object" ? JSON.stringify(entry) : String(entry))
      .join(", ");
  }
  if (value && typeof value === "object") return JSON.stringify(value);
  return String(value ?? "");
}

function normalizeNumberArray(value: unknown, length: number): number[] | null {
  if (!Array.isArray(value) || value.length !== length) return null;
  const numbers = value.map((entry) => Number(entry));
  return numbers.every(Number.isFinite) ? numbers : null;
}

function normalizePreviewTiles(value: unknown): LocationPreviewTile[] {
  if (!Array.isArray(value)) return [];
  return value.flatMap((entry) => {
    if (!entry || typeof entry !== "object") return [];
    const raw = entry as Record<string, unknown>;
    const z = Number(raw.z);
    const x = Number(raw.x);
    const y = Number(raw.y);
    const url = typeof raw.url === "string" ? raw.url : "";
    if (!Number.isFinite(z) || !Number.isFinite(x) || !Number.isFinite(y) || !url) return [];
    return [{ z, x, y, url }];
  });
}

function locationPreviewTiles(details: Record<string, unknown>): LocationPreviewTile[] {
  const fromDetails = normalizePreviewTiles(details.preview_tiles);
  if (fromDetails.length > 0) return fromDetails;
  const bbox = normalizeNumberArray(details.bbox, 4) as LocationBbox | null;
  return bbox ? buildPreviewTiles(bbox) : [];
}

function riskClass(riskLevel: string): string {
  if (riskLevel === "high") return "border-red-200 bg-red-50 text-red-700";
  if (riskLevel === "medium") return "border-amber-200 bg-amber-50 text-amber-700";
  return "border-emerald-200 bg-emerald-50 text-emerald-700";
}

function responseActionError(payload: ChatResponse): string | null {
  const failedAction = payload.actions?.find((action) => action.status === "error");
  if (!failedAction) return null;
  if (typeof failedAction.result?.error === "string" && failedAction.result.error.trim()) {
    return failedAction.result.error;
  }
  if (typeof payload.reply === "string" && payload.reply.trim()) {
    return payload.reply;
  }
  return "Ground Agent declined this action.";
}

function proofLabel(key: string): string {
  if (key === "request") return "Request";
  if (key === "planner_result") return "Planner Result";
  if (key === "workflow_mode") return "Workflow";
  if (key === "difficulty") return "Difficulty";
  if (key === "replay_id") return "Replay";
  if (key === "runtime_truth_mode") return "Truth";
  if (key === "imagery_origin") return "Origin";
  if (key === "scoring_basis") return "Scoring";
  if (key === "use_case_id") return "Use Case";
  if (key === "target_pack_id") return "Target Pack";
  if (key === "object_target_labels") return "Object Targets";
  if (key === "location_id") return "Location";
  if (key === "query") return "Query";
  if (key === "provider") return "Provider";
  if (key === "location_provider") return "Location Provider";
  if (key === "location_confidence") return "Location Confidence";
  if (key === "feature_type") return "Feature";
  if (key === "bbox") return "BBox";
  if (key === "location_context_bbox") return "Context BBox";
  if (key === "center") return "Center";
  if (key === "camera") return "Camera";
  if (key === "stop_active_mission") return "Stop Mission";
  if (key === "location_type") return "Type";
  if (key === "terrain_context") return "Terrain";
  if (key === "mission_context") return "Use";
  if (key === "semantic_tags") return "Tags";
  if (key === "suggested_targets") return "Suggested Targets";
  if (key === "evidence_guidance") return "Evidence Guidance";
  if (key === "region_label") return "Region";
  if (key === "start_date") return "Start";
  if (key === "end_date") return "End";
  if (key === "temporal_cadence") return "Cadence";
  if (key === "requested_frame_count") return "Requested Frames";
  if (key === "cadence_note") return "Cadence Note";
  if (key === "confidence") return "Confidence";
  return detailLabel(key);
}

export default function GroundAgentActionCard({
  proposal,
  onConfirmed,
  onCancelled,
}: GroundAgentActionCardProps) {
  const [expanded, setExpanded] = useState(false);
  const [status, setStatus] = useState<"pending" | "running" | "confirmed" | "cancelled" | "error">("pending");
  const [error, setError] = useState<string | null>(null);
  const stateImpact = Array.isArray(proposal.details.state_impact)
    ? proposal.details.state_impact.map((item) => String(item))
    : [];
  const previewTiles = proposal.kind === "navigate_map_location"
    ? locationPreviewTiles(proposal.details).slice(0, 9)
    : [];
  const proofDetails = ["request", "query", "planner_result", "workflow_mode", "difficulty", "replay_id", "region_label", "location_id", "provider", "location_provider", "location_confidence", "feature_type", "location_type", "suggested_targets", "evidence_guidance", "bbox", "location_context_bbox", "center", "start_date", "end_date", "temporal_cadence", "requested_frame_count", "cadence_note", "runtime_truth_mode", "imagery_origin", "scoring_basis", "use_case_id", "target_pack_id", "object_target_labels", "confidence"]
    .map((key) => [key, proposal.details[key]] as const)
    .filter(([, value]) => value !== undefined && value !== null && value !== "");
  const visibleDetails = Object.entries(proposal.details).filter(([key]) => key !== "state_impact" && key !== "preview_tiles");
  const canAct = status === "pending" || status === "error";

  async function confirmProposal() {
    if (!canAct) return;
    setStatus("running");
    setError(null);
    try {
      const response = await fetch(`${getApiBaseUrl()}/api/agent/action/confirm`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ proposal }),
      });
      if (!response.ok) {
        throw new Error(await readAgentError(response, `Ground Agent action failed with HTTP ${response.status}.`));
      }
      const payload = await response.json() as ChatResponse;
      const actionError = responseActionError(payload);
      if (actionError) {
        setStatus("error");
        setError(actionError);
        await onConfirmed(payload);
        return;
      }
      setStatus("confirmed");
      await onConfirmed(payload);
    } catch (err) {
      setStatus("error");
      setError(err instanceof Error ? err.message : "Ground Agent action failed.");
    }
  }

  function cancelProposal() {
    if (!canAct) return;
    setStatus("cancelled");
    onCancelled(proposal);
  }

  return (
    <div
      className="mt-3 w-full rounded border border-zinc-200 bg-white p-3 text-left shadow-sm"
      data-testid="ground-agent-proposal-card"
    >
      <div className="mb-2 flex items-start justify-between gap-3">
        <div>
          <p className="text-[10px] font-bold uppercase tracking-wider text-zinc-500">Action Proposal</p>
          <p className="mt-1 text-sm font-semibold text-zinc-900">{proposal.title}</p>
        </div>
        <span className={`shrink-0 rounded border px-2 py-1 text-[10px] font-bold uppercase tracking-wider ${riskClass(proposal.risk_level)}`}>
          {proposal.risk_level}
        </span>
      </div>

      <p className="text-xs leading-relaxed text-zinc-600">{proposal.summary}</p>

      {previewTiles.length > 0 && (
        <div className="mt-3 overflow-hidden rounded border border-zinc-200 bg-zinc-950" data-testid="location-preview-tiles">
          <div className="grid aspect-[3/2] grid-cols-3 grid-rows-3">
            {previewTiles.map((tile) => (
              <img
                key={`${tile.z}/${tile.x}/${tile.y}`}
                src={tile.url}
                alt=""
                className="h-full w-full object-cover"
                draggable={false}
              />
            ))}
          </div>
          <p className="border-t border-white/10 px-2 py-1 text-[10px] font-semibold uppercase tracking-wider text-zinc-300">
            Preview imagery for confirmation only
          </p>
        </div>
      )}

      {proofDetails.length > 0 && (
        <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
          {proofDetails.map(([key, value]) => (
            <div
              key={key}
              className={`rounded border border-zinc-100 bg-zinc-50 px-2 py-1 ${["request", "evidence_guidance", "cadence_note", "object_target_labels"].includes(key) ? "col-span-2" : ""}`}
            >
              <p className="text-[10px] font-bold uppercase tracking-wider text-zinc-500">{proofLabel(key)}</p>
              <p className="break-words font-semibold text-zinc-800">{detailValue(value)}</p>
            </div>
          ))}
        </div>
      )}

      {stateImpact.length > 0 && (
        <div className="mt-3 rounded border border-zinc-200 bg-zinc-50 p-2">
          <p className="mb-1 text-[10px] font-bold uppercase tracking-wider text-zinc-500">State Impact</p>
          <ul className="space-y-1 text-xs text-zinc-700">
            {stateImpact.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
      )}

      {expanded && (
        <dl className="mt-3 grid grid-cols-2 gap-2 text-xs" data-testid="ground-agent-proposal-details">
          {visibleDetails.map(([key, value]) => (
            <div key={key} className="rounded border border-zinc-100 bg-zinc-50 px-2 py-1">
              <dt className="font-semibold capitalize text-zinc-500">{detailLabel(key)}</dt>
              <dd className="break-words font-medium text-zinc-800">{detailValue(value)}</dd>
            </div>
          ))}
        </dl>
      )}

      {error && (
        <p className="mt-2 rounded border border-red-200 bg-red-50 px-2 py-1 text-xs font-medium text-red-700">
          {error}
        </p>
      )}

      <div className="mt-3 flex flex-wrap gap-2">
        <button
          type="button"
          onClick={() => setExpanded((value) => !value)}
          className="rounded border border-zinc-200 bg-white px-3 py-1.5 text-xs font-semibold text-zinc-700 transition hover:bg-zinc-50"
        >
          {expanded ? "Hide Details" : "Details"}
        </button>
        <button
          type="button"
          onClick={() => void confirmProposal()}
          disabled={!canAct}
          data-testid="ground-agent-run-proposal"
          className="rounded bg-zinc-900 px-3 py-1.5 text-xs font-semibold text-white transition hover:bg-zinc-800 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {status === "running" ? "Running..." : status === "confirmed" ? "Confirmed" : proposal.confirm_label}
        </button>
        <button
          type="button"
          onClick={cancelProposal}
          disabled={!canAct}
          className="rounded border border-zinc-200 bg-white px-3 py-1.5 text-xs font-semibold text-zinc-600 transition hover:bg-zinc-50 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {status === "cancelled" ? "Cancelled" : proposal.cancel_label}
        </button>
      </div>
    </div>
  );
}
