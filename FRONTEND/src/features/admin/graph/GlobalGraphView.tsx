import React, { useEffect, useState } from 'react';
import neo4j from 'neo4j-driver';
import type { Node, Relationship } from '@neo4j-nvl/base';
import { InteractiveNvlWrapper } from '@neo4j-nvl/react';

// ─── Label → colour mapping ───────────────────────────────────────────────────
const LABEL_COLORS: Record<string, string> = {
  Chunk:    '#FF7F0E',  // orange
  Document: '#1F77B4',  // blue
  Entity:   '#2CA02C',  // green
  Default:  '#4A90E2',  // fallback
};

const getDotStyle = (color: string): React.CSSProperties => ({
  width: 10,
  height: 10,
  borderRadius: '50%',
  background: color,
  flexShrink: 0,
});

// ─── Neo4j credentials from Vite env vars ────────────────────────────────────
const NEO4J_URL      = import.meta.env.VITE_NEO4J_URI      ?? 'neo4j+ssc://localhost:7687';
const NEO4J_USERNAME = import.meta.env.VITE_NEO4J_USERNAME ?? 'neo4j';
const NEO4J_PASSWORD = import.meta.env.VITE_NEO4J_PASSWORD ?? '';
const DEFAULT_QUERY  = 'MATCH (n)-[r]->(m) RETURN n, r, m LIMIT 100';

// ─── Styles ───────────────────────────────────────────────────────────────────
const s: Record<string, React.CSSProperties> = {
  root: {
    display: 'flex',
    flexDirection: 'column',
    height: '100%',
    background: 'var(--bg-base)',
    color: 'var(--text-primary)',
    fontFamily: 'var(--font-sans)',
  },
  canvas: {
    flex: 1,
    position: 'relative',
    overflow: 'hidden',
  },
  overlay: {
    position: 'absolute',
    inset: 0,
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    gap: '8px',
    color: 'var(--text-muted)',
    fontSize: 'var(--text-sm)',
  },
  error: {
    padding: '8px 16px',
    background: 'rgba(239,68,68,0.15)',
    border: '1px solid rgba(239,68,68,0.4)',
    borderRadius: '8px',
    color: '#ef4444',
    fontSize: 'var(--text-sm)',
    maxWidth: '480px',
    textAlign: 'center',
  },
  legend: {
    position: 'absolute',
    bottom: '12px',
    left: '12px',
    background: 'rgba(0,0,0,0.6)',
    backdropFilter: 'blur(8px)',
    border: '1px solid var(--border)',
    borderRadius: '8px',
    padding: '8px 12px',
    display: 'flex',
    flexDirection: 'column',
    gap: '4px',
    zIndex: 10,
    pointerEvents: 'none',
  },
  legendItem: {
    display: 'flex',
    alignItems: 'center',
    gap: '6px',
    fontSize: '11px',
    color: 'var(--text-muted)',
  },
  stats: {
    position: 'absolute',
    top: '12px',
    right: '12px',
    background: 'rgba(0,0,0,0.6)',
    backdropFilter: 'blur(8px)',
    border: '1px solid var(--border)',
    borderRadius: '8px',
    padding: '6px 12px',
    fontSize: '11px',
    color: 'var(--text-muted)',
    zIndex: 10,
    pointerEvents: 'none',
  },
  hint: {
    position: 'absolute',
    bottom: '12px',
    right: '12px',
    background: 'rgba(0,0,0,0.5)',
    backdropFilter: 'blur(8px)',
    border: '1px solid var(--border)',
    borderRadius: '8px',
    padding: '5px 10px',
    fontSize: '10px',
    color: 'var(--text-muted)',
    zIndex: 10,
    pointerEvents: 'none',
  },
};

export function GlobalGraphView() {
  const [nodes, setNodes]        = useState<Node[]>([]);
  const [relationships, setRels] = useState<Relationship[]>([]);
  const [loading, setLoading]    = useState(true);
  const [error, setError]        = useState<string | null>(null);

  useEffect(() => {
    let driver: ReturnType<typeof neo4j.driver> | undefined;

    const fetchGraph = async () => {
      setLoading(true);
      setError(null);
      try {
        driver = neo4j.driver(NEO4J_URL, neo4j.auth.basic(NEO4J_USERNAME, NEO4J_PASSWORD));
        const result = await driver.executeQuery(DEFAULT_QUERY);

        const nodesMap = new Map<string, Node>();
        const relsMap  = new Map<string, Relationship>();

        result.records.forEach((record) => {
          record.keys.forEach((key) => {
            const item = record.get(key);
            if (!item) return;

            // ── Nodes ──────────────────────────────────────────────────────────
            if (item.labels && (item.elementId || item.identity)) {
              const id = item.elementId || item.identity.toString();
              if (!nodesMap.has(id)) {
                const props        = item.properties || {};
                const primaryLabel = item.labels[0] || 'Node';
                const raw = String(
                  props.id    ||
                  props.name  ||
                  props.title ||
                  props.text  ||
                  props.value ||
                  primaryLabel,
                ).trim();
                const caption = raw.length > 8 ? raw.substring(0, 6) + '..' : raw;
                nodesMap.set(id, {
                  id,
                  size: 50,
                  color: LABEL_COLORS[primaryLabel] || LABEL_COLORS.Default,
                  captions: [{ value: caption }],
                } as Node);
              }
            }

            // ── Relationships ──────────────────────────────────────────────────
            if (item.type && item.startNodeElementId && item.endNodeElementId) {
              const relId = item.elementId || item.identity?.toString();
              if (!relsMap.has(relId)) {
                relsMap.set(relId, {
                  id:      relId,
                  from:    item.startNodeElementId,
                  to:      item.endNodeElementId,
                  caption: item.type,
                } as Relationship);
              }
            }
          });
        });

        setNodes(Array.from(nodesMap.values()));
        setRels(Array.from(relsMap.values()));
      } catch (err: unknown) {
        console.error(err);
        setError(err instanceof Error ? err.message : 'Failed to connect to Neo4j.');
      } finally {
        if (driver) await driver.close();
        setLoading(false);
      }
    };

    fetchGraph();
  }, []); // run once on mount

  return (
    <div style={s.root}>
      {/* ── Graph canvas ─────────────────────────────────────────────────── */}
      <div style={s.canvas}>
        {loading && (
          <div style={s.overlay}>
            <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" style={{ opacity: 0.5, animation: 'spin 1.2s linear infinite' }}>
              <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83" />
            </svg>
            <span>Loading knowledge graph…</span>
          </div>
        )}

        {!loading && error && (
          <div style={s.overlay}>
            <span style={s.error}>{error}</span>
          </div>
        )}

        {!loading && !error && nodes.length === 0 && (
          <div style={s.overlay}>
            <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" style={{ opacity: 0.4 }}>
              <circle cx="12" cy="12" r="3" /><circle cx="3" cy="5" r="2" /><circle cx="21" cy="5" r="2" /><circle cx="3" cy="19" r="2" /><circle cx="21" cy="19" r="2" />
              <line x1="5" y1="5" x2="10" y2="10" /><line x1="19" y1="5" x2="14" y2="10" /><line x1="5" y1="19" x2="10" y2="14" /><line x1="19" y1="19" x2="14" y2="14" />
            </svg>
            <span>No nodes found in the knowledge graph.</span>
          </div>
        )}

        {!loading && !error && nodes.length > 0 && (
          <>
            <InteractiveNvlWrapper
              nodes={nodes}
              rels={relationships}
              nvlOptions={{
                renderer: 'canvas',
                allowDynamicMinZoom: true,
                minZoom: 0.05,
                maxZoom: 5,
                initialZoom: 1,
              }}
            />

            {/* Stats HUD */}
            <div style={s.stats}>
              {nodes.length} nodes · {relationships.length} relationships
            </div>

            {/* Legend */}
            <div style={s.legend}>
              {Object.entries(LABEL_COLORS)
                .filter(([k]) => k !== 'Default')
                .map(([label, color]) => (
                  <div key={label} style={s.legendItem}>
                    <span style={getDotStyle(color)} />
                    {label}
                  </div>
                ))}
            </div>

            {/* Controls hint */}
            <div style={s.hint}>Scroll to zoom · Drag to pan · Click node to inspect</div>
          </>
        )}
      </div>
    </div>
  );
}
