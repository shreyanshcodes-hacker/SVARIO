import React from "react";
import { AuthShell } from "@/components/auth/AuthShell";
import { LoginForm } from "@/components/auth/LoginForm";

export default function LoginPage(): React.JSX.Element {
  return (
    <AuthShell
      title="Sign In to Svario"
      subtitle="Access your multi-industry organization workspace."
    >
      <LoginForm />
    </AuthShell>
  );
}
