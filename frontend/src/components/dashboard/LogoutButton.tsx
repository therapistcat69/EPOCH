"use client";

import { LogOut } from "lucide-react";
import React from "react";

interface LogoutButtonProps {
  onLogout: () => void;
  isLoggingOut?: boolean;
  className?: string;
}

export default function LogoutButton({
  onLogout,
  isLoggingOut = false,
  className = "",
}: LogoutButtonProps) {
  return (
    <button
      type="button"
      onClick={onLogout}
      disabled={isLoggingOut}
      aria-label="Logout"
      title="Logout"
      className={`group relative flex items-center h-[44px] w-[46px] hover:w-[114px] focus-visible:w-[114px] rounded-xl border border-white/10 hover:border-white/[0.18] focus-visible:border-white/[0.22] bg-white/[0.03] hover:bg-white/[0.06] focus-visible:bg-white/[0.06] overflow-hidden transition-[width,background-color,border-color] duration-300 ease-out cursor-pointer select-none outline-none focus-visible:ring-1 focus-visible:ring-white/20 disabled:opacity-50 disabled:cursor-not-allowed ${className}`}
    >
      {/* Centered Fixed-Width Icon Container to prevent horizontal jump */}
      <div className="flex h-full w-[44px] shrink-0 items-center justify-center">
        <LogOut
          className="size-[22px] text-white/70 group-hover:text-white group-focus-visible:text-white transition-colors duration-200"
          strokeWidth={1.75}
        />
      </div>

      {/* Smoothly Revealed Logout Text */}
      <span className="shrink-0 text-xs font-medium tracking-wide text-white/85 opacity-0 -translate-x-1 group-hover:opacity-100 group-hover:translate-x-0 group-focus-visible:opacity-100 group-focus-visible:translate-x-0 transition-all duration-300 ease-out whitespace-nowrap pl-1 pr-3">
        {isLoggingOut ? "Exiting…" : "Logout"}
      </span>
    </button>
  );
}
