import React, { useEffect, useState, useRef } from 'react';
import { X, ExternalLink, Loader, AlertCircle, FileText, Download } from 'lucide-react';
import { adminApi } from '../../api/adminApi';

interface DocumentModalProps {
  docId: string;
  filename: string;
  onClose: () => void;
  /** Optional: scroll to / highlight a chunk content within the doc */
  highlightText?: string;
}

type FileType = 'pdf' | 'html' | 'text' | 'image' | 'binary';

export function DocumentModal({ docId, filename, onClose, highlightText }: DocumentModalProps) {
  const [displayFilename, setDisplayFilename] = useState<string>(filename || 'Document');
  const [blobUrl, setBlobUrl] = useState<string | null>(null);
  const [textContent, setTextContent] = useState<string | null>(null);
  const [fileType, setFileType] = useState<FileType | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const overlayRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let objectUrl: string | null = null;
    let isCancelled = false;

    const load = async () => {
      try {
        setLoading(true);
        setError(null);

        const url = adminApi.getDocumentFileUrl(docId);
        const res = await fetch(url, { credentials: 'include' });

        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          throw new Error((err as { detail?: string }).detail ?? `HTTP ${res.status}`);
        }

        // 1. Try to extract real filename from Content-Disposition header if available
        const disposition = res.headers.get('content-disposition');
        let resolvedFilename = filename;
        if (disposition) {
          const match = disposition.match(/filename\*?=(?:UTF-8'')?["']?([^"';\n]+)["']?/i);
          if (match && match[1]) {
            const parsed = decodeURIComponent(match[1].trim());
            if (parsed) {
              resolvedFilename = parsed;
              if (!isCancelled) setDisplayFilename(parsed);
            }
          }
        }

        const contentType = (res.headers.get('content-type') || '').toLowerCase();
        const ext = resolvedFilename.split('.').pop()?.toLowerCase() ?? '';

        const isKnownTxt =
          contentType.startsWith('text/plain') ||
          ['txt', 'log'].includes(ext);

        if (isKnownTxt) {
          const text = await res.text();
          if (!isCancelled) {
            setTextContent(text);
            setFileType('text');
          }
          return;
        }

        const rawBlob = await res.blob();
        if (isCancelled) return;

        // Check if PDF by MIME, extension, or '%PDF-' magic bytes
        const magicHeader = await rawBlob.slice(0, 5).text().catch(() => '');
        const isPdf =
          contentType.includes('pdf') ||
          ext === 'pdf' ||
          magicHeader === '%PDF-';

        if (isPdf) {
          const pdfBlob =
            rawBlob.type === 'application/pdf'
              ? rawBlob
              : new Blob([rawBlob], { type: 'application/pdf' });
          objectUrl = URL.createObjectURL(pdfBlob);
          setBlobUrl(objectUrl);
          setFileType('pdf');
          return;
        }

        // Check if HTML
        const isHtml =
          contentType.includes('html') ||
          ext === 'html' ||
          ext === 'htm';

        if (isHtml) {
          const htmlBlob = rawBlob.type.includes('html')
            ? rawBlob
            : new Blob([rawBlob], { type: 'text/html' });
          objectUrl = URL.createObjectURL(htmlBlob);
          setBlobUrl(objectUrl);
          setFileType('html');
          return;
        }

        // Check if Image
        const isImage =
          contentType.startsWith('image/') ||
          ['png', 'jpg', 'jpeg', 'gif', 'webp', 'svg'].includes(ext);

        if (isImage) {
          objectUrl = URL.createObjectURL(rawBlob);
          setBlobUrl(objectUrl);
          setFileType('image');
          return;
        }

        // Try reading as text if not binary
        const sample = await rawBlob.slice(0, 2000).text().catch(() => '\u0000');
        if (!sample.includes('\u0000')) {
          const fullText = await rawBlob.text();
          if (!isCancelled) {
            setTextContent(fullText);
            setFileType('text');
          }
        } else {
          objectUrl = URL.createObjectURL(rawBlob);
          setBlobUrl(objectUrl);
          setFileType('binary');
        }
      } catch (e) {
        if (!isCancelled) {
          setError(e instanceof Error ? e.message : 'Failed to load document');
        }
      } finally {
        if (!isCancelled) {
          setLoading(false);
        }
      }
    };

    load();

    return () => {
      isCancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [docId, filename]);

  // Close on overlay click
  const handleOverlayClick = (e: React.MouseEvent) => {
    if (e.target === overlayRef.current) onClose();
  };

  // Close on Escape
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [onClose]);

  return (
    <div
      ref={overlayRef}
      onClick={handleOverlayClick}
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(0,0,0,0.7)',
        backdropFilter: 'blur(6px)',
        zIndex: 1000,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '24px',
      }}
    >
      <div
        style={{
          background: 'var(--bg-surface)',
          border: '1px solid var(--border)',
          borderRadius: '16px',
          display: 'flex',
          flexDirection: 'column',
          width: '90vw',
          maxWidth: '1100px',
          height: '88vh',
          overflow: 'hidden',
          boxShadow: '0 32px 64px rgba(0,0,0,0.5)',
        }}
      >
        {/* Header */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '10px',
            padding: '14px 20px',
            borderBottom: '1px solid var(--border)',
            background: 'var(--bg-card)',
            flexShrink: 0,
          }}
        >
          <span
            style={{
              flex: 1,
              fontSize: 'var(--text-sm)',
              fontWeight: 600,
              color: 'var(--text-primary)',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}
            title={displayFilename}
          >
            {displayFilename}
          </span>

          {/* Open in new tab (if blobUrl available) */}
          {blobUrl && (
            <a
              href={blobUrl}
              target="_blank"
              rel="noopener noreferrer"
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '4px',
                color: 'var(--accent)',
                fontSize: 'var(--text-xs)',
                textDecoration: 'none',
                padding: '4px 8px',
                borderRadius: '6px',
                background: 'rgba(99,102,241,0.12)',
                border: '1px solid rgba(99,102,241,0.3)',
              }}
            >
              <ExternalLink size={12} />
              Open in tab
            </a>
          )}

          <button
            onClick={onClose}
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              width: '28px',
              height: '28px',
              borderRadius: '8px',
              background: 'transparent',
              border: '1px solid var(--border)',
              color: 'var(--text-muted)',
              cursor: 'pointer',
              flexShrink: 0,
            }}
          >
            <X size={14} />
          </button>
        </div>

        {/* Body */}
        <div style={{ flex: 1, overflow: 'hidden', position: 'relative' }}>
          {loading && (
            <div
              style={{
                position: 'absolute',
                inset: 0,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                flexDirection: 'column',
                gap: '12px',
                color: 'var(--text-muted)',
              }}
            >
              <Loader size={24} style={{ animation: 'spin 1s linear infinite' }} />
              <span style={{ fontSize: 'var(--text-sm)' }}>Loading document…</span>
            </div>
          )}

          {error && (
            <div
              style={{
                position: 'absolute',
                inset: 0,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                flexDirection: 'column',
                gap: '8px',
                padding: '24px',
              }}
            >
              <AlertCircle size={32} style={{ color: '#ef4444', opacity: 0.7 }} />
              <span style={{ color: '#ef4444', fontSize: 'var(--text-sm)', fontWeight: 500 }}>
                {error.toLowerCase().includes('not found') || error.includes('404')
                  ? 'Source Document Not Found on Disk'
                  : error}
              </span>
              {(error.toLowerCase().includes('not found') || error.includes('404')) && (
                <span
                  style={{
                    color: 'var(--text-muted)',
                    fontSize: 'var(--text-xs)',
                    maxWidth: '400px',
                    textAlign: 'center',
                    lineHeight: 1.5,
                  }}
                >
                  This document was ingested before permanent file storage was enabled, or was deleted from the server. Re-uploading it will enable viewing the original file.
                </span>
              )}
            </div>
          )}

          {!loading && !error && fileType === 'text' && textContent !== null && (
            <div style={{ height: '100%', overflow: 'auto', padding: '20px' }}>
              {highlightText ? (
                <HighlightedText text={textContent} highlight={highlightText} />
              ) : (
                <pre
                  style={{
                    margin: 0,
                    fontFamily: 'var(--font-mono, monospace)',
                    fontSize: '13px',
                    lineHeight: '1.7',
                    color: 'var(--text-primary)',
                    whiteSpace: 'pre-wrap',
                    wordBreak: 'break-word',
                  }}
                >
                  {textContent}
                </pre>
              )}
            </div>
          )}

          {!loading && !error && fileType === 'pdf' && blobUrl && (
            <object
              data={blobUrl}
              type="application/pdf"
              style={{ width: '100%', height: '100%', border: 'none', display: 'block' }}
            >
              <iframe
                src={blobUrl}
                style={{ width: '100%', height: '100%', border: 'none' }}
                title={displayFilename}
              />
            </object>
          )}

          {!loading && !error && fileType === 'html' && blobUrl && (
            <iframe
              src={blobUrl}
              style={{ width: '100%', height: '100%', border: 'none', background: '#fff' }}
              title={displayFilename}
              sandbox="allow-same-origin"
            />
          )}

          {!loading && !error && fileType === 'image' && blobUrl && (
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                height: '100%',
                padding: '24px',
                overflow: 'auto',
              }}
            >
              <img
                src={blobUrl}
                alt={displayFilename}
                style={{
                  maxWidth: '100%',
                  maxHeight: '100%',
                  objectFit: 'contain',
                  borderRadius: '8px',
                }}
              />
            </div>
          )}

          {!loading && !error && fileType === 'binary' && (
            <div
              style={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                height: '100%',
                gap: '16px',
                padding: '24px',
                color: 'var(--text-muted)',
              }}
            >
              <FileText size={48} style={{ opacity: 0.5 }} />
              <div style={{ fontSize: 'var(--text-sm)', textAlign: 'center' }}>
                Preview not available for this file type in the modal.
              </div>
              {blobUrl && (
                <a
                  href={blobUrl}
                  download={displayFilename}
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '6px',
                    padding: '8px 16px',
                    borderRadius: '8px',
                    background: 'var(--accent)',
                    color: '#fff',
                    fontSize: 'var(--text-xs)',
                    fontWeight: 600,
                    textDecoration: 'none',
                  }}
                >
                  <Download size={14} /> Download File
                </a>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

/** Renders text with a highlighted snippet (first occurrence). */
function HighlightedText({ text, highlight }: { text: string; highlight: string }) {
  const idx = text.toLowerCase().indexOf(highlight.toLowerCase().substring(0, 50));
  if (idx === -1) {
    return (
      <pre
        style={{
          margin: 0,
          fontFamily: 'monospace',
          fontSize: '13px',
          lineHeight: '1.7',
          color: 'var(--text-primary)',
          whiteSpace: 'pre-wrap',
          wordBreak: 'break-word',
        }}
      >
        {text}
      </pre>
    );
  }

  const before = text.slice(0, idx);
  const match = text.slice(idx, idx + highlight.length);
  const after = text.slice(idx + highlight.length);

  return (
    <pre
      style={{
        margin: 0,
        fontFamily: 'monospace',
        fontSize: '13px',
        lineHeight: '1.7',
        color: 'var(--text-primary)',
        whiteSpace: 'pre-wrap',
        wordBreak: 'break-word',
      }}
    >
      {before}
      <mark
        style={{
          background: 'rgba(251,191,36,0.35)',
          borderRadius: '2px',
          padding: '0 2px',
        }}
      >
        {match}
      </mark>
      {after}
    </pre>
  );
}
