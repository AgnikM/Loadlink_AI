"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Truck, ShieldCheck, Building2, RefreshCw, Radio, Home } from "lucide-react";
import { UserRole } from "@/types";

interface NavbarProps {
  currentRole?: UserRole;
  onSelectRole?: (role: UserRole) => void;
  currentUser?: any;
  onRefreshData?: () => void;
  isLoading?: boolean;
}

export default function Navbar({
  currentRole,
  onSelectRole,
  currentUser,
  onRefreshData,
  isLoading,
}: NavbarProps) {
  const pathname = usePathname();

  return (
    <header className="sticky top-0 z-50 bg-[#FFFFFF]/95 backdrop-blur-md border-b border-[#E6DED5] px-4 lg:px-8 py-3 transition-colors shadow-xs">
      <div className="max-w-7xl mx-auto flex flex-col md:flex-row items-center justify-between gap-3">
        {/* Brand & Network Indicator */}
        <div className="flex items-center gap-3 w-full md:w-auto justify-between md:justify-start">
          <Link href="/" className="flex items-center gap-2.5 group">
            <div className="w-9 h-9 rounded-lg bg-[#5A3E2B] flex items-center justify-center text-white shadow-xs group-hover:bg-[#432E20] transition">
              <Truck className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-bold tracking-tight text-lg text-[#29231F]">
                  LoadLink<span className="text-[#8A796B]">.ai</span>
                </span>
                <span className="text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 bg-[#F0EAE1] text-[#5A3E2B] border border-[#E6DED5] rounded">
                  Enterprise B2B
                </span>
              </div>
              <p className="text-[11px] text-[#6E6259] font-medium flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-[#3F7D58] inline-block live-pulse" />
                <span>West Bengal Freight Corridor Active</span>
              </p>
            </div>
          </Link>

          {/* Mobile Refresh Button */}
          {onRefreshData && (
            <button
              onClick={onRefreshData}
              title="Refresh Corridor Data"
              disabled={isLoading}
              className="md:hidden p-2 rounded-lg bg-[#F7F5F0] hover:bg-[#EFECE6] border border-[#E6DED5] text-[#29231F] transition"
            >
              <RefreshCw className={`w-4 h-4 ${isLoading ? "animate-spin text-[#5A3E2B]" : ""}`} />
            </button>
          )}
        </div>

        {/* Navigation Tabs (Landing, Dealer, Driver, Admin) */}
        <nav className="flex items-center bg-[#F7F5F0] p-1 rounded-xl border border-[#E6DED5] text-xs font-semibold">
          <Link
            href="/"
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg transition ${
              pathname === "/"
                ? "bg-[#FFFFFF] text-[#29231F] shadow-xs border border-[#E6DED5]"
                : "text-[#6E6259] hover:text-[#29231F]"
            }`}
          >
            <Home className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Overview</span>
          </Link>

          <Link
            href="/dealer"
            onClick={() => onSelectRole?.("DEALER")}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg transition ${
              pathname === "/dealer" || currentRole === "DEALER"
                ? "bg-[#5A3E2B] text-white shadow-xs"
                : "text-[#6E6259] hover:text-[#29231F]"
            }`}
          >
            <Building2 className="w-3.5 h-3.5" />
            <span>Dealer Portal</span>
          </Link>

          <Link
            href="/driver"
            onClick={() => onSelectRole?.("DRIVER")}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg transition ${
              pathname === "/driver" || currentRole === "DRIVER"
                ? "bg-[#8A796B] text-white shadow-xs"
                : "text-[#6E6259] hover:text-[#29231F]"
            }`}
          >
            <Truck className="w-3.5 h-3.5" />
            <span>Driver PWA</span>
          </Link>

          <Link
            href="/admin"
            onClick={() => onSelectRole?.("ADMIN")}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg transition ${
              pathname === "/admin" || currentRole === "ADMIN"
                ? "bg-[#29231F] text-white shadow-xs"
                : "text-[#6E6259] hover:text-[#29231F]"
            }`}
          >
            <ShieldCheck className="w-3.5 h-3.5" />
            <span>Admin Tower</span>
          </Link>
        </nav>

        {/* User Context & Live Action */}
        <div className="hidden md:flex items-center gap-3">
          {onRefreshData && (
            <button
              onClick={onRefreshData}
              title="Refresh Live Data"
              disabled={isLoading}
              className="p-2 rounded-lg bg-[#FFFFFF] hover:bg-[#F7F5F0] border border-[#E6DED5] text-[#5A3E2B] transition cursor-pointer shadow-xs"
            >
              <RefreshCw className={`w-4 h-4 ${isLoading ? "animate-spin text-[#5A3E2B]" : ""}`} />
            </button>
          )}

          {currentUser ? (
            <div className="flex items-center gap-2.5 pl-3 border-l border-[#E6DED5]">
              <div className="w-8 h-8 rounded-full bg-[#5A3E2B] text-white flex items-center justify-center font-bold text-xs shadow-xs">
                {currentUser.name ? currentUser.name.charAt(0) : "U"}
              </div>
              <div className="text-left">
                <p className="text-xs font-semibold text-[#29231F] leading-tight">
                  {currentUser.name || "Authenticated"}
                </p>
                <p className="text-[10px] text-[#6E6259] font-medium">
                  {currentUser.role === "DEALER"
                    ? "Shipper / Dealer"
                    : currentUser.role === "DRIVER"
                    ? "Verified Carrier"
                    : "Operations Admin"}
                </p>
              </div>
            </div>
          ) : (
            <div className="text-xs font-medium text-[#6E6259] pl-2 border-l border-[#E6DED5]">
              Demo Mode Active
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
