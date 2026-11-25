"use client";

import React, { useState, useEffect, useCallback } from "react";
import Navbar from "@/components/layout/Navbar";
import AdminView from "@/components/admin/AdminView";
import { AdminKPIs, Truck } from "@/types";
import { api, setToken, getToken } from "@/lib/api";

export default function AdminControlTowerPage() {
  const [currentUser, setCurrentUser] = useState<any>(null);
  const [metrics, setMetrics] = useState<AdminKPIs | null>(null);
  const [trucks, setTrucks] = useState<Truck[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  const initAdminAuth = useCallback(async () => {
    setIsLoading(true);
    try {
      let user: any = null;
      const token = getToken();
      if (token) {
        try {
          user = await api.getMe();
        } catch {
          setToken(null);
          user = null;
        }
      }

      // If no valid session or role is not ADMIN, authenticate as default operations admin
      if (!user || user.role !== "ADMIN") {
        const loginRes = await api.login("admin@loadlink.ai", "admin123");
        setToken(loginRes.access_token);
        user = await api.getMe();
      }

      setCurrentUser(user);
      await refreshData();
    } catch (err) {
      console.error("Admin auth initialization error:", err);
    } finally {
      setIsLoading(false);
    }
  }, []);

  const refreshData = async () => {
    setIsLoading(true);
    try {
      const [metricsData, trucksData] = await Promise.all([
        api.getAdminMetrics().catch(() => null),
        api.listTrucks().catch(() => []),
      ]);
      setMetrics(metricsData);
      setTrucks(trucksData);
    } catch (err) {
      console.error("Admin data refresh error:", err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    initAdminAuth();
  }, [initAdminAuth]);

  return (
    <div className="min-h-screen bg-[#F7F5F0] text-[#29231F] flex flex-col">
      <Navbar
        currentRole="ADMIN"
        currentUser={currentUser}
        onRefreshData={refreshData}
        isLoading={isLoading}
      />

      <main className="flex-1 max-w-7xl w-full mx-auto p-4 lg:p-8">
        <AdminView
          metrics={metrics}
          trucks={trucks}
          onRefresh={refreshData}
        />
      </main>

      <footer className="border-t border-[#E6DED5] bg-[#FFFFFF] px-6 py-4 text-center text-xs text-[#6E6259]">
        <p>
          LoadLink AI Operations Control Tower • 7-Factor Engine Configuration & Verified Audit Logs
        </p>
      </footer>
    </div>
  );
}
