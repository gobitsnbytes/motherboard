"use client";

import { RouteError } from "../../components/RouteError";

export default function OnboardingError(props: { error: Error & { digest?: string }; reset: () => void }) {
  return <RouteError {...props} segment="onboarding" />;
}
