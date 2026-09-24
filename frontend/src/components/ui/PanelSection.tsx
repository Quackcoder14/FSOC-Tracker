import React from "react";

interface PanelSectionProps {
  children: React.ReactNode;
  className?: string;
  level?: 1 | 2 | 3;
  padding?: "none" | "sm" | "md";
}

export const PanelSection: React.FC<PanelSectionProps> = ({
  children,
  className = "",
  level = 1,
  padding = "md",
}) => {
  const backgrounds = {
    1: "bg-[#111A28] border border-[#26364A]",
    2: "bg-[#162133] border border-[#1B2839]",
    3: "bg-[#1B283B] border border-[#1B2839]",
  };

  const paddings = {
    none: "",
    sm: "p-3",
    md: "p-4",
  };

  return (
    <div
      className={`rounded-md ${backgrounds[level]} ${paddings[padding]} ${className}`}
    >
      {children}
    </div>
  );
};
