import { useEffect, useMemo, useRef } from 'react';
import { useFrame } from '@react-three/fiber';
import { 
  forceSimulation, 
  forceLink, 
  forceManyBody, 
  forceCenter 
} from 'd3-force-3d';
import { useGraphStore } from '../../store/graphStore';
import { EntityNode } from './EntityNode';
import { ChunkNode } from './ChunkNode';
import { GraphLink } from './GraphLink';

export function GraphScene() {
  const { data, highlightedNodeIds, selectedNodeId, setSelectedNode } = useGraphStore();

  // Create mutable copies of data for the D3 simulation
  const simData = useMemo(() => {
    // If we have no data, generate some dummy data for preview/development
    // In production, this data comes from the activeSession's context or a global fetch
    if (!data.nodes.length) {
      return { nodes: [], links: [] };
    }

    const nodes = data.nodes.map(n => ({ ...n }));
    const links = data.links.map(l => ({ ...l }));
    return { nodes, links };
  }, [data]);

  const simulationRef = useRef<any>(null);

  // Initialize D3 Force Simulation
  useEffect(() => {
    if (!simData.nodes.length) return;

    // Reset coordinates if they don't exist
    simData.nodes.forEach((n: any) => {
      n.x = n.x ?? (Math.random() - 0.5) * 100;
      n.y = n.y ?? (Math.random() - 0.5) * 100;
      n.z = n.z ?? (Math.random() - 0.5) * 100;
    });

    const sim = forceSimulation(simData.nodes)
      .numDimensions(3)
      .force('link', forceLink(simData.links).id((d: any) => d.id).distance(80))
      .force('charge', forceManyBody().strength(-400))
      .force('center', forceCenter(0, 0, 0))
      .stop();

    // Run simulation synchronously for 100 ticks to pre-warm the layout
    // This prevents the graph from "exploding" on first load
    for (let i = 0; i < 100; i++) sim.tick();

    // Then let it run smoothly
    sim.restart();
    simulationRef.current = sim;

    return () => {
      sim.stop();
    };
  }, [simData]);

  // Sync D3 positions back to the Zustand store (throttle to avoid infinite re-renders)
  // Actually, for performance in R3F, it's better to NOT push frame-by-frame coords 
  // into Zustand. Instead, we mutate the store's nodes in place, or use a ref.
  // The React components below will read from `simData` directly on render.
  useFrame(() => {
    if (simulationRef.current) {
      // D3 modifies the simData.nodes in place
      // We don't trigger a React render here. The Object3Ds are bound to these nodes.
    }
  });

  if (!simData.nodes.length) return null;

  return (
    <group>
      {/* Links */}
      {simData.links.map((link: any, i) => (
        <GraphLink 
          key={`link-${i}`} 
          source={link.source} 
          target={link.target} 
          type={link.type}
        />
      ))}

      {/* Nodes */}
      {simData.nodes.map((node: any) => {
        const isHighlighted = highlightedNodeIds.has(node.id);
        const isSelected = selectedNodeId === node.id;
        
        return node.type === 'entity' ? (
          <EntityNode
            key={node.id}
            node={node}
            isHighlighted={isHighlighted}
            isSelected={isSelected}
            onClick={(e) => { e.stopPropagation(); setSelectedNode(node.id); }}
          />
        ) : (
          <ChunkNode
            key={node.id}
            node={node}
            isHighlighted={isHighlighted}
            isSelected={isSelected}
            onClick={(e) => { e.stopPropagation(); setSelectedNode(node.id); }}
          />
        );
      })}
    </group>
  );
}
