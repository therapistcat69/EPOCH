"use client";

import { Suspense, useRef, useMemo } from "react";
import { Canvas } from "@react-three/fiber";
import { useGLTF, useAnimations } from "@react-three/drei";
import * as THREE from "three";

// ─── Inner GLB model (loaded inside Canvas) ────────────────────────────────
function CharacterModel() {
  const group = useRef<THREE.Group>(null);
  const headRef = useRef<THREE.Object3D | null>(null);
  const eyeLRef = useRef<THREE.Object3D | null>(null);
  const eyeRRef = useRef<THREE.Object3D | null>(null);

  const { scene, animations } = useGLTF("/models/retainai-character.glb");

  // Play animations if present
  useAnimations(animations, group);

  // Configure materials and locate interaction nodes once on load
  useMemo(() => {
    // Find interaction nodes for future cursor tracking (Step 2)
    headRef.current = scene.getObjectByName("Head") || null;
    eyeLRef.current = scene.getObjectByName("Eye_L") || null;
    eyeRRef.current = scene.getObjectByName("Eye_R") || null;

    scene.traverse((child) => {
      if ((child as THREE.Mesh).isMesh) {
        const mesh = child as THREE.Mesh;
        mesh.castShadow = true;
        mesh.receiveShadow = false;

        // Tune materials for rich contrast against dark hero
        if (mesh.material) {
          const mats = Array.isArray(mesh.material)
            ? mesh.material
            : [mesh.material];
          mats.forEach((m) => {
            const mat = m as THREE.MeshStandardMaterial;
            mat.side = THREE.FrontSide;
            if (mat.roughness !== undefined) {
              // Ensure hoodie and skin have rich non-washed out appearance
              mat.envMapIntensity = 0.8;
            }
          });
        }
      }
    });
  }, [scene]);

  return (
    <group
      ref={group}
      // Perfectly framed: chest/waist upward, slight angle toward hero copy on left
      position={[0, -0.15, 0]}
      rotation={[0, -0.1, 0]}
    >
      <primitive object={scene} />
    </group>
  );
}

// ─── Canvas wrapper ─────────────────────────────────────────────────────────
export default function RetainaiCharacter() {
  return (
    <div
      className="w-full h-full relative flex items-center justify-center pointer-events-none"
      style={{ minHeight: "inherit", background: "transparent" }}
    >
      <Canvas
        gl={{
          alpha: true,
          antialias: true,
          preserveDrawingBuffer: false,
          powerPreference: "high-performance",
        }}
        camera={{
          position: [0, 0.2, 3.2],
          fov: 42,
          near: 0.1,
          far: 20,
        }}
        style={{ background: "transparent", width: "100%", height: "100%" }}
        dpr={[1, 1.5]}
      >
        {/* ── Direct Cinematic Studio Lighting (No external CDN dependencies) ── */}
        {/* Base ambient light: keeps black hoodie fabric detailed, not pitch black */}
        <ambientLight intensity={0.9} color="#ffffff" />

        {/* Key light: warm frontal key light for face and microphone */}
        <directionalLight
          position={[-2.2, 3, 3]}
          intensity={1.5}
          color="#fff5ed"
          castShadow={false}
        />

        {/* Hero Red Rim light: highlights character silhouette from back-right */}
        <directionalLight
          position={[3, 1.5, -2]}
          intensity={1.8}
          color="#ff1a1a"
        />

        {/* Soft cool fill light from camera right */}
        <directionalLight
          position={[2.5, 0.8, 2.2]}
          intensity={0.65}
          color="#dbeafe"
        />

        {/* Subtle top spotlight on microphone and hair */}
        <pointLight
          position={[0, 1.8, 1.8]}
          intensity={0.7}
          color="#ffffff"
        />

        {/* ── 3D Model ── */}
        <Suspense fallback={null}>
          <CharacterModel />
        </Suspense>
      </Canvas>
    </div>
  );
}

// Preload the GLB to eliminate waterfall delay
useGLTF.preload("/models/retainai-character.glb");
