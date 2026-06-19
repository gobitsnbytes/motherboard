import React from "react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
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
  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle>{title}</CardTitle>
          {icon}
        </div>

        {description && (
          <CardDescription>{description}</CardDescription>
        )}
      </CardHeader>

      <CardContent>
        <p className="text-4xl font-heading font-bold">
          {value}
        </p>
      </CardContent>
    </Card>
  );
}