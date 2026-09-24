import { useMemo } from "react";
import {
  Group,
  SphereGeometry,
  MeshStandardMaterial,
  Mesh,
  RingGeometry,
  Color,
  BufferGeometry,
  BufferAttribute,
  LineBasicMaterial,
  Line,
} from "three";
import { WORLD_VIEW_COLORS, WORLD_VIEW_CONSTANTS } from "./worldViewTypes";

interface TargetObjectProps {
  position: [number, number, number];
  size?: number;
  showTrail?: boolean;
  trailPoints?: [number, number, number][];
}

export function TargetObject({
  position,
  size = 0.25,
  showTrail = false,
  trailPoints = [],
}: TargetObjectProps) {
  const targetGroup = useMemo(() => {
    const group = new Group();

    // Main beacon sphere
    const sphereGeometry = new SphereGeometry(size, 16, 16);
    const sphereMaterial = new MeshStandardMaterial({
      color: WORLD_VIEW_COLORS.target,
      emissive: new Color(WORLD_VIEW_COLORS.target).multiplyScalar(0.3),
      metalness: 0.1,
      roughness: 0.9,
    });
    const sphere = new Mesh(sphereGeometry, sphereMaterial);
    group.add(sphere);

    // Ring indicator around target
    const ringGeometry = new RingGeometry(size * 1.3, size * 1.5, 32);
    const ringMaterial = new MeshStandardMaterial({
      color: WORLD_VIEW_COLORS.target,
      transparent: true,
      opacity: 0.3,
      side: 2,
    });
    const ring = new Mesh(ringGeometry, ringMaterial);
    ring.rotation.x = -Math.PI / 2;
    ring.position.y = -0.01;
    group.add(ring);

    return group;
  }, [size]);

  const trail = useMemo(() => {
    if (!showTrail || trailPoints.length < 2) return null;

    const positions = new Float32Array(trailPoints.length * 3);
    trailPoints.forEach((p, i) => {
      positions[i * 3] = p[0];
      positions[i * 3 + 1] = p[1];
      positions[i * 3 + 2] = p[2];
    });

    const geometry = new BufferGeometry();
    geometry.setAttribute("position", new BufferAttribute(positions, 3));

    const material = new LineBasicMaterial({
      color: WORLD_VIEW_COLORS.trajectory,
      transparent: true,
      opacity: 0.4,
    });

    return new Line(geometry, material);
  }, [showTrail, trailPoints]);

  return (
    <group position={position}>
      <primitive object={targetGroup} />
      {trail && <primitive object={trail} />}
    </group>
  );
}