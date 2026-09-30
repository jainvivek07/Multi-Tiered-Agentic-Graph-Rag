import React, { useState, useCallback, useEffect } from 'react';
import { Upload, FileText, CheckCircle, XCircle, Loader, Trash2, ChevronDown, ChevronRight, FolderOpen } from 'lucide-react';
import { adminApi } from '../../../api/adminApi';
import { sessionApi } from '../../../api/chatApi';
import { GlassCard } from '../../../components/ui/GlassCard';
import { Badge } from '../../../components/ui/Badge';
import { DocumentModal } from '../../../components/ui/DocumentModal';
import styles from './IngestionView.module.css';

interface QueuedDoc {
  id: string;
  filename: string;
  category: string;
  status: 'pending' | 'uploading' | 'queued' | 'failed';
  error?: string;
}

interface RemoteDoc {
  id: string;
  filename: string;
  category: string;
  status: string;
  created_at: string;
}

const ALLOWED_TYPES = ['application/pdf', 'text/html', 'text/plain'];
const ALLOWED_EXTS = ['.pdf', '.html', '.htm', '.txt'];

export function IngestionView() {
  const [docs, setDocs] = useState<QueuedDoc[]>([]);
  const [category, setCategory] = useState('');
  const [customCategory, setCustomCategory] = useState('');
  const [existingCategories, setExistingCategories] = useState<string[]>([]);
  const [isDragOver, setIsDragOver] = useState(false);

  // Per-category expanded state and loaded docs
  const [expandedCats, setExpandedCats] = useState<Set<string>>(new Set());
  const [catDocs, setCatDocs] = useState<Record<string, RemoteDoc[]>>({});
  const [catDocsLoading, setCatDocsLoading] = useState<Record<string, boolean>>({});
  const [deletingDocId, setDeletingDocId] = useState<string | null>(null);
  const [openDoc, setOpenDoc] = useState<{ id: string; filename: string } | null>(null);

  const isNewMode = category === 'NEW' || existingCategories.length === 0;
  const effectiveCategory = isNewMode ? customCategory : category;

  const fetchCategories = useCallback(() => {
    sessionApi.getCategories().then(cats => {
      setExistingCategories(cats);
      if (cats.length > 0 && !category) setCategory(cats[0]);
    }).catch(console.error);
  }, [category]);

  useEffect(() => {
    fetchCategories();
  }, [fetchCategories]);

  // Toggle expand / collapse a category row and lazy-load its docs
  const toggleCategory = async (cat: string) => {
    setExpandedCats(prev => {
      const next = new Set(prev);
      if (next.has(cat)) {
        next.delete(cat);
      } else {
        next.add(cat);
      }
      return next;
    });

    // Fetch docs if not already loaded or category just expanded
    if (!expandedCats.has(cat) && !catDocs[cat]) {
      setCatDocsLoading(prev => ({ ...prev, [cat]: true }));
      try {
        const data = await adminApi.listCategoryDocuments(cat);
        setCatDocs(prev => ({ ...prev, [cat]: data }));
      } catch (err) {
        console.error('Failed to load documents for', cat, err);
        setCatDocs(prev => ({ ...prev, [cat]: [] }));
      } finally {
        setCatDocsLoading(prev => ({ ...prev, [cat]: false }));
      }
    }
  };

  const handleDeleteCategory = async (cat: string) => {
    if (!window.confirm(`Delete category "${cat}" and ALL its documents?`)) return;
    try {
      await adminApi.deleteCategory(cat);
      if (category === cat) setCategory('');
      setCatDocs(prev => { const n = { ...prev }; delete n[cat]; return n; });
      fetchCategories();
    } catch (err) {
      console.error(err);
      alert('Failed to delete category');
    }
  };

  const handleDeleteDocument = async (cat: string, docId: string) => {
    if (!window.confirm('Delete this document?')) return;
    setDeletingDocId(docId);
    try {
      await adminApi.deleteDocument(docId);
      setCatDocs(prev => ({
        ...prev,
        [cat]: (prev[cat] ?? []).filter(d => d.id !== docId),
      }));
    } catch (err) {
      console.error(err);
      alert('Failed to delete document');
    } finally {
      setDeletingDocId(null);
    }
  };

  const processFiles = useCallback(
    async (files: File[]) => {
      const valid = files.filter((f) => {
        const ext = '.' + f.name.split('.').pop()?.toLowerCase();
        return ALLOWED_TYPES.includes(f.type) || ALLOWED_EXTS.includes(ext);
      });

      const targetCategory = effectiveCategory.trim().toLowerCase();
      if (!valid.length || !targetCategory) return;

      const newDocs: QueuedDoc[] = valid.map((f) => ({
        id: crypto.randomUUID(),
        filename: f.name,
        category: targetCategory,
        status: 'pending',
      }));

      setDocs((prev) => [...newDocs, ...prev]);

      for (const [i, file] of valid.entries()) {
        const docId = newDocs[i].id;
        setDocs((prev) =>
          prev.map((d) => (d.id === docId ? { ...d, status: 'uploading' } : d)),
        );

        try {
          await adminApi.uploadDocument(file, targetCategory);
          setDocs((prev) =>
            prev.map((d) => (d.id === docId ? { ...d, status: 'queued' } : d)),
          );
          // Invalidate the cached doc list for this category so it refreshes
          setCatDocs(prev => { const n = { ...prev }; delete n[targetCategory]; return n; });
        } catch (err) {
          setDocs((prev) =>
            prev.map((d) =>
              d.id === docId
                ? { ...d, status: 'failed', error: (err as Error).message }
                : d,
            ),
          );
        }
      }
    },
    [effectiveCategory],
  );

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
    processFiles(Array.from(e.dataTransfer.files));
  };

  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) processFiles(Array.from(e.target.files));
    e.target.value = '';
  };

  const statusBadge = (status: QueuedDoc['status']) => {
    switch (status) {
      case 'uploading': return <Badge variant="amber"><Loader size={10} className={styles.spin} /> Uploading</Badge>;
      case 'queued':    return <Badge variant="emerald"><CheckCircle size={10} /> Queued</Badge>;
      case 'failed':    return <Badge variant="rose"><XCircle size={10} /> Failed</Badge>;
      default:          return <Badge variant="muted">Pending</Badge>;
    }
  };

  const remoteStatusBadge = (status: string) => {
    switch (status) {
      case 'completed':  return <Badge variant="emerald" size="sm">completed</Badge>;
      case 'processing': return <Badge variant="amber" size="sm">processing</Badge>;
      case 'failed':     return <Badge variant="rose" size="sm">failed</Badge>;
      default:           return <Badge variant="muted" size="sm">{status}</Badge>;
    }
  };

  return (
    <div className={styles.view}>
      <h2 className={styles.heading}>Document Ingestion</h2>
      <p className={styles.sub}>
        Upload PDF, HTML, or TXT files. Each document is queued for asynchronous parsing,
        chunking, embedding, and Neo4j graph construction.
      </p>

      {/* Controls */}
      <div className={styles.controls}>
        {existingCategories.length > 0 && (
          <select
            value={category}
            onChange={(e) => {
              setCategory(e.target.value);
              if (e.target.value !== 'NEW') setCustomCategory('');
            }}
            className={styles.categorySelect}
            style={{ width: '220px' }}
          >
            <option value="" disabled>Select category...</option>
            {existingCategories.map((c) => (
              <option key={c} value={c}>{c}</option>
            ))}
            <option value="NEW">+ Create New Category</option>
          </select>
        )}

        {isNewMode && (
          <input
            type="text"
            value={customCategory}
            onChange={(e) => setCustomCategory(e.target.value)}
            placeholder="New Category Name (e.g., hr-policy)"
            className={styles.categorySelect}
            style={{ width: '300px' }}
          />
        )}
      </div>

      {/* Dropzone */}
      <label
        className={[styles.dropzone, isDragOver ? styles.dragOver : ''].join(' ')}
        onDragOver={(e) => { e.preventDefault(); setIsDragOver(true); }}
        onDragLeave={() => setIsDragOver(false)}
        onDrop={handleDrop}
        aria-label="Drop files here or click to upload"
      >
        <input
          type="file"
          multiple
          accept=".pdf,.html,.htm,.txt"
          onChange={handleFileInput}
          className={styles.fileInput}
          aria-hidden
        />
        <Upload size={32} className={styles.uploadIcon} />
        <p className={styles.dropText}>Drop files here or <span className={styles.browse}>click to browse</span></p>
        <p className={styles.dropHint}>PDF · HTML · TXT</p>
      </label>

      {/* Queue */}
      {docs.length > 0 && (
        <GlassCard padding="none" className={styles.queue}>
          {docs.map((doc) => (
            <div key={doc.id} className={styles.queueItem}>
              <FileText size={16} className={styles.fileIcon} />
              <div className={styles.fileInfo}>
                <span className={styles.filename}>{doc.filename}</span>
                <span className={styles.docCategory}>{doc.category}</span>
              </div>
              <div className={styles.docStatus}>{statusBadge(doc.status)}</div>
              {doc.error && <p className={styles.errorText}>{doc.error}</p>}
            </div>
          ))}
        </GlassCard>
      )}

      {/* Manage Categories — expandable with per-doc delete */}
      {existingCategories.length > 0 && (
        <div className={styles.manageSection}>
          <h3 className={styles.manageHeading}>Manage Categories</h3>
          <GlassCard padding="none" className={styles.categoryList}>
            {existingCategories.map((cat) => {
              const isExpanded = expandedCats.has(cat);
              const docs = catDocs[cat];
              const isLoadingDocs = catDocsLoading[cat];

              return (
                <div key={cat}>
                  {/* Category row */}
                  <div className={styles.categoryItem}>
                    {/* Expand toggle */}
                    <button
                      type="button"
                      className={styles.expandBtn}
                      onClick={() => toggleCategory(cat)}
                      title={isExpanded ? 'Collapse' : 'Show documents'}
                    >
                      {isExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                    </button>

                    <FolderOpen size={14} className={styles.folderIcon} />
                    <span className={styles.categoryName}>{cat}</span>

                    {docs && (
                      <span className={styles.docCount}>{docs.length} doc{docs.length !== 1 ? 's' : ''}</span>
                    )}

                    <button
                      type="button"
                      onClick={() => handleDeleteCategory(cat)}
                      className={styles.deleteBtn}
                      title="Delete entire category"
                    >
                      <Trash2 size={14} />
                      <span className={styles.deleteBtnLabel}>Delete all</span>
                    </button>
                  </div>

                  {/* Documents list (expanded) */}
                  {isExpanded && (
                    <div className={styles.docList}>
                      {isLoadingDocs ? (
                        <div className={styles.docListLoading}>
                          <Loader size={12} className={styles.spin} />
                          <span>Loading documents…</span>
                        </div>
                      ) : docs && docs.length > 0 ? (
                        docs.map((doc) => (
                          <div key={doc.id} className={styles.docListItem}>
                            <FileText size={12} className={styles.docIcon} />
                            <span
                              className={styles.docFilename}
                              title={`Click to open ${doc.filename}`}
                              onClick={() => setOpenDoc({ id: doc.id, filename: doc.filename })}
                              style={{ cursor: 'pointer', textDecoration: 'underline dotted' }}
                            >
                              {doc.filename}
                            </span>
                            <span className={styles.docItemStatus}>
                              {remoteStatusBadge(doc.status)}
                            </span>
                            <span className={styles.docDate}>
                              {doc.created_at ? new Date(doc.created_at).toLocaleDateString() : '—'}
                            </span>
                            <button
                              type="button"
                              className={styles.docDeleteBtn}
                              disabled={deletingDocId === doc.id}
                              onClick={() => handleDeleteDocument(cat, doc.id)}
                              title="Delete this document"
                            >
                              {deletingDocId === doc.id
                                ? <Loader size={12} className={styles.spin} />
                                : <Trash2 size={12} />}
                            </button>
                          </div>
                        ))
                      ) : (
                        <div className={styles.docListEmpty}>No documents in this category.</div>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </GlassCard>
        </div>
      )}

      {/* Document viewer modal */}
      {openDoc && (
        <DocumentModal
          docId={openDoc.id}
          filename={openDoc.filename}
          onClose={() => setOpenDoc(null)}
        />
      )}
    </div>
  );
}
