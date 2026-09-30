import { useRef } from 'react';
import { useFrame } from '@react-three/fiber';
import { Line } from '@react-three/drei';

interface GraphLinkProps {
  source: any;
  target: any;
  type: string;
}

export function GraphLink({ source, target, type }: GraphLinkProps) {
  const lineRef = useRef<any>(null);

  // Sync line positions with the nodes on every frame
  useFrame(() => {
    if (lineRef.current) {
      // D3 modifies source/target which are objects with x,y,z
      const p1 = [source.x ?? 0, source.y ?? 0, source.z ?? 0];
      const p2 = [target.x ?? 0, target.y ?? 0, target.z ?? 0];
      
      // Updating geometry points dynamically
      lineRef.current.setPoints([p1, p2]);
    }
  });

  // Color mapping based on relationship type
  let color = 'rgba(255, 255, 255, 0.1)';
  if (type === 'HAS_CHUNK') color = 'rgba(0, 240, 255, 0.3)';
  else if (type.includes('SIMILAR')) color = 'rgba(124, 58, 237, 0.3)';

  return (
    <Line
      ref={lineRef}
      points={[[0,0,0], [0,0,0]]} // initial dummy points
      color={color}
      lineWidth={1.5}
      transparent
      depthTest={true}
    />
  );
}
