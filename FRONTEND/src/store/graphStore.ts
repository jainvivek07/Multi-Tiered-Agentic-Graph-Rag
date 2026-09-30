import { create } from 'zustand';

export interface GraphNode {
  id: string;
  label: string;
  type: 'entity' | 'chunk';
  category?: string;
  content?: string;
  metadata?: Record<string, unknown>;
  // 3D positions (set by force simulation)
  x?: number;
  y?: number;
  z?: number;
}

export interface GraphLink {
  source: string;
  target: string;
  type?: string;
}

export interface GraphData {
  nodes: GraphNode[];
  links: GraphLink[];
}

interface GraphState {
  data: GraphData;
  activeCitationId: string | null;       // triggers camera fly-to
  highlightedNodeIds: Set<string>;        // nodes from current query's citations
  selectedNodeId: string | null;          // node inspector panel
  isLoading: boolean;

  setData: (d: GraphData) => void;
  setActiveCitation: (id: string | null) => void;
  setHighlightedNodes: (ids: string[]) => void;
  setSelectedNode: (id: string | null) => void;
  setLoading: (v: boolean) => void;
}

export const useGraphStore = create<GraphState>()((set) => ({
  data: { nodes: [], links: [] },
  activeCitationId: null,
  highlightedNodeIds: new Set(),
  selectedNodeId: null,
  isLoading: false,

  setData: (d) => set({ data: d }),
  setActiveCitation: (id) => set({ activeCitationId: id }),
  setHighlightedNodes: (ids) => set({ highlightedNodeIds: new Set(ids) }),
  setSelectedNode: (id) => set({ selectedNodeId: id }),
  setLoading: (v) => set({ isLoading: v }),
}));
