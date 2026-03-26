import { FormEvent, useCallback, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { createCompany, listCompanies } from "../api/companies";
import { ApiRequestError } from "../api/client";
import type { CompanyListItem } from "../types";

const PAGE_SIZE = 25;

function CompanyListPage() {
  const navigate = useNavigate();
  const [companies, setCompanies] = useState<CompanyListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // Create form state.
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState("");
  const [newMission, setNewMission] = useState("");
  const [newVision, setNewVision] = useState("");
  const [createError, setCreateError] = useState("");
  const [creating, setCreating] = useState(false);

  const fetchCompanies = useCallback(
    async (newOffset: number) => {
      setLoading(true);
      try {
        const result = await listCompanies(PAGE_SIZE, newOffset);
        setCompanies(result.items);
        setTotal(result.total);
        setOffset(newOffset);
        setError("");
      } catch (err) {
        if (err instanceof ApiRequestError && err.status === 401) {
          navigate("/login");
          return;
        }
        setError("Failed to load companies.");
      } finally {
        setLoading(false);
      }
    },
    [navigate],
  );

  useEffect(() => {
    void fetchCompanies(0);
  }, [fetchCompanies]);

  const currentPage = Math.floor(offset / PAGE_SIZE) + 1;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const hasPrev = offset > 0;
  const hasNext = offset + PAGE_SIZE < total;

  async function handleCreate(e: FormEvent) {
    e.preventDefault();
    setCreateError("");
    setCreating(true);
    try {
      const result = await createCompany({
        name: newName,
        mission: newMission || undefined,
        vision: newVision || undefined,
      });
      setShowCreate(false);
      setNewName("");
      setNewMission("");
      setNewVision("");
      navigate(`/companies/${result.company_id}`);
    } catch (err) {
      if (err instanceof ApiRequestError) {
        if (err.error.code === "name_conflict") {
          setCreateError("A company with this name already exists.");
        } else {
          setCreateError(err.error.message);
        }
      } else {
        setCreateError("Failed to create company.");
      }
    } finally {
      setCreating(false);
    }
  }

  return (
    <div className="page-content">
      <div className="page-header">
        <h1>Companies</h1>
        <button onClick={() => setShowCreate(!showCreate)}>
          {showCreate ? "Cancel" : "+ New Company"}
        </button>
      </div>

      {showCreate && (
        <div className="card" style={{ marginBottom: 24 }}>
          <h2>Create Company</h2>
          <form onSubmit={handleCreate}>
            <div className="form-group">
              <label htmlFor="company-name">Name *</label>
              <input
                id="company-name"
                type="text"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                required
                autoFocus
              />
            </div>
            <div className="form-group">
              <label htmlFor="company-mission">Mission</label>
              <textarea
                id="company-mission"
                value={newMission}
                onChange={(e) => setNewMission(e.target.value)}
                rows={2}
              />
            </div>
            <div className="form-group">
              <label htmlFor="company-vision">Vision</label>
              <textarea
                id="company-vision"
                value={newVision}
                onChange={(e) => setNewVision(e.target.value)}
                rows={2}
              />
            </div>
            {createError && <div className="error-message">{createError}</div>}
            <button type="submit" disabled={creating}>
              {creating ? "Creating..." : "Create Company"}
            </button>
          </form>
        </div>
      )}

      {error && <div className="error-message">{error}</div>}

      {loading ? (
        <p className="text-muted">Loading...</p>
      ) : companies.length === 0 && offset === 0 ? (
        <p className="text-muted">
          No companies yet. Click &quot;+ New Company&quot; to get started.
        </p>
      ) : (
        <>
          <table>
            <thead>
              <tr>
                <th>Name</th>
                <th>Pending</th>
                <th>Last Updated</th>
              </tr>
            </thead>
            <tbody>
              {companies.map((c) => (
                <tr key={c.id}>
                  <td>
                    <Link to={`/companies/${c.id}`}>{c.name}</Link>
                  </td>
                  <td>{c.pending_count}</td>
                  <td>{new Date(c.updated_at).toLocaleDateString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="pagination">
            <button
              disabled={!hasPrev || loading}
              onClick={() => void fetchCompanies(offset - PAGE_SIZE)}
            >
              Previous
            </button>
            <span className="text-muted">
              Page {currentPage} of {totalPages} ({total} companies)
            </span>
            <button
              disabled={!hasNext || loading}
              onClick={() => void fetchCompanies(offset + PAGE_SIZE)}
            >
              Next
            </button>
          </div>
        </>
      )}
    </div>
  );
}

export default CompanyListPage;
