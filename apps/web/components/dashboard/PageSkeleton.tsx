import React from "react";

export default function PageSkeleton() {
  return (
    <div className="flex flex-col gap-6 p-6 animate-pulse">
      {/* Header skeleton */}
      <div className="flex items-center justify-between">
        <div className="h-8 w-48 rounded-base bg-secondary-background border-2 border-border" />
        <div className="h-9 w-32 rounded-base bg-secondary-background border-2 border-border" />
      </div>

      {/* Content block skeletons */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {Array.from({ length: 3 }).map((_, i) => (
          <div
            key={i}
            className="h-40 rounded-base bg-secondary-background border-2 border-border"
          />
        ))}
      </div>

      {/* Table/list skeleton */}
      <div className="flex flex-col gap-3">
        {Array.from({ length: 4 }).map((_, i) => (
          <div
            key={i}
            className="h-14 rounded-base bg-secondary-background border-2 border-border"
          />
        ))}
      </div>
    </div>
  );
}
