import React from "react";
import { AuthShell } from "@/components/auth/AuthShell";
import { SignupForm } from "@/components/auth/SignupForm";

export default function SignupPage(): React.JSX.Element {
  return (
    <AuthShell
      title="Create Your Svario Account"
      subtitle="Set up your operator identity for Salons, Clinics, or Hospitals."
    >
      <SignupForm />
    </AuthShell>
  );
}
