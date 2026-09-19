"use client";

import { useParams } from "next/navigation";
import OnboardingReviewWorkspace from "../../../../../components/onboarding/OnboardingReviewWorkspace";

export default function OnboardingDocumentReviewPage() {
  const params = useParams<{ caseId: string; documentId: string }>();
  return <OnboardingReviewWorkspace caseId={params.caseId} documentId={params.documentId} />;
}
