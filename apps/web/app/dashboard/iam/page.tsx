import IAMRoleMappings from "../../../components/dashboard/IAMRoleMappings";

export const metadata = {
  title: "IAM — bits&bytes Motherboard",
};
 
export default function IAMPage() {
  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-heading font-bold text-foreground">
          Identity &amp; Access Management
        </h1>
        <p className="text-sm text-muted-foreground font-base mt-1">
          Configure Discord role mappings for internal groups and sync provisioning behavior. 
        </p>
      </div>
      <IAMRoleMappings />
    </div>
  );
}
