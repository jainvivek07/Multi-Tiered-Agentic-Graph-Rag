import { useRef } from 'react';
import { useFrame } from '@react-three/fiber';
import { Html } from '@react-three/drei';
import * as THREE from 'three';

interface ChunkNodeProps {
  node: any;
  isHighlighted: boolean;
  isSelected: boolean;
  onClick: (e: any) => void;
}

export function ChunkNode({ node, isHighlighted, isSelected, onClick }: ChunkNodeProps) {
  const meshRef = useRef<THREE.Mesh>(null);
  
  useFrame(() => {
    if (meshRef.current) {
      meshRef.current.position.set(node.x ?? 0, node.y ?? 0, node.z ?? 0);
      // slowly rotate chunks for a floating effect
      meshRef.current.rotation.x += 0.005;
      meshRef.current.rotation.y += 0.005;
    }
  });

  useFrame(({ clock }) => {
    if (isSelected && meshRef.current) {
      const scale = 1 + Math.sin(clock.elapsedTime * 4) * 0.15;
      meshRef.current.scale.setScalar(scale);
    } else if (meshRef.current) {
      meshRef.current.scale.lerp(new THREE.Vector3(1, 1, 1), 0.1);
    }
  });

  const baseColor = '#00F0FF'; // cyan
  const highlightColor = '#00F0FF';
  const color = isHighlighted || isSelected ? highlightColor : baseColor;

  return (
    <mesh 
      ref={meshRef} 
      onClick={onClick}
      onPointerOver={() => { document.body.style.cursor = 'pointer'; }}
      onPointerOut={() => { document.body.style.cursor = 'auto'; }}
    >
      <boxGeometry args={[3, 3, 3]} />
      <meshPhysicalMaterial 
        color={color} 
        emissive={color}
        emissiveIntensity={isSelected || isHighlighted ? 0.8 : 0.2}
        roughness={0.2}
        metalness={0.8}
        clearcoat={1.0}
        transparent
        opacity={isHighlighted || isSelected ? 1 : 0.6}
      />
      
      {/* Label */}
      <Html 
        distanceFactor={100}
        zIndexRange={[100, 0]}
        style={{
          transition: 'all 0.2s',
          opacity: isSelected || isHighlighted ? 1 : 0.4,
          transform: `scale(${isSelected ? 1.2 : 1})`,
        }}
      >
        <div style={{
          background: 'rgba(13, 18, 31, 0.85)',
          backdropFilter: 'blur(4px)',
          border: `1px solid ${color}`,
          color: '#E8EEFF',
          padding: '2px 6px',
          borderRadius: '4px',
          fontSize: '12px',
          fontWeight: 600,
          whiteSpace: 'nowrap',
          pointerEvents: 'none',
          userSelect: 'none',
          transform: 'translate3d(-50%, 15px, 0)'
        }}>
          {node.label || 'Chunk'}
        </div>
      </Html>
    </mesh>
  );
}
