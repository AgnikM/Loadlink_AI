"use client";

import React, { useState, useEffect } from "react";
import { AlertTriangle, PhoneCall, ShieldAlert, CheckCircle2, Clock, MapPin, Radio, WifiOff, X, MessageSquare } from "lucide-react";
import { api } from "@/lib/api";
import { OfflineStorageManager, OfflineQueueItem } from "@/lib/offlineStorage";
import { SOSCategory, SOSEvent } from "@/types";

interface DriverSOSModalProps {
  isOpen: boolean;
  onClose: () => void;
  truckId: string;
  shipmentId?: string;
  bookingId?: string;
  driverPhone?: string;
  currentLat?: number;
  currentLon?: number;
}

export default function DriverSOSModal({
  isOpen,
  onClose,
  truckId,
  shipmentId,
  bookingId,
  driverPhone,
  currentLat = 22.5448,
  currentLon = 88.3186,
}: DriverSOSModalProps) {
  const [category, setCategory] = useState<SOSCategory>("ACCIDENT");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [activeSOS, setActiveSOS] = useState<SOSEvent | null>(null);
  const [offlineItem, setOfflineItem] = useState<OfflineQueueItem | null>(null);
  const [isOfflineMode, setIsOfflineMode] = useState(false);

  useEffect(() => {
    if (typeof window !== "undefined") {
      setIsOfflineMode(!navigator.onLine);
      const handleOnline = () => setIsOfflineMode(false);
      const handleOffline = () => setIsOfflineMode(true);
      window.addEventListener("online", handleOnline);
      window.addEventListener("offline", handleOffline);
      return () => {
        window.removeEventListener("online", handleOnline);
        window.removeEventListener("offline", handleOffline);
      };
    }
  }, []);

  if (!isOpen) return null;

  const handleTriggerSOS = async () => {
    setIsSubmitting(true);
    const eventId = "sos_" + crypto.randomUUID();
    const timestamp = new Date().toISOString();

    const payload = {
      event_id: eventId,
      truck_id: truckId,
      shipment_id: shipmentId,
      booking_id: bookingId,
      latitude: currentLat,
      longitude: currentLon,
      accuracy_meters: 6.5,
      incident_category: category,
      network_status: isOfflineMode ? "OFFLINE_SYNCED" : "ONLINE",
      device_timestamp: timestamp,
      emergency_contact_name: "Paramjeet Yadav (Brother)",
      emergency_contact_phone: "+919830099881",
    };

    if (isOfflineMode) {
      // Offline fallback: persist to local offline queue and prepare SMS payload
      const queued = OfflineStorageManager.enqueueSOS(payload);
      setOfflineItem(queued);
      setIsSubmitting(false);
      return;
    }

    try {
      const res = await api.triggerSOS(payload);
      setActiveSOS(res);
    } catch (err: any) {
      // Network failed during transit: enqueue offline
      const queued = OfflineStorageManager.enqueueSOS(payload);
      setOfflineItem(queued);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4">
      <div className="bg-[#FFFFFF] border-2 border-[#D9381E] rounded-3xl max-w-lg w-full shadow-2xl overflow-hidden animate-in fade-in zoom-in-95 duration-150">
        {/* Header Banner */}
        <div className="bg-[#D9381E] text-white p-5 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-white/20 flex items-center justify-center animate-pulse">
              <ShieldAlert className="w-6 h-6 text-white" />
            </div>
            <div>
              <h2 className="text-base font-black tracking-wide uppercase">
                Emergency SOS Dispatch
              </h2>
              <p className="text-xs text-white/80">
                Direct Control Room & Highway Emergency Alert
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-white/80 hover:text-white p-1 rounded-full cursor-pointer transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-6 space-y-5">
          {/* Active / Triggered State Display */}
          {activeSOS || offlineItem ? (
            <div className="space-y-4">
              <div className="p-4 rounded-2xl bg-[#FEF2F2] border border-[#FCA5A5] space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-[#991B1B] flex items-center gap-1.5">
                    <Radio className="w-4 h-4 animate-ping text-[#DC2626]" />
                    {activeSOS ? `STATUS: ${activeSOS.status}` : "STATUS: OFFLINE QUEUED"}
                  </span>
                  <span className="text-[10px] font-mono text-[#7F1D1D]">
                    ID: {(activeSOS?.event_id || offlineItem?.id || "").slice(0, 16)}
                  </span>
                </div>
                <p className="text-xs text-[#991B1B] font-medium">
                  {activeSOS
                    ? "Control room notified. Responders and highway patrol dispatched to your coordinates."
                    : "No cellular data available. SOS alert safely persisted in device storage. Will auto-sync upon connection."}
                </p>
              </div>

              {/* Offline SMS Fallback Payload Card (Master Prompt 3 Task B) */}
              {offlineItem && offlineItem.sms_fallback_string && (
                <div className="p-3.5 bg-[#FFFBEB] border border-[#FDE68A] rounded-xl space-y-2">
                  <div className="flex items-center gap-2 text-xs font-bold text-[#92400E]">
                    <MessageSquare className="w-4 h-4 text-[#D97706]" />
                    <span>Cellular SMS Emergency Fallback</span>
                  </div>
                  <p className="text-[11px] text-[#78350F]">
                    If internet is absent, send this encrypted fallback code via standard SMS to Control Room (+91 98000 11222):
                  </p>
                  <pre className="p-2 bg-white border border-[#FDE68A] rounded-lg text-[10px] font-mono text-[#92400E] overflow-x-auto select-all">
                    {offlineItem.sms_fallback_string}
                  </pre>
                </div>
              )}

              {/* Notification Delivery Tracker */}
              <div className="space-y-2 text-xs">
                <div className="flex items-center justify-between p-2.5 bg-[#F7F5F0] rounded-xl border border-[#E6DED5]">
                  <span className="font-semibold text-[#29231F]">1. LoadLink Control Room</span>
                  {activeSOS?.control_room_notified ? (
                    <span className="text-[#3F7D58] font-bold flex items-center gap-1">
                      <CheckCircle2 className="w-3.5 h-3.5" /> Dispatched
                    </span>
                  ) : (
                    <span className="text-[#B7791F] font-bold flex items-center gap-1">
                      <Clock className="w-3.5 h-3.5" /> Pending Confirmation
                    </span>
                  )}
                </div>

                <div className="flex items-center justify-between p-2.5 bg-[#F7F5F0] rounded-xl border border-[#E6DED5]">
                  <span className="font-semibold text-[#29231F]">2. Consignment Dealer / Shipper</span>
                  {activeSOS?.dealer_notified ? (
                    <span className="text-[#3F7D58] font-bold flex items-center gap-1">
                      <CheckCircle2 className="w-3.5 h-3.5" /> Alerted
                    </span>
                  ) : (
                    <span className="text-[#6E6259] font-medium">Policy Gated / Awaiting</span>
                  )}
                </div>

                <div className="flex items-center justify-between p-2.5 bg-[#F7F5F0] rounded-xl border border-[#E6DED5]">
                  <span className="font-semibold text-[#29231F]">3. Emergency Contact (Family)</span>
                  {activeSOS?.emergency_contact_notified ? (
                    <span className="text-[#3F7D58] font-bold flex items-center gap-1">
                      <CheckCircle2 className="w-3.5 h-3.5" /> SMS Sent
                    </span>
                  ) : (
                    <span className="text-[#B7791F] font-bold flex items-center gap-1">
                      <Clock className="w-3.5 h-3.5" /> Queued
                    </span>
                  )}
                </div>
              </div>

              <button
                onClick={onClose}
                className="w-full py-3 rounded-xl bg-[#29231F] text-white text-xs font-bold transition hover:bg-black cursor-pointer"
              >
                Close SOS Status Window
              </button>
            </div>
          ) : (
            <>
              {/* Network Warning if Offline */}
              {isOfflineMode && (
                <div className="p-3 bg-[#FEF6E7] border border-[#FCDCA0] rounded-xl flex items-center gap-2.5 text-xs text-[#B7791F]">
                  <WifiOff className="w-4 h-4 shrink-0" />
                  <span>Device is currently OFFLINE. SOS alert will be queued in local storage and fallback SMS prepared.</span>
                </div>
              )}

              {/* Category Selector */}
              <div>
                <label className="block text-xs font-bold uppercase tracking-wider text-[#29231F] mb-2">
                  Emergency Category
                </label>
                <div className="grid grid-cols-2 gap-2 text-xs">
                  {[
                    { id: "ACCIDENT", label: "Collision / Accident" },
                    { id: "MEDICAL_EMERGENCY", label: "Medical Emergency" },
                    { id: "VEHICLE_FIRE", label: "Vehicle Fire" },
                    { id: "THEFT_OR_HIJACKING", label: "Theft / Hijacking" },
                    { id: "HIGHWAY_HARASSMENT", label: "Highway Harassment" },
                    { id: "MECHANICAL_CRITICAL", label: "Critical Mechanical" },
                  ].map((cat) => (
                    <button
                      key={cat.id}
                      type="button"
                      onClick={() => setCategory(cat.id as SOSCategory)}
                      className={`p-2.5 rounded-xl border text-left font-semibold transition cursor-pointer ${
                        category === cat.id
                          ? "bg-[#FEF2F2] border-[#D9381E] text-[#D9381E] ring-1 ring-[#D9381E]"
                          : "bg-[#F7F5F0] border-[#E6DED5] text-[#29231F] hover:bg-[#EFEAE2]"
                      }`}
                    >
                      {cat.label}
                    </button>
                  ))}
                </div>
              </div>

              {/* Location telemetry display */}
              <div className="p-3 bg-[#F7F5F0] border border-[#E6DED5] rounded-xl flex items-center justify-between text-xs text-[#6E6259]">
                <div className="flex items-center gap-2">
                  <MapPin className="w-4 h-4 text-[#D9381E]" />
                  <span>GPS: {currentLat.toFixed(4)}, {currentLon.toFixed(4)} (±6m)</span>
                </div>
                <span className="font-mono text-[10px]">NH19 Corridor</span>
              </div>

              {/* BIG RED TRIGGER BUTTON */}
              <button
                type="button"
                disabled={isSubmitting}
                onClick={handleTriggerSOS}
                className="w-full py-4 rounded-2xl bg-[#D9381E] hover:bg-[#B91C1C] text-white font-black text-sm tracking-wider uppercase shadow-lg shadow-red-500/20 transition flex items-center justify-center gap-2 cursor-pointer disabled:opacity-50"
              >
                {isSubmitting ? (
                  <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                ) : (
                  <>
                    <AlertTriangle className="w-5 h-5" />
                    <span>CONFIRM & TRIGGER EMERGENCY SOS</span>
                  </>
                )}
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
