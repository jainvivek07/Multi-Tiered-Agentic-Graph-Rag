import { useRef } from 'react';
import { useFrame } from '@react-three/fiber';
import { Html } from '@react-three/drei';
import * as THREE from 'three';

interface EntityNodeProps {
  node: any;
  isHighlighted: boolean;
  isSelected: boolean;
  onClick: (e: any) => void;
}

export function EntityNode({ node, isHighlighted, isSelected, onClick }: EntityNodeProps) {
  const meshRef = useRef<THREE.Mesh>(null);
  
  // D3 updates `node.x`, `node.y`, `node.z` directly on the object.
  // We sync these to the Three.js mesh in the useFrame loop.
  useFrame(() => {
    if (meshRef.current) {
      meshRef.current.position.set(node.x ?? 0, node.y ?? 0, node.z ?? 0);
    }
  });

  // Scale pulses if selected
  useFrame(({ clock }) => {
    if (isSelected && meshRef.current) {
      const scale = 1 + Math.sin(clock.elapsedTime * 4) * 0.15;
      meshRef.current.scale.setScalar(scale);
    } else if (meshRef.current) {
      // Return to normal
      meshRef.current.scale.lerp(new THREE.Vector3(1, 1, 1), 0.1);
    }
  });

  const baseColor = '#7C3AED'; // violet
  const highlightColor = '#00F0FF'; // cyan (active citation)
  const color = isHighlighted ? highlightColor : baseColor;

  return (
    <mesh 
      ref={meshRef} 
      onClick={onClick}
      onPointerOver={() => { document.body.style.cursor = 'pointer'; }}
      onPointerOut={() => { document.body.style.cursor = 'auto'; }}
    >
      <sphereGeometry args={[2.5, 32, 32]} />
      <meshPhysicalMaterial 
        color={color} 
        emissive={color}
        emissiveIntensity={isSelected || isHighlighted ? 0.8 : 0.2}
        roughness={0.2}
        metalness={0.8}
        clearcoat={1.0}
        transparent
        opacity={isHighlighted || isSelected ? 1 : 0.8}
      />
      
      {/* Label */}
      <Html 
        distanceFactor={100}
        zIndexRange={[100, 0]}
        style={{
          transition: 'all 0.2s',
          opacity: isSelected || isHighlighted ? 1 : 0.7,
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
          {node.label}
        </div>
      </Html>
    </mesh>
  );
}
