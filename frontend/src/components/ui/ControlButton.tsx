import React from "react";

interface ControlButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "danger" | "tertiary";
  icon?: React.ReactNode;
  size?: "sm" | "md";
}

export const ControlButton: React.FC<ControlButtonProps> = ({
  variant = "primary",
  icon,
  size = "md",
  children,
  className = "",
  disabled,
  ...props
}) => {
  const base =
    "inline-flex items-center justify-center gap-1.5 font-sans font-medium tracking-wide whitespace-nowrap transition-colors duration-150 focus-visible:outline-2 focus-visible:outline-offset-2 cursor-pointer border select-none";

  const sizes = {
    sm: "h-[30px] px-3 text-[11px] rounded",
    md: "h-[34px] px-4 text-[12px] rounded",
  };

  const variants = {
    primary: disabled
      ? "bg-[#111A28] border-[#26364A] text-[#738397] cursor-not-allowed"
      : "bg-[#155A8A] border-[#1F78B4] text-[#E8EDF3] hover:bg-[#1F78B4] active:bg-[#155A8A]",
    secondary: disabled
      ? "bg-transparent border-[#1B2839] text-[#738397] cursor-not-allowed"
      : "bg-transparent border-[#26364A] text-[#AAB7C5] hover:bg-[#111A28] hover:text-[#E8EDF3] hover:border-[#34475E] active:bg-[#0B111B]",
    danger: disabled
      ? "bg-transparent border-[#1B2839] text-[#738397] cursor-not-allowed"
      : "bg-[#7B1F1F] border-[#D9534F] text-[#E8EDF3] hover:bg-[#D9534F] active:bg-[#7B1F1F]",
    tertiary: disabled
      ? "bg-transparent border-transparent text-[#738397] cursor-not-allowed"
      : "bg-transparent border-transparent text-[#AAB7C5] hover:bg-[#111A28] hover:text-[#E8EDF3] active:bg-[#0B111B]",
  };

  return (
    <button
      className={`${base} ${sizes[size]} ${variants[variant]} ${className}`}
      disabled={disabled}
      {...props}
    >
      {icon && (
        <span className="flex-shrink-0 [&>svg]:w-3.5 [&>svg]:h-3.5" aria-hidden="true">
          {icon}
        </span>
      )}
      {children}
    </button>
  );
};
