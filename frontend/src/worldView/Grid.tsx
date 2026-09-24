import { GridHelper } from "three";

interface GridProps {
  size?: number;
  divisions?: number;
  colorCenterLine?: number;
  colorGrid?: number;
}

export function Grid({
  size = 20,
  divisions = 20,
  colorCenterLine = 0x26364A,
  colorGrid = 0x1A2839,
}: GridProps) {
  const grid = new GridHelper(size, divisions, colorCenterLine, colorGrid);
  grid.position.y = 0;
  return <primitive object={grid} />;
}