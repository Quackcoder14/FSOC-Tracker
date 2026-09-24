import { useMemo } from "react";
import {
  BufferGeometry,
  BufferAttribute,
  LineBasicMaterial,
  LineSegments,
} from "three";
import { WORLD_VIEW_COLORS, WORLD_VIEW_CONSTANTS } from "./worldViewTypes";

interface FOVFrustumProps {
  hfovDeg: number;
  vfovDeg: number;
  length?: number;
  near?: number;
}

export function FOVFrustum({
  hfovDeg,
  vfovDeg,
  length = 10,
  near = 0.1,
}: FOVFrustumProps) {
  const frustum = useMemo(() => {
    const halfHFOV = Math.tan((hfovDeg * Math.PI) / 360);
    const halfVFOV = Math.tan((vfovDeg * Math.PI) / 360);

    const nearWidth = 2 * near * halfHFOV;
    const nearHeight = 2 * near * halfVFOV;
    const farWidth = 2 * length * halfHFOV;
    const farHeight = 2 * length * halfVFOV;

    const positions = new Float32Array([
      // Near plane
      -nearWidth / 2, -nearHeight / 2, -near,
      nearWidth / 2, -nearHeight / 2, -near,
      nearWidth / 2, nearHeight / 2, -near,
      -nearWidth / 2, nearHeight / 2, -near,
      // Far plane
      -farWidth / 2, -farHeight / 2, -length,
      farWidth / 2, -farHeight / 2, -length,
      farWidth / 2, farHeight / 2, -length,
      -farWidth / 2, farHeight / 2, -length,
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
      opacity: 0.25,
    });

    return new LineSegments(geometry, material);
  }, [hfovDeg, vfovDeg, length, near]);

  return <primitive object={frustum} />;
}