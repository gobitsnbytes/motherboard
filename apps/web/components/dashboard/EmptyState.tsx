import React from "react";

interface EmptyStateProps {
  icon: React.ReactNode;
  title: string;
  description: string;
}

export default function EmptyState({ icon, title, description }: EmptyStateProps) {
  return (
    <div className="mx-auto max-w-md rounded-base border-2 border-border bg-[#111] p-8 shadow-shadow">
      <div className="flex flex-col items-center gap-4 text-center">
        <div className="flex size-14 items-center justify-center rounded-base border-2 border-border bg-secondary-background text-muted-foreground">
          {icon}
        </div>
        <div className="flex flex-col gap-1.5">
          <h3 className="text-lg font-heading font-bold text-foreground">
            {title}
          </h3>
          <p className="text-sm text-muted-foreground font-base leading-relaxed">
            {description}
          </p>
        </div>
      </div>
    </div>
  );
}
