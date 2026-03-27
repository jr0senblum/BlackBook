import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { deleteCompany, getCompany, updateCompany } from "../api/companies";
import { uploadSource } from "../api/sources";
import { listPending } from "../api/pending";
import { ApiRequestError } from "../api/client";
import type { CompanyDetail, PendingFactItem } from "../types";
import SourceList from "../components/SourceList";
import PendingReviewQueue from "../components/PendingReviewQueue";

function CompanyProfilePage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const [company, setCompany] = useState<CompanyDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // Edit state.
  const [editing, setEditing] = useState(false);
  const [editName, setEditName] = useState("");
  const [editMission, setEditMission] = useState("");
  const [editVision, setEditVision] = useState("");
  const [editError, setEditError] = useState("");
  const [saving, setSaving] = useState(false);

  // Delete state.
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [deleting, setDeleting] = useState(false);

  // Upload state.
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadMsg, setUploadMsg] = useState("");
  const [sourceRefreshKey, setSourceRefreshKey] = useState(0);

  // Accepted entities (Phase 2 workaround — reads from inferred_facts).
  // MUST be replaced in Phase 3 when dedicated entity endpoints exist.
  const [acceptedPersons, setAcceptedPersons] = useState<PendingFactItem[]>([]);
  const [acceptedTech, setAcceptedTech] = useState<PendingFactItem[]>([]);
  const [acceptedProcesses, setAcceptedProcesses] = useState<PendingFactItem[]>([]);
  const [acceptedAreas, setAcceptedAreas] = useState<PendingFactItem[]>([]);

  const fetchCompany = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    try {
      const data = await getCompany(id);
      setCompany(data);
      setEditName(data.name);
      setEditMission(data.mission ?? "");
      setEditVision(data.vision ?? "");
      setError("");
    } catch (err) {
      if (err instanceof ApiRequestError) {
        if (err.status === 401) {
          navigate("/login");
          return;
        }
        if (err.status === 404) {
          setError("Company not found.");
        } else {
          setError(err.error.message);
        }
      } else {
        setError("Failed to load company.");
      }
    } finally {
      setLoading(false);
    }
  }, [id, navigate]);

  const fetchAcceptedEntities = useCallback(async () => {
    if (!id) return;
    try {
      const [persons, tech, procs, areas] = await Promise.all([
        listPending(id, { status: "accepted", category: "person", limit: 200 }),
        listPending(id, { status: "accepted", category: "technology", limit: 200 }),
        listPending(id, { status: "accepted", category: "process", limit: 200 }),
        listPending(id, { status: "accepted", category: "functional-area", limit: 200 }),
      ]);
      setAcceptedPersons(persons.items);
      setAcceptedTech(tech.items);
      setAcceptedProcesses(procs.items);
      setAcceptedAreas(areas.items);
    } catch {
      // Non-critical — accepted entities are supplementary display.
    }
  }, [id]);

  useEffect(() => {
    void fetchCompany();
    void fetchAcceptedEntities();
  }, [fetchCompany, fetchAcceptedEntities]);

  async function handleSave(e: FormEvent) {
    e.preventDefault();
    if (!id) return;
    setEditError("");
    setSaving(true);
    try {
      const updated = await updateCompany(id, {
        name: editName,
        mission: editMission || undefined,
        vision: editVision || undefined,
      });
      setCompany(updated);
      setEditing(false);
    } catch (err) {
      if (err instanceof ApiRequestError) {
        if (err.error.code === "name_conflict") {
          setEditError("A company with this name already exists.");
        } else {
          setEditError(err.error.message);
        }
      } else {
        setEditError("Failed to update company.");
      }
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete() {
    if (!id) return;
    setDeleting(true);
    try {
      await deleteCompany(id);
      navigate("/");
    } catch (err) {
      if (err instanceof ApiRequestError) {
        setError(err.error.message);
      } else {
        setError("Failed to delete company.");
      }
      setDeleting(false);
      setConfirmDelete(false);
    }
  }

  async function handleUpload() {
    const file = fileInputRef.current?.files?.[0];
    if (!file || !id) return;
    setUploading(true);
    setUploadMsg("");
    try {
      await uploadSource(file, id);
      setUploadMsg("File uploaded successfully. Processing...");
      setSourceRefreshKey((k) => k + 1);
      // Clear file input.
      if (fileInputRef.current) fileInputRef.current.value = "";
    } catch (err) {
      if (err instanceof ApiRequestError) {
        setUploadMsg(err.error.message);
      } else {
        setUploadMsg("Upload failed.");
      }
    } finally {
      setUploading(false);
    }
  }

  function handleFactReviewed() {
    // Refresh company (pending_count) and accepted entities.
    void fetchCompany();
    void fetchAcceptedEntities();
  }

  if (loading) {
    return (
      <div className="page-content">
        <p className="text-muted">Loading...</p>
      </div>
    );
  }

  if (error && !company) {
    return (
      <div className="page-content">
        <div className="error-message">{error}</div>
        <button onClick={() => navigate("/")}>Back to Companies</button>
      </div>
    );
  }

  if (!company || !id) return null;

  return (
    <div className="page-content">
      <button className="link-button" onClick={() => navigate("/")}>
        &larr; Back to Companies
      </button>

      {!editing ? (
        <>
          <div className="page-header" style={{ marginTop: 16 }}>
            <h1>{company.name}</h1>
            <div>
              <button onClick={() => setEditing(true)}>Edit</button>
              <button
                className="danger"
                onClick={() => setConfirmDelete(true)}
                style={{ marginLeft: 8 }}
              >
                Delete
              </button>
            </div>
          </div>

          {error && <div className="error-message">{error}</div>}

          <div className="detail-section">
            <h3>Mission</h3>
            <p>{company.mission || "—"}</p>
          </div>
          <div className="detail-section">
            <h3>Vision</h3>
            <p>{company.vision || "—"}</p>
          </div>
          <div className="detail-section">
            <h3>Pending Items</h3>
            <p>{company.pending_count}</p>
          </div>

          <div className="detail-section text-muted">
            <p>
              Created: {new Date(company.created_at).toLocaleString()} | Last
              Updated: {new Date(company.updated_at).toLocaleString()}
            </p>
          </div>

          {/* ── Upload Notes ──────────────────────────────────── */}
          <hr />
          <div className="detail-section">
            <h3>Upload Notes</h3>
            <div className="upload-area">
              <input
                ref={fileInputRef}
                type="file"
                accept=".txt,.md,.text"
                disabled={uploading}
              />
              <button
                onClick={() => void handleUpload()}
                disabled={uploading}
                style={{ marginLeft: 8 }}
              >
                {uploading ? "Uploading..." : "Upload"}
              </button>
            </div>
            {uploadMsg && (
              <p
                className={
                  uploadMsg.includes("success")
                    ? "success-message"
                    : "error-message"
                }
                style={{ marginTop: 8 }}
              >
                {uploadMsg}
              </p>
            )}
          </div>

          {/* ── Pending Review ────────────────────────────────── */}
          {company.pending_count > 0 && (
            <div className="detail-section">
              <h3>Pending Review ({company.pending_count})</h3>
              <PendingReviewQueue
                companyId={id}
                onFactReviewed={handleFactReviewed}
              />
            </div>
          )}

          {/* ── Sources ───────────────────────────────────────── */}
          <hr />
          <div className="detail-section">
            <h3>Sources</h3>
            <SourceList companyId={id} refreshKey={sourceRefreshKey} />
          </div>

          {/* ── People (Phase 2 workaround) ───────────────────── */}
          <hr />
          <div className="detail-section">
            <h3>People</h3>
            {acceptedPersons.length > 0 ? (
              <ul className="entity-list">
                {acceptedPersons.map((p) => (
                  <li key={p.fact_id}>{p.inferred_value}</li>
                ))}
              </ul>
            ) : (
              <p className="text-muted">No people accepted yet.</p>
            )}
          </div>

          {/* ── Functional Areas ──────────────────────────────── */}
          <div className="detail-section">
            <h3>Functional Areas</h3>
            {acceptedAreas.length > 0 ? (
              <ul className="entity-list">
                {acceptedAreas.map((a) => (
                  <li key={a.fact_id}>{a.inferred_value}</li>
                ))}
              </ul>
            ) : (
              <p className="text-muted">No functional areas accepted yet.</p>
            )}
          </div>

          {/* ── Technologies ──────────────────────────────────── */}
          <div className="detail-section">
            <h3>Technologies</h3>
            {acceptedTech.length > 0 ? (
              <ul className="entity-list">
                {acceptedTech.map((t) => (
                  <li key={t.fact_id}>{t.inferred_value}</li>
                ))}
              </ul>
            ) : (
              <p className="text-muted">No technologies accepted yet.</p>
            )}
          </div>

          {/* ── Processes ─────────────────────────────────────── */}
          <div className="detail-section">
            <h3>Processes</h3>
            {acceptedProcesses.length > 0 ? (
              <ul className="entity-list">
                {acceptedProcesses.map((p) => (
                  <li key={p.fact_id}>{p.inferred_value}</li>
                ))}
              </ul>
            ) : (
              <p className="text-muted">No processes accepted yet.</p>
            )}
          </div>

          {/* Placeholder sections for future phases */}
          <hr />
          <div className="detail-section placeholder-section">
            <h3>Coverage</h3>
            <p className="text-muted">Coming in Phase 3</p>
          </div>
          <div className="detail-section placeholder-section">
            <h3>CGKRA</h3>
            <p className="text-muted">Coming in Phase 4</p>
          </div>

          {/* Delete confirmation modal */}
          {confirmDelete && (
            <div className="modal-overlay">
              <div className="card modal">
                <h2>Delete Company</h2>
                <p>
                  Are you sure you want to delete <strong>{company.name}</strong>
                  ? This will remove all associated data and cannot be undone.
                </p>
                <div style={{ display: "flex", gap: 8, marginTop: 16 }}>
                  <button
                    className="danger"
                    onClick={() => void handleDelete()}
                    disabled={deleting}
                  >
                    {deleting ? "Deleting..." : "Yes, Delete"}
                  </button>
                  <button onClick={() => setConfirmDelete(false)}>Cancel</button>
                </div>
              </div>
            </div>
          )}
        </>
      ) : (
        <>
          <h2 style={{ marginTop: 16 }}>Edit Company</h2>
          <form onSubmit={handleSave}>
            <div className="form-group">
              <label htmlFor="edit-name">Name *</label>
              <input
                id="edit-name"
                type="text"
                value={editName}
                onChange={(e) => setEditName(e.target.value)}
                required
                autoFocus
              />
            </div>
            <div className="form-group">
              <label htmlFor="edit-mission">Mission</label>
              <textarea
                id="edit-mission"
                value={editMission}
                onChange={(e) => setEditMission(e.target.value)}
                rows={3}
              />
            </div>
            <div className="form-group">
              <label htmlFor="edit-vision">Vision</label>
              <textarea
                id="edit-vision"
                value={editVision}
                onChange={(e) => setEditVision(e.target.value)}
                rows={3}
              />
            </div>
            {editError && <div className="error-message">{editError}</div>}
            <div style={{ display: "flex", gap: 8 }}>
              <button type="submit" disabled={saving}>
                {saving ? "Saving..." : "Save Changes"}
              </button>
              <button
                type="button"
                onClick={() => {
                  setEditing(false);
                  setEditError("");
                  setEditName(company.name);
                  setEditMission(company.mission ?? "");
                  setEditVision(company.vision ?? "");
                }}
              >
                Cancel
              </button>
            </div>
          </form>
        </>
      )}
    </div>
  );
}

export default CompanyProfilePage;
