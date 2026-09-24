"use client";

import { RouteError } from "../../components/RouteError";

export default function FinanceError(props: { error: Error & { digest?: string }; reset: () => void }) {
  return <RouteError {...props} segment="finance" />;
}
