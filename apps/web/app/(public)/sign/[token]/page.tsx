import React from "react";
import { SigningPortalClient } from "../../../../components/signatures/SigningPortalClient";

interface SigningPageProps {
  params: Promise<{ token: string }>;
}

export default async function PublicSigningPage({ params }: SigningPageProps) {
  const { token } = await params;
  return <SigningPortalClient token={token} />;
}
