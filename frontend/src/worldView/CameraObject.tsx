import { useMemo } from "react";
import {
  Group,
  BoxGeometry,
  MeshStandardMaterial,
  Mesh,
  CylinderGeometry,
  BufferGeometry,
  BufferAttribute,
  LineBasicMaterial,
  LineSegments,
} from "three";
import { WORLD_VIEW_COLORS, WORLD_VIEW_CONSTANTS } from "./worldViewTypes";

interface CameraObjectProps {
  position: [number, number, number];
  rotation: [number, number, number]; // [tilt, pan, 0] in radians
  hfovDeg: number;
  vfovDeg: number;
  targetDistance: number;
  showFrustum?: boolean;
}

export function CameraObject({
  position,
  rotation,
  hfovDeg,
  vfovDeg,
  targetDistance,
  showFrustum = true,
}: CameraObjectProps) {
  const cameraGroup = useMemo(() => {
    const group = new Group();

    // Camera body - a simple box representing the terminal
    const bodyGeometry = new BoxGeometry(
      WORLD_VIEW_CONSTANTS.cameraSize * 1.2,
      WORLD_VIEW_CONSTANTS.cameraSize * 0.8,
      WORLD_VIEW_CONSTANTS.cameraSize * 1.5
    );
    const bodyMaterial = new MeshStandardMaterial({
      color: WORLD_VIEW_COLORS.cameraBody,
      metalness: 0.3,
      roughness: 0.7,
    });
    const body = new Mesh(bodyGeometry, bodyMaterial);
    body.position.z = -WORLD_VIEW_CONSTANTS.cameraSize * 0.75;
    group.add(body);

    // Camera lens - cylinder at front
    const lensGeometry = new CylinderGeometry(
      WORLD_VIEW_CONSTANTS.cameraSize * 0.35,
      WORLD_VIEW_CONSTANTS.cameraSize * 0.35,
      0.2,
      16
    );
    const lensMaterial = new MeshStandardMaterial({
      color: 0x1A2839,
      metalness: 0.8,
      roughness: 0.2,
    });
    const lens = new Mesh(lensGeometry, lensMaterial);
    lens.rotation.x = Math.PI / 2;
    lens.position.z = -WORLD_VIEW_CONSTANTS.cameraSize * 1.6;
    group.add(lens);

    // Base platform
    const baseGeometry = new CylinderGeometry(
      WORLD_VIEW_CONSTANTS.cameraSize * 0.6,
      WORLD_VIEW_CONSTANTS.cameraSize * 0.7,
      0.3,
      12
    );
    const baseMaterial = new MeshStandardMaterial({
      color: WORLD_VIEW_COLORS.cameraBody,
      metalness: 0.2,
      roughness: 0.8,
    });
    const base = new Mesh(baseGeometry, baseMaterial);
    base.position.y = -WORLD_VIEW_CONSTANTS.cameraSize * 0.55;
    group.add(base);

    return group;
  }, []);

  const frustum = useMemo(() => {
    if (!showFrustum) return null;

    // Create frustum as a wireframe pyramid
    const halfHFOV = Math.tan((hfovDeg * Math.PI) / 360);
    const halfVFOV = Math.tan((vfovDeg * Math.PI) / 360);

    const near = 0.1;
    const far = targetDistance * 1.2;

    const nearWidth = 2 * near * halfHFOV;
    const nearHeight = 2 * near * halfVFOV;
    const farWidth = 2 * far * halfHFOV;
    const farHeight = 2 * far * halfVFOV;

    const positions = new Float32Array([
      // Near plane
      -nearWidth / 2, -nearHeight / 2, -near,
      nearWidth / 2, -nearHeight / 2, -near,
      nearWidth / 2, nearHeight / 2, -near,
      -nearWidth / 2, nearHeight / 2, -near,
      // Far plane
      -farWidth / 2, -farHeight / 2, -far,
      farWidth / 2, -farHeight / 2, -far,
      farWidth / 2, farHeight / 2, -far,
      -farWidth / 2, farHeight / 2, -far,
    ]);

    const indices = [
      // Near plane edges
      0, 1, 1, 2, 2, 3, 3, 0,
      // Far plane edges
      4, 5, 5, 6, 6, 7, 7, 4,
      // Connecting edges
      0, 4, 1, 5, 2, 6, 3, 7,
    ];

    const geometry = new BufferGeometry();
    geometry.setAttribute("position", new BufferAttribute(positions, 3));
    geometry.setIndex(indices);

    const material = new LineBasicMaterial({
      color: WORLD_VIEW_COLORS.cameraFrustum,
      transparent: true,
      opacity: 0.3,
    });

    return new LineSegments(geometry, material);
  }, [hfovDeg, vfovDeg, targetDistance, showFrustum]);

  return (
    <group position={position} rotation={rotation}>
      <primitive object={cameraGroup} />
      {frustum && <primitive object={frustum} />}
    </group>
  );
}