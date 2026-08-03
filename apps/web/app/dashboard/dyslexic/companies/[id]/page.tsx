import React from "react";
import CompanyDetailContent from "components/dyslexic/CompanyDetailContent";

export const metadata = {
  title: "Company — Dyslexic",
};

export default async function DyslexicCompanyPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <CompanyDetailContent companyId={id} />;
}
