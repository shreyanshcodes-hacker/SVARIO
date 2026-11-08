import React from "react";
import { AuthShell } from "@/components/auth/AuthShell";
import { ForgotPasswordForm } from "@/components/auth/ForgotPasswordForm";

export default function ForgotPasswordPage(): React.JSX.Element {
  return (
    <AuthShell
      title="Reset Your Password"
      subtitle="Enter your account email to receive a password recovery link."
    >
      <ForgotPasswordForm />
    </AuthShell>
  );
}
