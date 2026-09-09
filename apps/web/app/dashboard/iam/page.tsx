
import IAMRoleMappings from "../../../components/dashboard/IAMRoleMappings";
import { IAMContent } from "../../../components/dashboard/IAMContent";

export const metadata = {
  title: "IAM — bits&bytes Motherboard",
};
 
export default function IAMPage() {
  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-heading font-bold text-foreground">
          Identity & Access Management
        </h1>

        <p className="text-sm text-muted-foreground font-base mt-1">
          Review effective access, city scope, groups, and Discord provisioning inputs.
        </p>
       </div> 
      
      <IAMContent />

      <div className="border-t-2 border-border pt-8">
        <IAMRoleMappings />
      </div>
    </div>
  );
}
