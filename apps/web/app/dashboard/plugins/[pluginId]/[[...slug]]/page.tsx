"use client";

import React, { use } from "react";
import dynamic from "next/dynamic";
import { Skeleton } from "@bnb/ui";

type PageProps = {
  params: Promise<{ pluginId: string; slug?: string[] }>;
};

export default function PluginPage({ params }: PageProps) {
  const { pluginId } = use(params);

  // Dynamically import the plugin's frontend entrypoint.
  // ssr: false is supported here since this is now a Client Component.
  const PluginPanel = dynamic(
    () =>
      import(`../../../../../../../plugins/${pluginId}/ui`).catch(
        () => () => (
          <div className="p-6 border-4 border-border bg-bg font-heading font-bold rounded-base shadow-light text-red-500">
            Plugin UI panel not found for plugin ID: {pluginId}
          </div>
        )
      ),
    {
      loading: () => <Skeleton className="h-96 w-full border-4 border-border rounded-base" />,
      ssr: false, // Plugins are rendered purely client-side within the shell
    }
  );

  return (
    <div className="flex flex-col gap-6">
      <PluginPanel />
    </div>
  );
}
