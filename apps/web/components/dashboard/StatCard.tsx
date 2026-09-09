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
    <Card className="min-h-36 border-2 border-border bg-background text-foreground shadow-none">
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm font-semibold text-foreground">
            {title}
          </CardTitle>
          {icon && <div className="text-orange">{icon}</div>}
        </div>

        {description && (
          <CardDescription className="mt-1 text-xs text-muted-foreground">
            {description}
          </CardDescription>
        )}
      </CardHeader>

      <CardContent>
        {isLoading ? (
          <Skeleton className="h-9 w-20" />
        ) : (
          <p className="text-3xl font-heading font-black tracking-tight text-foreground">
            {value}
          </p>
        )}
      </CardContent>
    </Card>
  );
}
