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
    <Card className="border-2 border-border shadow-shadow bg-[#111] text-foreground">
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="font-heading font-bold text-xs uppercase tracking-wider text-muted-foreground">
            {title}
          </CardTitle>
          {icon && <div className="text-[#FC920D]">{icon}</div>}
        </div>

        {description && (
          <CardDescription className="text-[11px] text-muted-foreground mt-0.5">
            {description}
          </CardDescription>
        )}
      </CardHeader>

      <CardContent>
        {isLoading ? (
          <Skeleton className="h-9 w-20" />
        ) : (
          <p className="text-3xl font-heading font-black text-white">
            {value}
          </p>
        )}
      </CardContent>
    </Card>
  );
}