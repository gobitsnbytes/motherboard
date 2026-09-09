"use client";

import React from "react";
import { Skeleton } from "@bnb/ui";

export function OverviewSkeleton() {
  return (
    <div className="space-y-6 animate-pulse">
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="rounded-base border-2 border-border bg-background p-5 space-y-3 shadow-light">
            <div className="flex justify-between items-center">
              <Skeleton className="h-4 w-24 bg-muted" />
              <Skeleton className="h-5 w-5 rounded-sm bg-muted" />
            </div>
            <Skeleton className="h-8 w-16 bg-muted" />
            <Skeleton className="h-3 w-32 bg-muted" />
          </div>
        ))}
      </div>

      <div className="rounded-base border-2 border-border bg-background p-6 space-y-3 shadow-light">
        <Skeleton className="h-6 w-48 bg-muted" />
        <Skeleton className="h-4 w-3/4 bg-muted" />
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2 rounded-base border-2 border-border bg-background p-6 space-y-4 shadow-light">
          <Skeleton className="h-5 w-36 bg-muted" />
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="flex justify-between items-center py-2 border-b border-border">
              <Skeleton className="h-4 w-48 bg-muted" />
              <Skeleton className="h-3 w-20 bg-muted" />
            </div>
          ))}
        </div>
        <div className="rounded-base border-2 border-border bg-background p-6 space-y-4 shadow-light">
          <Skeleton className="h-5 w-32 bg-muted" />
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="flex justify-between items-center py-2 border-b border-border">
              <Skeleton className="h-4 w-24 bg-muted" />
              <Skeleton className="h-5 w-16 rounded-base bg-muted" />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

export function IAMSkeleton() {
  return (
    <div className="space-y-6 animate-pulse">
      <div className="rounded-base border-2 border-border bg-background p-6 space-y-3 shadow-light">
        <Skeleton className="h-6 w-56 bg-muted" />
        <Skeleton className="h-4 w-2/3 bg-muted" />
      </div>
      <div className="grid gap-4 md:grid-cols-3">
        {[1, 2, 3].map((i) => (
          <div key={i} className="rounded-base border-2 border-border bg-background p-5 space-y-3 shadow-light">
            <Skeleton className="h-5 w-32 bg-muted" />
            <Skeleton className="h-10 w-full bg-muted" />
            <Skeleton className="h-3 w-24 bg-muted" />
          </div>
        ))}
      </div>
      <div className="rounded-base border-2 border-border bg-background p-6 space-y-4 shadow-light">
        <Skeleton className="h-6 w-40 bg-muted" />
        {[1, 2, 3, 4, 5].map((i) => (
          <div key={i} className="grid grid-cols-4 gap-4 py-2 border-b border-border">
            <Skeleton className="h-4 w-32 bg-muted" />
            <Skeleton className="h-4 w-24 bg-muted" />
            <Skeleton className="h-8 w-36 bg-muted" />
            <Skeleton className="h-8 w-20 bg-muted" />
          </div>
        ))}
      </div>
    </div>
  );
}

export function ProfileSkeleton() {
  return (
    <div className="space-y-6 animate-pulse">
      <div className="rounded-base border-2 border-border bg-background p-6 flex flex-col md:flex-row items-center gap-6 shadow-light">
        <Skeleton className="size-16 rounded-base bg-muted" />
        <div className="space-y-2 flex-1 text-center md:text-left">
          <Skeleton className="h-6 w-48 bg-muted mx-auto md:mx-0" />
          <Skeleton className="h-4 w-64 bg-muted mx-auto md:mx-0" />
          <Skeleton className="h-5 w-32 bg-muted mx-auto md:mx-0 rounded-base" />
        </div>
      </div>
      <div className="grid gap-6 md:grid-cols-2">
        <div className="rounded-base border-2 border-border bg-background p-6 space-y-4 shadow-light">
          <Skeleton className="h-5 w-40 bg-muted" />
          <Skeleton className="h-10 w-full bg-muted" />
          <Skeleton className="h-20 w-full bg-muted" />
          <Skeleton className="h-10 w-full bg-muted" />
        </div>
        <div className="rounded-base border-2 border-border bg-background p-6 space-y-4 shadow-light">
          <Skeleton className="h-5 w-48 bg-muted" />
          <Skeleton className="h-10 w-full bg-muted" />
          <Skeleton className="h-10 w-full bg-muted" />
          <Skeleton className="h-10 w-full bg-muted" />
        </div>
      </div>
    </div>
  );
}
