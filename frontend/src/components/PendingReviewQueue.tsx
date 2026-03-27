import { useCallback, useEffect, useState } from "react";
import { acceptFact, dismissFact, listPending } from "../api/pending";
import { ApiRequestError } from "../api/client";
import type { PendingFactItem } from "../types";

const PAGE_SIZE = 50;

interface Props {
  companyId: string;
  /** Called after a fact is accepted/dismissed so parent can refresh counts. */
  onFactReviewed?: () => void;
}

function PendingReviewQueue({ companyId, onFactReviewed }: Props) {
  const [facts, setFacts] = useState<PendingFactItem[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [actionInProgress, setActionInProgress] = useState<string | null>(null);

  const fetchPending = useCallback(
    async (newOffset = 0) => {
      setLoading(true);
      try {
        const data = await listPending(companyId, {
          status: "pending",
          limit: PAGE_SIZE,
          offset: newOffset,
        });
        setFacts(data.items);
        setTotal(data.total);
        setOffset(newOffset);
        setError("");
      } catch (err) {
        if (err instanceof ApiRequestError) {
          setError(err.error.message);
        } else {
          setError("Failed to load pending facts.");
        }
      } finally {
        setLoading(false);
      }
    },
    [companyId],
  );

  useEffect(() => {
    void fetchPending(0);
  }, [fetchPending]);

  async function handleAccept(factId: string) {
    setActionInProgress(factId);
    try {
      await acceptFact(companyId, factId);
      // Remove from list and update total.
      setFacts((prev) => prev.filter((f) => f.fact_id !== factId));
      setTotal((prev) => prev - 1);
      onFactReviewed?.();
    } catch (err) {
      if (err instanceof ApiRequestError) {
        setError(err.error.message);
      }
    } finally {
      setActionInProgress(null);
    }
  }

  async function handleDismiss(factId: string) {
    setActionInProgress(factId);
    try {
      await dismissFact(companyId, factId);
      setFacts((prev) => prev.filter((f) => f.fact_id !== factId));
      setTotal((prev) => prev - 1);
      onFactReviewed?.();
    } catch (err) {
      if (err instanceof ApiRequestError) {
        setError(err.error.message);
      }
    } finally {
      setActionInProgress(null);
    }
  }

  if (loading && facts.length === 0) {
    return <p className="text-muted">Loading pending facts...</p>;
  }

  if (error) {
    return <div className="error-message">{error}</div>;
  }

  if (total === 0) {
    return <p className="text-muted">No pending facts to review.</p>;
  }

  const totalPages = Math.ceil(total / PAGE_SIZE);
  const currentPage = Math.floor(offset / PAGE_SIZE) + 1;

  return (
    <div>
      <div className="pending-list">
        {facts.map((fact) => (
          <div key={fact.fact_id} className="pending-item">
            <div className="pending-item-content">
              <span className={`category-badge cat-${fact.category}`}>
                {fact.category}
              </span>
              <span className="pending-value">{fact.inferred_value}</span>
              {fact.source_excerpt && (
                <span className="pending-excerpt">{fact.source_excerpt}</span>
              )}
            </div>
            <div className="pending-item-actions">
              <button
                className="btn-small btn-accept"
                onClick={() => void handleAccept(fact.fact_id)}
                disabled={actionInProgress === fact.fact_id}
              >
                Accept
              </button>
              <button
                className="btn-small btn-dismiss"
                onClick={() => void handleDismiss(fact.fact_id)}
                disabled={actionInProgress === fact.fact_id}
              >
                Dismiss
              </button>
            </div>
          </div>
        ))}
      </div>

      {totalPages > 1 && (
        <div className="pagination">
          <button
            onClick={() => void fetchPending(offset - PAGE_SIZE)}
            disabled={offset === 0}
          >
            Previous
          </button>
          <span className="text-muted">
            Page {currentPage} of {totalPages}
          </span>
          <button
            onClick={() => void fetchPending(offset + PAGE_SIZE)}
            disabled={offset + PAGE_SIZE >= total}
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}

export default PendingReviewQueue;
