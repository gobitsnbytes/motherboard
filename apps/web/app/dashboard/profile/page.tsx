import React from "react";
import { ProfileContent } from "../../../components/dashboard/ProfileContent";

export const metadata = {
  title: "Profile Setup — bits&bytes Motherboard",
};

export default function ProfilePage() {
  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-heading font-bold text-foreground">
          Team Setup Profile
        </h1>

        <p className="text-sm text-muted-foreground font-base mt-1">
          Keep your Motherboard identity current. Scheduling availability lives in Cal.com.
        </p>
      </div>

      <ProfileContent />
    </div>
  );
}
