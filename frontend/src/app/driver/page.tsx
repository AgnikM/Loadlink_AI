"use client";

import React, { useState, useEffect, useCallback } from "react";
import Navbar from "@/components/layout/Navbar";
import DriverView from "@/components/driver/DriverView";
import { Booking, Shipment, Truck } from "@/types";
import { api, setToken, getToken } from "@/lib/api";

export default function DriverPWAPage() {
  const [currentUser, setCurrentUser] = useState<any>(null);
  const [trucks, setTrucks] = useState<Truck[]>([]);
  const [bookings, setBookings] = useState<Booking[]>([]);
  const [shipments, setShipments] = useState<Shipment[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  const initDriverAuth = useCallback(async () => {
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

      // If no valid session or role is not DRIVER, authenticate as default demo driver
      if (!user || user.role !== "DRIVER") {
        const loginRes = await api.login("driver.rajesh@loadlink.ai", "driver123");
        setToken(loginRes.access_token);
        user = await api.getMe();
      }

      setCurrentUser(user);
      await refreshData();
    } catch (err) {
      console.error("Driver auth initialization error:", err);
    } finally {
      setIsLoading(false);
    }
  }, []);

  const refreshData = async () => {
    setIsLoading(true);
    try {
      const [trucksData, bookingsData, shipmentsData] = await Promise.all([
        api.listTrucks().catch(() => []),
        api.listBookings().catch(() => []),
        api.listShipments().catch(() => []),
      ]);
      setTrucks(trucksData);
      setBookings(bookingsData);
      setShipments(shipmentsData);
    } catch (err) {
      console.error("Driver data refresh error:", err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    initDriverAuth();
  }, [initDriverAuth]);

  const currentTruck = trucks.find(
    (t) => currentUser?.driver_id && t.driver_id === currentUser.driver_id
  ) || trucks[0];

  const activeShipment = shipments.find(
    (s) => s.state !== "COMPLETED" && s.state !== "CANCELLED"
  ) || shipments[0] || null;

  return (
    <div className="min-h-screen bg-[#F7F5F0] text-[#29231F] flex flex-col">
      <Navbar
        currentRole="DRIVER"
        currentUser={currentUser}
        onRefreshData={refreshData}
        isLoading={isLoading}
      />

      <main className="flex-1 max-w-2xl w-full mx-auto p-4 lg:p-6">
        <DriverView
          currentTruck={currentTruck}
          bookings={bookings}
          activeShipment={activeShipment}
          onRefresh={refreshData}
          currentUser={currentUser}
        />
      </main>

      <footer className="border-t border-[#E6DED5] bg-[#FFFFFF] px-6 py-4 text-center text-xs text-[#6E6259]">
        <p>
          LoadLink AI Driver Mobile PWA • Direct Shipper Dispatch & Instant ePOD Settlements
        </p>
      </footer>
    </div>
  );
}
