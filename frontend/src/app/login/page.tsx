"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Eye, EyeOff } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import FlowingRgbBackground from "@/components/FlowingRgbBackground";
import { friendlyMessage } from "@/lib/api";
import { loginRetainAI } from "@/lib/auth";
import { api } from "@/lib/creator-api";

function LoginInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const queryClient = useQueryClient();

  const urlError = searchParams.get("error");
  const me = useQuery({ queryKey: ["me"], queryFn: api.me });

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
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

    if (!email.trim()) {
      setErrorMsg("Please enter your email address.");
      return;
    }
    if (!password) {
      setErrorMsg("Please enter your password.");
      return;
    }

    try {
      setIsLoading(true);
      await loginRetainAI(email, password);
      await queryClient.invalidateQueries({ queryKey: ["me"] });
      router.replace("/dashboard");
    } catch (err: unknown) {
      setIsLoading(false);
      if (err instanceof Error) {
        setErrorMsg(err.message);
      } else {
        setErrorMsg("Failed to sign in. Please check your credentials.");
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
        <Link href="/" className="auth-brand" id="brand-logo">
          RETAIN<span>AI</span>
        </Link>

        {/* Heading */}
        <h1 className="auth-heading">Welcome back.</h1>
        <p className="auth-subtext">Log in to your RetainAI account.</p>

        {/* Error message */}
        {(errorMsg || urlError) && (
          <p role="alert" className="auth-error" id="login-error-alert">
            {errorMsg || (urlError ? friendlyMessage(urlError) : "")}
          </p>
        )}

        {/* Form */}
        <form onSubmit={handleSubmit} className="auth-form" noValidate>
          <div className="auth-field">
            <label htmlFor="login-email" className="auth-label">
              Email
            </label>
            <input
              id="login-email"
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
            <label htmlFor="login-password" className="auth-label">
              Password
            </label>
            <div className="auth-input-wrapper">
              <input
                id="login-password"
                type={showPassword ? "text" : "password"}
                autoComplete="current-password"
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

          {/* Primary CTA Button */}
          <button
            type="submit"
            disabled={isLoading}
            className="btn-auth-primary"
            id="login-submit-btn"
          >
            <span className="btn-content">
              {isLoading ? "LOGGING IN..." : "LOGIN →"}
            </span>
          </button>
        </form>

        {/* Divider */}
        <div className="auth-divider" />

        {/* Footer */}
        <div className="auth-footer">
          <span>
            New here?{" "}
            <Link href="/signup" id="goto-signup-link">
              Sign up
            </Link>
          </span>
          <Link href="/" className="auth-back-link" id="back-to-home-login-link">
            ← Back to home
          </Link>
        </div>
      </div>
    </main>
  );
}

export default function LoginPage() {
  return (
    <Suspense>
      <LoginInner />
    </Suspense>
  );
}
