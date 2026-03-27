import { useCallback, useEffect, useRef, useState } from "react";
import {
  listSources,
  getSource,
  getSourceStatus,
  retrySource,
} from "../api/sources";
import { ApiRequestError } from "../api/client";
import type { SourceDetail, SourceListItem } from "../types";

const POLL_INTERVAL_MS = 3000;

interface Props {
  companyId: string;
  /** Incremented by parent to trigger a refresh (e.g. after upload). */
  refreshKey?: number;
}

function SourceList({ companyId, refreshKey }: Props) {
  const [sources, setSources] = useState<SourceListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [expandedDetail, setExpandedDetail] = useState<SourceDetail | null>(
    null,
  );
  const [detailLoading, setDetailLoading] = useState(false);
  const [retrying, setRetrying] = useState<string | null>(null);

  // Ref to hold latest sources so the polling interval callback always
  // reads current state without re-creating the interval on every change.
  const sourcesRef = useRef<SourceListItem[]>(sources);
  sourcesRef.current = sources;

  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchSources = useCallback(async () => {
    try {
      const data = await listSources(companyId);
      setSources(data.items);
      setTotal(data.total);
      setError("");
    } catch (err) {
      if (err instanceof ApiRequestError) {
        setError(err.error.message);
      } else {
        setError("Failed to load sources.");
      }
    } finally {
      setLoading(false);
    }
  }, [companyId]);

  // Initial fetch + re-fetch when refreshKey changes.
  useEffect(() => {
    setLoading(true);
    void fetchSources();
  }, [fetchSources, refreshKey]);

  // Start/stop polling based on whether any source is in-progress.
  // Uses a ref for sources so the interval closure always sees current data
  // without triggering effect re-runs on every state change.
  const hasInProgress = sources.some(
    (s) => s.status === "pending" || s.status === "processing",
  );

  useEffect(() => {
    if (!hasInProgress) {
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
      return;
    }

    pollRef.current = setInterval(async () => {
      const current = sourcesRef.current;
      const inProgress = current.filter(
        (s) => s.status === "pending" || s.status === "processing",
      );
      if (inProgress.length === 0) return;

      let changed = false;
      const updated = [...current];

      for (const source of inProgress) {
        try {
          const statusResp = await getSourceStatus(source.source_id);
          const idx = updated.findIndex(
            (s) => s.source_id === source.source_id,
          );
          const existing = idx !== -1 ? updated[idx] : undefined;
          if (existing && existing.status !== statusResp.status) {
            updated[idx] = { ...existing, status: statusResp.status };
            changed = true;
          }
        } catch {
          // Ignore individual poll errors.
        }
      }

      if (changed) {
        setSources(updated);
        // If all sources finished, do a full refresh to pick up error messages.
        const stillInProgress = updated.some(
          (s) => s.status === "pending" || s.status === "processing",
        );
        if (!stillInProgress) {
          void fetchSources();
        }
      }
    }, POLL_INTERVAL_MS);

    return () => {
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
    };
  }, [hasInProgress, fetchSources]);

  async function handleExpand(sourceId: string) {
    if (expandedId === sourceId) {
      // Collapse.
      setExpandedId(null);
      setExpandedDetail(null);
      return;
    }

    setExpandedId(sourceId);
    setExpandedDetail(null);
    setDetailLoading(true);
    try {
      const detail = await getSource(sourceId);
      setExpandedDetail(detail);
    } catch (err) {
      if (err instanceof ApiRequestError) {
        setError(err.error.message);
      }
      // Keep expandedId set so the user sees the error state.
    } finally {
      setDetailLoading(false);
    }
  }

  async function handleRetry(sourceId: string) {
    setRetrying(sourceId);
    try {
      await retrySource(sourceId);
      // Update the local status immediately.
      setSources((prev) =>
        prev.map((s) =>
          s.source_id === sourceId
            ? { ...s, status: "pending", error: null }
            : s,
        ),
      );
    } catch (err) {
      if (err instanceof ApiRequestError) {
        setError(err.error.message);
      }
    } finally {
      setRetrying(null);
    }
  }

  if (loading) {
    return <p className="text-muted">Loading sources...</p>;
  }

  if (error) {
    return <div className="error-message">{error}</div>;
  }

  if (sources.length === 0) {
    return <p className="text-muted">No sources uploaded yet.</p>;
  }

  return (
    <div>
      <table>
        <thead>
          <tr>
            <th>File</th>
            <th>Type</th>
            <th>Received</th>
            <th>Status</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {sources.map((source) => (
            <tr key={source.source_id}>
              <td>
                <button
                  className="link-button"
                  onClick={() => void handleExpand(source.source_id)}
                >
                  {source.subject_or_filename || "Unnamed"}
                </button>
              </td>
              <td>{source.type}</td>
              <td>{new Date(source.received_at).toLocaleString()}</td>
              <td>
                <span className={`status-badge status-${source.status}`}>
                  {source.status}
                </span>
              </td>
              <td>
                {source.status === "failed" && (
                  <button
                    className="btn-small"
                    onClick={() => void handleRetry(source.source_id)}
                    disabled={retrying === source.source_id}
                  >
                    {retrying === source.source_id ? "Retrying..." : "Retry"}
                  </button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {total > sources.length && (
        <p className="text-muted" style={{ marginTop: 8 }}>
          Showing {sources.length} of {total} sources.
        </p>
      )}
      {/* Expanded source detail with raw content */}
      {expandedId && (
        <div className="source-detail-panel">
          {detailLoading && (
            <p className="text-muted">Loading source content...</p>
          )}
          {expandedDetail && (
            <>
              {expandedDetail.error && (
                <div className="error-message" style={{ marginBottom: 8 }}>
                  <strong>Error:</strong> {expandedDetail.error}
                </div>
              )}
              {expandedDetail.who && (
                <p style={{ marginBottom: 4 }}>
                  <strong>Contact:</strong> {expandedDetail.who}
                </p>
              )}
              {expandedDetail.interaction_date && (
                <p style={{ marginBottom: 4 }}>
                  <strong>Date:</strong> {expandedDetail.interaction_date}
                </p>
              )}
              {expandedDetail.src && (
                <p style={{ marginBottom: 4 }}>
                  <strong>Source:</strong> {expandedDetail.src}
                </p>
              )}
              <h3 style={{ marginTop: 12 }}>Raw Content</h3>
              <pre className="source-raw-content">
                {expandedDetail.raw_content}
              </pre>
              <p className="text-muted" style={{ fontSize: 12, marginTop: 8 }}>
                Source ID: {expandedDetail.source_id}
              </p>
            </>
          )}
          {!detailLoading && !expandedDetail && (
            <p className="text-muted">Failed to load source detail.</p>
          )}
        </div>
      )}
    </div>
  );
}

export default SourceList;
