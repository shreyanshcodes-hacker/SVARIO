import React from "react";
import { AuthShell } from "@/components/auth/AuthShell";
import { ResetPasswordForm } from "@/components/auth/ResetPasswordForm";

export default function ResetPasswordPage(): React.JSX.Element {
  return (
    <AuthShell
      title="Choose a New Password"
      subtitle="Complete your password reset to restore access to Svario."
    >
      <ResetPasswordForm />
    </AuthShell>
  );
}
