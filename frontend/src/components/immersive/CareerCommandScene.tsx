"use client";

import { Float, Stars } from "@react-three/drei";
import { Canvas, useFrame } from "@react-three/fiber";
import { Suspense, useMemo, useRef } from "react";
import * as THREE from "three";

type SceneKind = "hero" | "dashboard" | "jobs" | "agents" | "resume" | "interview" | "ambient";

interface CareerCommandSceneProps {
  kind?: SceneKind;
}

const labels: Record<SceneKind, string[]> = {
  hero: ["Resume", "Jobs", "Agents", "Email", "LinkedIn", "RAG"],
  dashboard: ["ATS", "Matches", "Approvals", "Follow-ups", "Interviews", "Saved"],
  jobs: ["Remote", "Hybrid", "Onsite", "Google", "Greenhouse", "Lever"],
  agents: ["Search", "Resume", "Email", "Follow", "LinkedIn", "Memory"],
  resume: ["ATS", "Keywords", "Bullets", "Preview", "Cover", "Export"],
  interview: ["STAR", "Practice", "Voice", "Score", "Role", "Company"],
  ambient: ["Apply", "Tailor", "Track", "Follow", "Prepare", "Grow"],
};

function OrbitingNodes({ kind = "ambient" }: CareerCommandSceneProps) {
  const group = useRef<THREE.Group>(null);
  const nodeLabels = labels[kind];
  const color = kind === "jobs" ? "#38bdf8" : kind === "interview" ? "#a78bfa" : "#8b5cf6";
  const points = useMemo(
    () =>
      nodeLabels.map((label, index) => {
        const angle = (index / nodeLabels.length) * Math.PI * 2;
        const radius = kind === "hero" ? 3.3 : 2.7;
        return {
          label,
          x: Math.cos(angle) * radius,
          y: Math.sin(index * 1.7) * 0.45,
          z: Math.sin(angle) * radius,
        };
      }),
    [kind, nodeLabels],
  );

  useFrame((state) => {
    if (!group.current) return;
    group.current.rotation.y = state.clock.elapsedTime * 0.08;
    group.current.rotation.x = Math.sin(state.clock.elapsedTime * 0.18) * 0.05;
  });

  return (
    <group ref={group}>
      <mesh>
        <icosahedronGeometry args={[0.64, 2]} />
        <meshStandardMaterial color={color} roughness={0.22} metalness={0.35} emissive={color} emissiveIntensity={0.28} />
      </mesh>
      {points.map((point, index) => (
        <Float key={point.label} speed={1.1 + index * 0.08} rotationIntensity={0.2} floatIntensity={0.7}>
          <group position={[point.x, point.y, point.z]}>
            <mesh>
              <sphereGeometry args={[0.13 + (index % 2) * 0.035, 24, 24]} />
              <meshStandardMaterial color={index % 3 === 0 ? "#22d3ee" : color} emissive={index % 3 === 0 ? "#22d3ee" : color} emissiveIntensity={0.5} roughness={0.28} />
            </mesh>
          </group>
        </Float>
      ))}
      {points.map((point, index) => (
        <line key={`line-${point.label}`}>
          <bufferGeometry>
            <bufferAttribute
              attach="attributes-position"
              args={[new Float32Array([0, 0, 0, point.x, point.y, point.z]), 3]}
            />
          </bufferGeometry>
          <lineBasicMaterial color={index % 2 === 0 ? "#22d3ee" : "#a78bfa"} transparent opacity={0.24} />
        </line>
      ))}
      <mesh rotation={[Math.PI / 2, 0, 0]}>
        <torusGeometry args={[2.75, 0.008, 16, 180]} />
        <meshBasicMaterial color="#7c3aed" transparent opacity={0.35} />
      </mesh>
      <mesh rotation={[Math.PI / 2.45, 0.2, 0.4]}>
        <torusGeometry args={[3.25, 0.006, 16, 180]} />
        <meshBasicMaterial color="#22d3ee" transparent opacity={0.22} />
      </mesh>
    </group>
  );
}

export function CareerCommandScene({ kind = "ambient" }: CareerCommandSceneProps) {
  return (
    <Canvas
      camera={{ position: [0, 1.1, 7.2], fov: 46 }}
      dpr={[1, 1.5]}
      gl={{ antialias: true, alpha: true }}
      className="h-full w-full"
    >
      <ambientLight intensity={0.75} />
      <pointLight position={[4, 4, 4]} intensity={16} color="#8b5cf6" />
      <pointLight position={[-4, -1, 2]} intensity={9} color="#22d3ee" />
      <Suspense fallback={null}>
        <Stars radius={42} depth={24} count={900} factor={2.4} saturation={0.4} fade speed={0.35} />
        <OrbitingNodes kind={kind} />
      </Suspense>
    </Canvas>
  );
}
