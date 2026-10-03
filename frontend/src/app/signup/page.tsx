"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Eye, EyeOff } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import FlowingRgbBackground from "@/components/FlowingRgbBackground";
import { friendlyMessage } from "@/lib/api";
import { signupRetainAI } from "@/lib/auth";
import { api } from "@/lib/creator-api";

function SignupInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const queryClient = useQueryClient();

  const urlError = searchParams.get("error");
  const me = useQuery({ queryKey: ["me"], queryFn: api.me });

  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    if (me.data?.authenticated) {
      router.replace("/dashboard");
    }
  }, [me.data, router]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg(null);

    if (!name.trim()) {
      setErrorMsg("Please enter your name.");
      return;
    }
    if (!email.trim()) {
      setErrorMsg("Please enter your email address.");
      return;
    }
    if (!password) {
      setErrorMsg("Please create a password.");
      return;
    }
    if (password.length < 6) {
      setErrorMsg("Password must be at least 6 characters.");
      return;
    }
    if (password !== confirmPassword) {
      setErrorMsg("Passwords do not match.");
      return;
    }

    try {
      setIsLoading(true);
      await signupRetainAI(name, email, password, confirmPassword);
      await queryClient.invalidateQueries({ queryKey: ["me"] });
      router.replace("/dashboard");
    } catch (err: unknown) {
      setIsLoading(false);
      if (err instanceof Error) {
        setErrorMsg(err.message);
      } else {
        setErrorMsg("Failed to create account. Please try again.");
      }
    }
  };

  return (
    <main className="auth-page">
      {/* Cinematic Flowing RGB Background */}
      <FlowingRgbBackground />

      {/* Dark Glass Auth Card */}
      <div className="auth-card">
        {/* Brand */}
        <Link href="/" className="auth-brand" id="brand-logo-signup">
          RETAIN<span>AI</span>
        </Link>

        {/* Heading */}
        <h1 className="auth-heading">Create your account.</h1>
        <p className="auth-subtext">Create your RetainAI account to get started.</p>

        {/* Error message */}
        {(errorMsg || urlError) && (
          <p role="alert" className="auth-error" id="signup-error-alert">
            {errorMsg || (urlError ? friendlyMessage(urlError) : "")}
          </p>
        )}

        {/* Form */}
        <form onSubmit={handleSubmit} className="auth-form" noValidate>
          <div className="auth-field">
            <label htmlFor="signup-name" className="auth-label">
              Name
            </label>
            <input
              id="signup-name"
              type="text"
              autoComplete="name"
              placeholder="Your name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              disabled={isLoading}
              className="auth-input"
              required
            />
          </div>

          <div className="auth-field">
            <label htmlFor="signup-email" className="auth-label">
              Email
            </label>
            <input
              id="signup-email"
              type="email"
              autoComplete="email"
              placeholder="Email address"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              disabled={isLoading}
              className="auth-input"
              required
            />
          </div>

          <div className="auth-field">
            <label htmlFor="signup-password" className="auth-label">
              Password
            </label>
            <div className="auth-input-wrapper">
              <input
                id="signup-password"
                type={showPassword ? "text" : "password"}
                autoComplete="new-password"
                placeholder="Password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                disabled={isLoading}
                className="auth-input auth-input-password"
                required
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="auth-password-toggle"
                aria-label={showPassword ? "Hide password" : "Show password"}
                tabIndex={-1}
              >
                {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
          </div>

          <div className="auth-field">
            <label htmlFor="signup-confirm-password" className="auth-label">
              Confirm Password
            </label>
            <div className="auth-input-wrapper">
              <input
                id="signup-confirm-password"
                type={showConfirmPassword ? "text" : "password"}
                autoComplete="new-password"
                placeholder="Confirm password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                disabled={isLoading}
                className="auth-input auth-input-password"
                required
              />
              <button
                type="button"
                onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                className="auth-password-toggle"
                aria-label={showConfirmPassword ? "Hide confirm password" : "Show confirm password"}
                tabIndex={-1}
              >
                {showConfirmPassword ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
          </div>

          {/* Primary CTA Button */}
          <button
            type="submit"
            disabled={isLoading}
            className="btn-auth-primary"
            id="signup-submit-btn"
          >
            <span className="btn-content">
              {isLoading ? "CREATING ACCOUNT..." : "CREATE ACCOUNT →"}
            </span>
          </button>
        </form>

        {/* Divider */}
        <div className="auth-divider" />

        {/* Footer */}
        <div className="auth-footer">
          <span>
            Already have an account?{" "}
            <Link href="/login" id="goto-login-link">
              Login
            </Link>
          </span>
          <Link href="/" className="auth-back-link" id="back-to-home-signup-link">
            ← Back to home
          </Link>
        </div>
      </div>
    </main>
  );
}

export default function SignupPage() {
  return (
    <Suspense>
      <SignupInner />
    </Suspense>
  );
}
