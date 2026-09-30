import { useEffect, useRef } from 'react';
import { Canvas } from '@react-three/fiber';
import { CameraControls, Stars } from '@react-three/drei';
import { useGraphStore } from '../../store/graphStore';
import { GraphScene } from './GraphScene';
import { NodeInspector } from './NodeInspector';
import styles from './GraphCanvas.module.css';

export function GraphCanvas() {
  const cameraControlsRef = useRef<CameraControls>(null);
  const { data, activeCitationId, selectedNodeId, setSelectedNode } = useGraphStore();

  // Fly to active citation when it changes
  useEffect(() => {
    if (!activeCitationId || !cameraControlsRef.current || !data.nodes.length) return;
    
    const node = data.nodes.find(n => n.id === activeCitationId);
    if (!node || node.x === undefined || node.y === undefined || node.z === undefined) return;

    // Fly camera slightly back and above the target node
    cameraControlsRef.current.setLookAt(
      node.x + 30, node.y + 20, node.z + 40,
      node.x, node.y, node.z,
      true
    );
  }, [activeCitationId, data.nodes]);

  return (
    <div className={styles.container}>
      {/* 3D WebGL Canvas */}
      <Canvas
        camera={{ position: [0, 0, 150], fov: 60 }}
        gl={{ antialias: true, alpha: true }}
        onPointerMissed={() => setSelectedNode(null)}
      >
        <color attach="background" args={['var(--bg-base)']} />
        
        {/* Environment */}
        <ambientLight intensity={0.2} />
        <directionalLight position={[100, 100, 100]} intensity={1.5} />
        <pointLight position={[-100, -100, -100]} intensity={0.5} />
        <Stars radius={300} depth={50} count={5000} factor={4} saturation={0} fade speed={0.5} />

        {/* Graph rendering */}
        <GraphScene />

        {/* Camera interaction */}
        <CameraControls 
          ref={cameraControlsRef} 
          makeDefault
          minDistance={10}
          maxDistance={500}
          dollySpeed={0.3}
          azimuthRotateSpeed={0.5}
          polarRotateSpeed={0.5}
        />
      </Canvas>

      {/* UI Overlay */}
      {selectedNodeId && <NodeInspector />}

      {/* HUD Overlay */}
      <div className={styles.hud}>
        <p className={styles.hudTitle}>Global Knowledge Graph</p>
        <p className={styles.hudStats}>
          {data.nodes.length > 0 ? (
            `${data.nodes.length} Nodes · ${data.links.length} Edges`
          ) : (
            'No graph data yet. Ingest documents to build the graph.'
          )}
        </p>
      </div>
    </div>
  );
}
