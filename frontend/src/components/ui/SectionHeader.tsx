import React from "react";

interface SectionHeaderProps {
  title: string;
  subtitle?: string;
  className?: string;
  action?: React.ReactNode;
}

export const SectionHeader: React.FC<SectionHeaderProps> = ({
  title,
  subtitle,
  className = "",
  action,
}) => {
  return (
    <div
      className={`flex items-center justify-between pb-2 border-b border-[#26364A] ${className}`}
    >
      <div>
        <h3 className="font-sans font-semibold text-[11px] uppercase tracking-[0.06em] text-[#AAB7C5]">
          {title}
        </h3>
        {subtitle && (
          <p className="font-sans text-[11px] text-[#738397] mt-0.5">{subtitle}</p>
        )}
      </div>
      {action && <div>{action}</div>}
    </div>
  );
};

interface PageHeaderProps {
  title: string;
  subtitle?: string;
  action?: React.ReactNode;
  className?: string;
}

export const PageHeader: React.FC<PageHeaderProps> = ({
  title,
  subtitle,
  action,
  className = "",
}) => {
  return (
    <div className={`flex items-start justify-between ${className}`}>
      <div>
        <h2 className="font-sans font-semibold text-[15px] text-[#E8EDF3] tracking-tight">
          {title}
        </h2>
        {subtitle && (
          <p className="font-sans text-[12px] text-[#738397] mt-1">{subtitle}</p>
        )}
      </div>
      {action && <div className="flex-shrink-0">{action}</div>}
    </div>
  );
};
