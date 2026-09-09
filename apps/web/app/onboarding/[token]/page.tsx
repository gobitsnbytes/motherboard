import OnboardingPortalClient from "../../../components/onboarding/OnboardingPortalClient";

export default async function OnboardingPortalPage({ params }: { params: Promise<{ token: string }> }) {
  const { token } = await params;
  return <OnboardingPortalClient token={token} />;
}
