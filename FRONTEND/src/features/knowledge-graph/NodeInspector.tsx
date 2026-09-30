import { X, Network, FileText } from 'lucide-react';
import { useGraphStore } from '../../store/graphStore';
import { Badge } from '../../components/ui/Badge';
import { GlassCard } from '../../components/ui/GlassCard';
import styles from './NodeInspector.module.css';

export function NodeInspector() {
  const { data, selectedNodeId, setSelectedNode } = useGraphStore();
  const node = data.nodes.find(n => n.id === selectedNodeId);

  if (!node) return null;

  const isEntity = node.type === 'entity';

  return (
    <GlassCard padding="none" elevated className={styles.inspector}>
      {/* Header */}
      <div className={styles.header}>
        <div className={styles.titleRow}>
          <div className={[styles.iconBox, isEntity ? styles.iconEntity : styles.iconChunk].join(' ')}>
            {isEntity ? <Network size={16} /> : <FileText size={16} />}
          </div>
          <h3 className={styles.title} title={node.label}>{node.label}</h3>
        </div>
        <button onClick={() => setSelectedNode(null)} className={styles.closeBtn} aria-label="Close inspector">
          <X size={16} />
        </button>
      </div>

      {/* Body */}
      <div className={styles.body}>
        <div className={styles.metaRow}>
          <Badge variant={isEntity ? 'violet' : 'cyan'}>
            {isEntity ? 'Entity' : 'Document Chunk'}
          </Badge>
          {node.category && <Badge variant="muted">{node.category}</Badge>}
        </div>

        {/* Content for chunks */}
        {node.content && (
          <div className={styles.section}>
            <p className={styles.sectionTitle}>Content Snippet</p>
            <div className={styles.contentBlock}>
              {node.content}
            </div>
          </div>
        )}

        {/* Metadata properties */}
        {node.metadata && Object.keys(node.metadata).length > 0 && (
          <div className={styles.section}>
            <p className={styles.sectionTitle}>Properties</p>
            <dl className={styles.propList}>
              {Object.entries(node.metadata).map(([key, value]) => (
                <div key={key} className={styles.propItem}>
                  <dt className={styles.propKey}>{key}</dt>
                  <dd className={styles.propVal}>{String(value)}</dd>
                </div>
              ))}
            </dl>
          </div>
        )}

        {/* ID Reference */}
        <div className={styles.section}>
          <p className={styles.sectionTitle}>System ID</p>
          <code className={styles.sysId}>{node.id}</code>
        </div>
      </div>
    </GlassCard>
  );
}
