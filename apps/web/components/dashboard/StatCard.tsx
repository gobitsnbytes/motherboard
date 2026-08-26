import React from "react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  Skeleton,
} from "@bnb/ui";

interface StatCardProps {
  title: string;
  value: string | number;
  description?: string;
  icon?: React.ReactNode;
}

export default function StatCard({
  title,
  value,
  description,
  icon,
}: StatCardProps) {
  const isLoading = value === "...";

  return (
    <Card className="border-2 border-border shadow-dark bg-[#141418] text-foreground hover:translate-x-[1px] hover:translate-y-[1px] transition-all">
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="font-mono font-bold text-xs uppercase tracking-wider text-zinc-400">
            {title}
          </CardTitle>
          {icon && <div className="text-orange">{icon}</div>}
        </div>

        {description && (
          <CardDescription className="text-[11px] text-zinc-400 font-mono mt-0.5">
            {description}
          </CardDescription>
        )}
      </CardHeader>

      <CardContent>
        {isLoading ? (
          <Skeleton className="h-9 w-20" />
        ) : (
          <p className="text-3xl font-heading font-black text-white tracking-tight">
            {value}
          </p>
        )}
      </CardContent>
    </Card>
  );
}