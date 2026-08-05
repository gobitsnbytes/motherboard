"use client";

import React from "react";
import { Skeleton } from "@bnb/ui";

export function OverviewSkeleton() {
  return (
    <div className="space-y-6 animate-pulse">
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="rounded-xl border-2 border-border/50 bg-[#111]/80 p-5 space-y-3">
            <div className="flex justify-between items-center">
              <Skeleton className="h-4 w-24 bg-white/10" />
              <Skeleton className="h-5 w-5 rounded-md bg-white/10" />
            </div>
            <Skeleton className="h-8 w-16 bg-white/20" />
            <Skeleton className="h-3 w-32 bg-white/10" />
          </div>
        ))}
      </div>

      <div className="rounded-xl border-2 border-border/50 bg-[#111]/80 p-6 space-y-3">
        <Skeleton className="h-6 w-48 bg-white/20" />
        <Skeleton className="h-4 w-3/4 bg-white/10" />
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <div className="lg:col-span-2 rounded-xl border-2 border-border/50 bg-[#111]/80 p-6 space-y-4">
          <Skeleton className="h-5 w-36 bg-white/20" />
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="flex justify-between items-center py-2 border-b border-white/5">
              <Skeleton className="h-4 w-48 bg-white/10" />
              <Skeleton className="h-3 w-20 bg-white/10" />
            </div>
          ))}
        </div>
        <div className="rounded-xl border-2 border-border/50 bg-[#111]/80 p-6 space-y-4">
          <Skeleton className="h-5 w-32 bg-white/20" />
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="flex justify-between items-center py-1.5">
              <Skeleton className="h-4 w-24 bg-white/10" />
              <Skeleton className="h-5 w-16 rounded-full bg-white/10" />
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
      <div className="rounded-xl border-2 border-border/50 bg-[#111]/80 p-6 space-y-3">
        <Skeleton className="h-6 w-56 bg-white/20" />
        <Skeleton className="h-4 w-2/3 bg-white/10" />
      </div>
      <div className="grid gap-4 md:grid-cols-3">
        {[1, 2, 3].map((i) => (
          <div key={i} className="rounded-xl border-2 border-border/50 bg-[#111]/80 p-5 space-y-3">
            <Skeleton className="h-5 w-32 bg-white/20" />
            <Skeleton className="h-10 w-full bg-white/10" />
            <Skeleton className="h-3 w-24 bg-white/10" />
          </div>
        ))}
      </div>
      <div className="rounded-xl border-2 border-border/50 bg-[#111]/80 p-6 space-y-4">
        <Skeleton className="h-6 w-40 bg-white/20" />
        {[1, 2, 3, 4, 5].map((i) => (
          <div key={i} className="grid grid-cols-4 gap-4 py-2 border-b border-white/5">
            <Skeleton className="h-4 w-32 bg-white/10" />
            <Skeleton className="h-4 w-24 bg-white/10" />
            <Skeleton className="h-8 w-36 bg-white/10" />
            <Skeleton className="h-8 w-20 bg-white/10" />
          </div>
        ))}
      </div>
    </div>
  );
}

export function ProfileSkeleton() {
  return (
    <div className="space-y-6 animate-pulse">
      <div className="rounded-xl border-2 border-border/50 bg-[#111]/80 p-6 flex flex-col md:flex-row items-center gap-6">
        <Skeleton className="size-20 rounded-full bg-white/20" />
        <div className="space-y-2 flex-1 text-center md:text-left">
          <Skeleton className="h-6 w-48 bg-white/20 mx-auto md:mx-0" />
          <Skeleton className="h-4 w-64 bg-white/10 mx-auto md:mx-0" />
          <Skeleton className="h-5 w-32 bg-white/10 mx-auto md:mx-0 rounded-full" />
        </div>
      </div>
      <div className="grid gap-6 md:grid-cols-2">
        <div className="rounded-xl border-2 border-border/50 bg-[#111]/80 p-6 space-y-4">
          <Skeleton className="h-5 w-40 bg-white/20" />
          <Skeleton className="h-10 w-full bg-white/10" />
          <Skeleton className="h-20 w-full bg-white/10" />
          <Skeleton className="h-10 w-full bg-white/10" />
        </div>
        <div className="rounded-xl border-2 border-border/50 bg-[#111]/80 p-6 space-y-4">
          <Skeleton className="h-5 w-48 bg-white/20" />
          <Skeleton className="h-10 w-full bg-white/10" />
          <Skeleton className="h-10 w-full bg-white/10" />
          <Skeleton className="h-10 w-full bg-white/10" />
        </div>
      </div>
    </div>
  );
}
