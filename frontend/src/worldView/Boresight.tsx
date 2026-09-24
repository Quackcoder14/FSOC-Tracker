import { useMemo } from "react";
import {
  Group,
  BufferGeometry,
  BufferAttribute,
  LineBasicMaterial,
  Line,
  ConeGeometry,
  MeshStandardMaterial,
  Mesh,
  Color,
} from "three";
import { WORLD_VIEW_COLORS, WORLD_VIEW_CONSTANTS } from "./worldViewTypes";

interface BoresightProps {
  direction: [number, number, number];
  length?: number;
  showErrorArc?: boolean;
  targetDirection?: [number, number, number];
}

export function Boresight({
  direction,
  length = 10,
  showErrorArc = false,
  targetDirection,
}: BoresightProps) {
  const boresightLine = useMemo(() => {
    const positions = new Float32Array([
      0, 0, 0,
      direction[0] * length, direction[1] * length, direction[2] * length,
    ]);

    const geometry = new BufferGeometry();
    geometry.setAttribute("position", new BufferAttribute(positions, 3));

    const material = new LineBasicMaterial({
      color: WORLD_VIEW_COLORS.boresight,
      transparent: true,
      opacity: 0.8,
    });

    return new Line(geometry, material);
  }, [direction, length]);

  const arrowHead = useMemo(() => {
    const tipX = direction[0] * length;
    const tipY = direction[1] * length;
    const tipZ = direction[2] * length;

    const arrowGeometry = new ConeGeometry(0.15, 0.4, 8);
    const arrowMaterial = new MeshStandardMaterial({
      color: WORLD_VIEW_COLORS.boresight,
      emissive: new Color(WORLD_VIEW_COLORS.boresight).multiplyScalar(0.2),
    });
    const arrow = new Mesh(arrowGeometry, arrowMaterial);
    arrow.position.set(tipX, tipY, tipZ);

    // Orient arrow to point along boresight
    arrow.lookAt(0, 0, 0);
    arrow.rotateX(Math.PI);

    return arrow;
  }, [direction, length]);

  const errorArc = useMemo(() => {
    if (!showErrorArc || !targetDirection) return null;

    // Calculate angle between boresight and target
    const bx = direction[0];
    const by = direction[1];
    const bz = direction[2];
    const tx = targetDirection[0];
    const ty = targetDirection[1];
    const tz = targetDirection[2];

    const dot = bx * tx + by * ty + bz * tz;
    const angle = Math.acos(Math.max(-1, Math.min(1, dot)));

    if (angle < 0.001) return null;

    // Create arc showing error angle
    const axisX = by * tz - bz * ty;
    const axisY = bz * tx - bx * tz;
    const axisZ = bx * ty - by * tx;
    const axisLen = Math.sqrt(axisX * axisX + axisY * axisY + axisZ * axisZ);

    if (axisLen < 0.001) return null;

    // Normalize axis
    const nax = axisX / axisLen;
    const nay = axisY / axisLen;
    const naz = axisZ / axisLen;

    // Generate arc points
    const arcPoints = 32;
    const positions = new Float32Array((arcPoints + 1) * 3);
    const arcRadius = length * 0.5;

    for (let i = 0; i <= arcPoints; i++) {
      const t = (i / arcPoints) * angle;
      // Rodrigues rotation formula
      const cosT = Math.cos(t);
      const sinT = Math.sin(t);
      const oneMinusCosT = 1 - cosT;

      const rx = bx * cosT + (nax * (nax * bx + nay * by + naz * bz)) * oneMinusCosT + (nay * bz - naz * by) * sinT;
      const ry = by * cosT + (nay * (nax * bx + nay * by + naz * bz)) * oneMinusCosT + (naz * bx - nax * bz) * sinT;
      const rz = bz * cosT + (naz * (nax * bx + nay * by + naz * bz)) * oneMinusCosT + (nax * by - nay * bx) * sinT;

      positions[i * 3] = rx * arcRadius;
      positions[i * 3 + 1] = ry * arcRadius;
      positions[i * 3 + 2] = rz * arcRadius;
    }

    const geometry = new BufferGeometry();
    geometry.setAttribute("position", new BufferAttribute(positions, 3));

    const material = new LineBasicMaterial({
      color: WORLD_VIEW_COLORS.errorArc,
      transparent: true,
      opacity: 0.6,
      linewidth: 2,
    });

    return new Line(geometry, material);
  }, [direction, targetDirection, length, showErrorArc]);

  return (
    <group>
      <primitive object={boresightLine} />
      <primitive object={arrowHead} />
      {errorArc && <primitive object={errorArc} />}
    </group>
  );
}