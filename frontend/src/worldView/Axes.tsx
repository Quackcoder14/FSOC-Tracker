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

interface AxesProps {
  size?: number;
}

export function Axes({ size = 5 }: AxesProps) {
  const axesGroup = useMemo(() => {
    const group = new Group();

    // X axis (red) - right
    const xGeometry = new BufferGeometry();
    xGeometry.setAttribute(
      "position",
      new BufferAttribute(new Float32Array([0, 0, 0, size, 0, 0]), 3)
    );
    const xMaterial = new LineBasicMaterial({ color: WORLD_VIEW_COLORS.axes.x });
    group.add(new Line(xGeometry, xMaterial));

    // X axis arrow
    const xArrow = new Mesh(
      new ConeGeometry(0.08, 0.25, 8),
      new MeshStandardMaterial({ color: WORLD_VIEW_COLORS.axes.x })
    );
    xArrow.position.set(size, 0, 0);
    xArrow.rotation.z = -Math.PI / 2;
    group.add(xArrow);

    // Y axis (green) - up
    const yGeometry = new BufferGeometry();
    yGeometry.setAttribute(
      "position",
      new BufferAttribute(new Float32Array([0, 0, 0, 0, size, 0]), 3)
    );
    const yMaterial = new LineBasicMaterial({ color: WORLD_VIEW_COLORS.axes.y });
    group.add(new Line(yGeometry, yMaterial));

    // Y axis arrow
    const yArrow = new Mesh(
      new ConeGeometry(0.08, 0.25, 8),
      new MeshStandardMaterial({ color: WORLD_VIEW_COLORS.axes.y })
    );
    yArrow.position.set(0, size, 0);
    group.add(yArrow);

    // Z axis (blue) - forward
    const zGeometry = new BufferGeometry();
    zGeometry.setAttribute(
      "position",
      new BufferAttribute(new Float32Array([0, 0, 0, 0, 0, size]), 3)
    );
    const zMaterial = new LineBasicMaterial({ color: WORLD_VIEW_COLORS.axes.z });
    group.add(new Line(zGeometry, zMaterial));

    // Z axis arrow
    const zArrow = new Mesh(
      new ConeGeometry(0.08, 0.25, 8),
      new MeshStandardMaterial({ color: WORLD_VIEW_COLORS.axes.z })
    );
    zArrow.position.set(0, 0, size);
    zArrow.rotation.x = Math.PI / 2;
    group.add(zArrow);

    // Labels would be nice but require text rendering - skip for now

    return group;
  }, [size]);

  return <primitive object={axesGroup} />;
}