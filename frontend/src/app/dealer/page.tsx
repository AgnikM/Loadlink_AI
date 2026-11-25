"use client";

import React, { useState, useEffect, useCallback } from "react";
import Navbar from "@/components/layout/Navbar";
import DealerView from "@/components/dealer/DealerView";
import { Load, Shipment } from "@/types";
import { api, setToken, getToken } from "@/lib/api";

export default function DealerPortalPage() {
  const [currentUser, setCurrentUser] = useState<any>(null);
  const [loads, setLoads] = useState<Load[]>([]);
  const [shipments, setShipments] = useState<Shipment[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  const initDealerAuth = useCallback(async () => {
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

      // If no valid session or role is not DEALER, authenticate as default demo dealer
      if (!user || user.role !== "DEALER") {
        const loginRes = await api.login("dealer.kolkata@bengalsteel.in", "dealer123");
        setToken(loginRes.access_token);
        user = await api.getMe();
      }

      setCurrentUser(user);
      await refreshData();
    } catch (err) {
      console.error("Dealer auth initialization error:", err);
    } finally {
      setIsLoading(false);
    }
  }, []);

  const refreshData = async () => {
    setIsLoading(true);
    try {
      const [loadsData, shipmentsData] = await Promise.all([
        api.listLoads().catch(() => []),
        api.listShipments().catch(() => []),
      ]);
      setLoads(loadsData);
      setShipments(shipmentsData);
    } catch (err) {
      console.error("Dealer data refresh error:", err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    initDealerAuth();
  }, [initDealerAuth]);

  return (
    <div className="min-h-screen bg-[#F7F5F0] text-[#29231F] flex flex-col">
      <Navbar
        currentRole="DEALER"
        currentUser={currentUser}
        onRefreshData={refreshData}
        isLoading={isLoading}
      />

      <main className="flex-1 max-w-7xl w-full mx-auto p-4 lg:p-8">
        <DealerView
          loads={loads}
          shipments={shipments}
          onRefresh={refreshData}
        />
      </main>

      <footer className="border-t border-[#E6DED5] bg-[#FFFFFF] px-6 py-4 text-center text-xs text-[#6E6259]">
        <p>
          LoadLink AI • Enterprise B2B Freight Matching Platform • West Bengal Industrial Corridor Network
        </p>
      </footer>
    </div>
  );
}
