"use client";

import React, { useState, useEffect } from "react";
import { ShieldAlert, AlertTriangle, Radio, CheckCircle, Clock, MapPin, User, Phone, RefreshCw, Send, CheckCircle2 } from "lucide-react";
import { api } from "@/lib/api";
import { SOSEvent } from "@/types";

export default function ControlRoomView() {
  const [activeAlerts, setActiveAlerts] = useState<SOSEvent[]>([]);
  const [selectedAlert, setSelectedAlert] = useState<SOSEvent | null>(null);
  const [actionNotes, setActionNotes] = useState("");
  const [isProcessing, setIsProcessing] = useState(false);
  const [isLoading, setIsLoading] = useState(true);

  const fetchAlerts = async () => {
    setIsLoading(true);
    try {
      const data = await api.getActiveSOS();
      setActiveAlerts(data);
      if (data.length > 0 && !selectedAlert) {
        setSelectedAlert(data[0]);
      } else if (selectedAlert) {
        const found = data.find((d: SOSEvent) => d.id === selectedAlert.id);
        if (found) setSelectedAlert(found);
      }
    } catch {
      setActiveAlerts([]);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchAlerts();
    const interval = setInterval(fetchAlerts, 10000); // Polling control room every 10s
    return () => clearInterval(interval);
  }, []);

  const handleAction = async (action: "ACKNOWLEDGE" | "RESPOND" | "RESOLVE" | "FALSE_ALARM") => {
    if (!selectedAlert) return;
    setIsProcessing(true);
    try {
      const updated = await api.handleSOSAction(selectedAlert.id, {
        action,
        notes: actionNotes || `Action ${action} executed by Control Room Operator`,
      });
      setSelectedAlert(updated);
      setActionNotes("");
      fetchAlerts();
    } catch (err: any) {
      alert(err.message || "Failed to process SOS action");
    } finally {
      setIsProcessing(false);
    }
  };

  const unacknowledgedCount = activeAlerts.filter(
    (a) => a.status === "TRIGGERED" || a.status === "NOTIFICATION_PENDING"
  ).length;

  return (
    <div className="space-y-6">
      {/* Control Room Live Banner */}
      <div className="bg-[#29231F] text-white p-5 rounded-3xl flex flex-col md:flex-row md:items-center justify-between gap-4 shadow-xs">
        <div className="flex items-center gap-3">
          <div className="w-12 h-12 rounded-2xl bg-[#D9381E] flex items-center justify-center animate-pulse">
            <ShieldAlert className="w-7 h-7 text-white" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-base font-black uppercase tracking-wider">
                LoadLink Central Control Room
              </h2>
              <span className="px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-[#D9381E] text-white">
                LIVE OPERATIONAL TOWER
              </span>
            </div>
            <p className="text-xs text-white/70 mt-0.5">
              Corridor Emergency Dispatch, Highway SOS Response & Incident Escalation
            </p>
          </div>
        </div>

        <div className="flex items-center gap-4">
          <div className="text-right">
            <span className="text-[11px] text-white/60 uppercase">Unacknowledged</span>
            <p className="text-xl font-black font-mono text-[#F87171]">{unacknowledgedCount}</p>
          </div>
          <button
            onClick={fetchAlerts}
            className="p-2.5 rounded-xl bg-white/10 hover:bg-white/20 transition cursor-pointer"
            title="Refresh Alert Stream"
          >
            <RefreshCw className={`w-4 h-4 ${isLoading ? "animate-spin" : ""}`} />
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column: Live Alert Queue */}
        <div className="space-y-3">
          <div className="flex items-center justify-between px-1">
            <h3 className="text-xs font-bold uppercase tracking-wider text-[#29231F]">
              Active Emergencies ({activeAlerts.length})
            </h3>
            <span className="text-[10px] font-mono text-[#6E6259]">Auto-refreshed</span>
          </div>

          {activeAlerts.length === 0 ? (
            <div className="p-8 text-center bg-[#FFFFFF] border border-[#E6DED5] rounded-2xl text-xs text-[#6E6259]">
              <CheckCircle2 className="w-8 h-8 text-[#3F7D58] mx-auto mb-2 opacity-80" />
              <span>No active SOS emergencies on corridor. All fleets operating normally.</span>
            </div>
          ) : (
            <div className="space-y-2.5">
              {activeAlerts.map((alert) => {
                const isSelected = selectedAlert?.id === alert.id;
                const isUnacked = alert.status === "TRIGGERED" || alert.status === "NOTIFICATION_PENDING";

                return (
                  <button
                    key={alert.id}
                    onClick={() => setSelectedAlert(alert)}
                    className={`w-full p-4 rounded-2xl border text-left transition cursor-pointer flex flex-col gap-2 ${
                      isSelected
                        ? "bg-[#FEF2F2] border-[#D9381E] shadow-sm"
                        : "bg-[#FFFFFF] border-[#E6DED5] hover:border-[#D9381E]/50"
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-bold text-[#29231F]">
                        {alert.truck_registration_no || "WB-19-AF-0184"}
                      </span>
                      <span
                        className={`px-2 py-0.5 rounded-full text-[10px] font-bold uppercase ${
                          isUnacked
                            ? "bg-[#DC2626] text-white animate-pulse"
                            : "bg-[#FEF6E7] text-[#B7791F] border border-[#FCDCA0]"
                        }`}
                      >
                        {alert.status}
                      </span>
                    </div>

                    <div className="text-xs text-[#D9381E] font-semibold">
                      {alert.incident_category.replace(/_/g, " ")}
                    </div>

                    <div className="flex items-center justify-between text-[11px] text-[#6E6259]">
                      <span>Driver: {alert.driver_name || "Rajesh Yadav"}</span>
                      <span className="font-mono text-[10px]">
                        {new Date(alert.device_timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                      </span>
                    </div>
                  </button>
                );
              })}
            </div>
          )}
        </div>

        {/* Right 2 Columns: Detailed Incident Command View */}
        <div className="lg:col-span-2">
          {selectedAlert ? (
            <div className="bg-[#FFFFFF] border border-[#E6DED5] rounded-3xl p-6 shadow-xs space-y-6">
              <div className="flex items-start justify-between border-b border-[#E6DED5] pb-4">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-bold text-[#D9381E] uppercase tracking-wider">
                      INCIDENT DOSSIER
                    </span>
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-[#F7F5F0] text-[#6E6259]">
                      #{selectedAlert.event_id}
                    </span>
                  </div>
                  <h3 className="text-lg font-black text-[#29231F] mt-1">
                    {selectedAlert.incident_category.replace(/_/g, " ")} — {selectedAlert.truck_registration_no || "WB-19-AF-0184"}
                  </h3>
                </div>

                <div className="text-right">
                  <span className="text-[10px] text-[#6E6259] uppercase">Current State</span>
                  <p className="text-xs font-bold text-[#D9381E]">{selectedAlert.status}</p>
                </div>
              </div>

              {/* Telemetry & Driver Card */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
                <div className="p-4 bg-[#F7F5F0] border border-[#E6DED5] rounded-2xl space-y-2">
                  <h4 className="font-bold text-[#29231F] uppercase tracking-wider text-[11px]">
                    Vehicle & Location Telemetry
                  </h4>
                  <div className="space-y-1 text-[#6E6259]">
                    <div className="flex items-center gap-1.5">
                      <MapPin className="w-3.5 h-3.5 text-[#D9381E]" />
                      <span>Coordinates: {selectedAlert.latitude.toFixed(4)}, {selectedAlert.longitude.toFixed(4)} (±{selectedAlert.accuracy_meters}m)</span>
                    </div>
                    <div>Corridor: Kolkata ↔ Durgapur NH19</div>
                    <div>Network Ingestion: {selectedAlert.network_status}</div>
                    <div>Device Timestamp: {new Date(selectedAlert.device_timestamp).toLocaleString()}</div>
                  </div>
                </div>

                <div className="p-4 bg-[#F7F5F0] border border-[#E6DED5] rounded-2xl space-y-2">
                  <h4 className="font-bold text-[#29231F] uppercase tracking-wider text-[11px]">
                    Driver & Emergency Contacts
                  </h4>
                  <div className="space-y-1 text-[#6E6259]">
                    <div className="flex items-center gap-1.5">
                      <User className="w-3.5 h-3.5 text-[#5A3E2B]" />
                      <span>{selectedAlert.driver_name || "Rajesh Yadav"} ({selectedAlert.driver_phone || "+919830012345"})</span>
                    </div>
                    <div className="flex items-center gap-1.5">
                      <Phone className="w-3.5 h-3.5 text-[#3F7D58]" />
                      <span>Next of Kin: {selectedAlert.emergency_contact_name || "Paramjeet Yadav"} ({selectedAlert.emergency_contact_phone || "+919830099881"})</span>
                    </div>
                    <div>Emergency Contact Notified: {selectedAlert.emergency_contact_notified ? "✅ Sent" : "⏳ Queued"}</div>
                    <div>Dealer Notified: {selectedAlert.dealer_notified ? "✅ Sent" : "ℹ️ Gated by Policy"}</div>
                  </div>
                </div>
              </div>

              {/* Response Log & Actions */}
              <div className="space-y-3">
                <h4 className="font-bold text-xs uppercase tracking-wider text-[#29231F]">
                  Response Timeline & Notes
                </h4>
                <div className="p-3.5 bg-[#F7F5F0] border border-[#E6DED5] rounded-xl text-xs space-y-1 text-[#6E6259]">
                  <div><span className="font-semibold text-[#29231F]">Assigned Responder:</span> {selectedAlert.assigned_responder_name || "LoadLink Control Room"}</div>
                  {selectedAlert.acknowledged_at && (
                    <div><span className="font-semibold text-[#29231F]">Acknowledged At:</span> {new Date(selectedAlert.acknowledged_at).toLocaleString()}</div>
                  )}
                  {selectedAlert.assigned_responder_notes && (
                    <div><span className="font-semibold text-[#29231F]">Responder Log:</span> {selectedAlert.assigned_responder_notes}</div>
                  )}
                  {selectedAlert.resolution_notes && (
                    <div><span className="font-semibold text-[#29231F]">Resolution:</span> {selectedAlert.resolution_notes}</div>
                  )}
                </div>

                <div className="space-y-2">
                  <textarea
                    rows={2}
                    value={actionNotes}
                    onChange={(e) => setActionNotes(e.target.value)}
                    placeholder="Enter responder log notes (e.g. Highway Patrol Unit 4 dispatched; ambulance en route)..."
                    className="w-full bg-[#F7F5F0] border border-[#E6DED5] rounded-xl p-3 text-xs font-medium text-[#29231F] focus:outline-none focus:border-[#29231F]"
                  />

                  <div className="flex flex-wrap items-center gap-2">
                    <button
                      type="button"
                      disabled={isProcessing}
                      onClick={() => handleAction("ACKNOWLEDGE")}
                      className="px-4 py-2.5 rounded-xl bg-[#5A3E2B] hover:bg-[#463021] text-white text-xs font-bold transition cursor-pointer disabled:opacity-50"
                    >
                      1. Acknowledge Alert
                    </button>

                    <button
                      type="button"
                      disabled={isProcessing}
                      onClick={() => handleAction("RESPOND")}
                      className="px-4 py-2.5 rounded-xl bg-[#B7791F] hover:bg-[#976016] text-white text-xs font-bold transition cursor-pointer disabled:opacity-50"
                    >
                      2. Dispatch Patrol / Responders
                    </button>

                    <button
                      type="button"
                      disabled={isProcessing}
                      onClick={() => handleAction("RESOLVE")}
                      className="px-4 py-2.5 rounded-xl bg-[#3F7D58] hover:bg-[#346648] text-white text-xs font-bold transition cursor-pointer disabled:opacity-50"
                    >
                      3. Mark Resolved
                    </button>

                    <button
                      type="button"
                      disabled={isProcessing}
                      onClick={() => handleAction("FALSE_ALARM")}
                      className="px-4 py-2.5 rounded-xl bg-[#F7F5F0] border border-[#E6DED5] text-[#6E6259] hover:bg-[#EAE4DC] text-xs font-bold transition cursor-pointer disabled:opacity-50 ml-auto"
                    >
                      Mark False Alarm
                    </button>
                  </div>
                </div>
              </div>
            </div>
          ) : (
            <div className="p-12 text-center bg-[#FFFFFF] border border-[#E6DED5] rounded-3xl text-xs text-[#6E6259]">
              Select an active emergency alert from the queue to open the command dossier.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
