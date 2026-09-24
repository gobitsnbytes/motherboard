"use client";

import { RouteError } from "../../components/RouteError";

export default function PublicError(props: { error: Error & { digest?: string }; reset: () => void }) {
  return <RouteError {...props} segment="(public)" />;
}
