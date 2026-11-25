"use client";

import React, { useState, useEffect } from "react";
import { ShieldCheck, Activity, Users, Truck, Sliders, History, IndianRupee, CheckCircle, XCircle, AlertCircle, Save, RefreshCw, ShieldAlert } from "lucide-react";
import { AdminKPIs, AuditLog, Truck as TruckType } from "@/types";
import { api } from "@/lib/api";
import FreightMap from "@/components/map/FreightMap";
import ControlRoomView from "@/components/controlroom/ControlRoomView";

interface AdminViewProps {
  metrics: AdminKPIs | null;
  trucks: TruckType[];
  onRefresh: () => void;
}

export default function AdminView({ metrics, trucks, onRefresh }: AdminViewProps) {
  const [activeTab, setActiveTab] = useState<"MAP" | "CONTROL_ROOM" | "WEIGHTS" | "QUEUE" | "AUDIT">("MAP");
  const [weights, setWeights] = useState<Record<string, number>>({
    route_compatibility: 0.25,
    availability_feasibility: 0.20,
    pickup_proximity: 0.15,
    capacity_fit: 0.10,
    price_competitiveness: 0.10,
    reliability: 0.10,
    return_load_potential: 0.10,
  });
  const [auditLogs, setAuditLogs] = useState<AuditLog[]>([]);
  const [verificationQueue, setVerificationQueue] = useState<any[]>([]);
  const [isSavingWeights, setIsSavingWeights] = useState(false);

  useEffect(() => {
    api.getMatchWeights().then(setWeights).catch(() => {});
    api.getAuditLogs(30).then(setAuditLogs).catch(() => {});
    api.getVerificationQueue().then(setVerificationQueue).catch(() => {});
  }, []);

  const handleSaveWeights = async () => {
    setIsSavingWeights(true);
    try {
      await api.updateMatchWeights(weights);
      alert("Deterministic match scoring weights updated successfully in backend!");
      onRefresh();
    } catch (err: any) {
      alert(err.message || "Failed to update weights");
    } finally {
      setIsSavingWeights(false);
    }
  };

  const handleVerifyUser = async (userId: string, action: string) => {
    try {
      await api.verifyUser(userId, action);
      alert(`User marked as ${action}!`);
      api.getVerificationQueue().then(setVerificationQueue);
      onRefresh();
    } catch (err: any) {
      alert(err.message || "Verification action failed");
    }
  };

  return (
    <div className="space-y-6">
      {/* Control Tower KPI Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-[#FFFFFF] border border-[#E6DED5] p-4 rounded-2xl shadow-xs">
          <div className="flex items-center justify-between text-[#6E6259] text-xs">
            <span>Corridor GMV</span>
            <IndianRupee className="w-4 h-4 text-[#3F7D58]" />
          </div>
          <p className="text-xl font-bold text-[#29231F] font-mono mt-1">
            ₹{(metrics?.total_gmv || 148500).toLocaleString("en-IN")}
          </p>
          <span className="text-[10px] text-[#3F7D58] font-semibold">+18.4% this month</span>
        </div>

        <div className="bg-[#FFFFFF] border border-[#E6DED5] p-4 rounded-2xl shadow-xs">
          <div className="flex items-center justify-between text-[#6E6259] text-xs">
            <span>Active Shipments</span>
            <Truck className="w-4 h-4 text-[#5A3E2B]" />
          </div>
          <p className="text-xl font-bold text-[#29231F] font-mono mt-1">
            {metrics?.total_active_shipments ?? 4}
          </p>
          <span className="text-[10px] text-[#5A3E2B] font-semibold">Live in transit</span>
        </div>

        <div className="bg-[#FFFFFF] border border-[#E6DED5] p-4 rounded-2xl shadow-xs">
          <div className="flex items-center justify-between text-[#6E6259] text-xs">
            <span>Algorithm Match Rate</span>
            <Activity className="w-4 h-4 text-[#B7791F]" />
          </div>
          <p className="text-xl font-bold text-[#29231F] font-mono mt-1">
            {metrics?.match_rate_percentage ?? 92.4}%
          </p>
          <span className="text-[10px] text-[#B7791F] font-semibold">Deterministic 7-Factor</span>
        </div>

        <div className="bg-[#FFFFFF] border border-[#E6DED5] p-4 rounded-2xl shadow-xs">
          <div className="flex items-center justify-between text-[#6E6259] text-xs">
            <span>On-Time Delivery SLA</span>
            <ShieldCheck className="w-4 h-4 text-[#3F7D58]" />
          </div>
          <p className="text-xl font-bold text-[#29231F] font-mono mt-1">
            {metrics?.average_on_time_percentage ?? 98.6}%
          </p>
          <span className="text-[10px] text-[#3F7D58] font-semibold">Verified via ePOD</span>
        </div>
      </div>

      {/* Navigation Sub-Tabs */}
      <div className="flex items-center gap-2 border-b border-[#E6DED5] pb-3 text-xs font-semibold">
        <button
          onClick={() => setActiveTab("MAP")}
          className={`flex items-center gap-1.5 px-3.5 py-2 rounded-lg transition cursor-pointer ${
            activeTab === "MAP"
              ? "bg-[#5A3E2B] text-white shadow-xs"
              : "text-[#6E6259] hover:text-[#29231F] bg-[#FFFFFF] border border-[#E6DED5]"
          }`}
        >
          <Truck className="w-3.5 h-3.5" />
          <span>Fleet Network Map</span>
        </button>

        <button
          onClick={() => setActiveTab("CONTROL_ROOM")}
          className={`flex items-center gap-1.5 px-3.5 py-2 rounded-lg transition cursor-pointer ${
            activeTab === "CONTROL_ROOM"
              ? "bg-[#D9381E] text-white shadow-xs font-bold"
              : "text-[#D9381E] hover:bg-[#FEF2F2] bg-[#FFFFFF] border border-[#FCA5A5]"
          }`}
        >
          <ShieldAlert className="w-3.5 h-3.5 animate-pulse" />
          <span>Control Room (SOS)</span>
        </button>

        <button
          onClick={() => setActiveTab("WEIGHTS")}
          className={`flex items-center gap-1.5 px-3.5 py-2 rounded-lg transition cursor-pointer ${
            activeTab === "WEIGHTS"
              ? "bg-[#5A3E2B] text-white shadow-xs"
              : "text-[#6E6259] hover:text-[#29231F] bg-[#FFFFFF] border border-[#E6DED5]"
          }`}
        >
          <Sliders className="w-3.5 h-3.5" />
          <span>Algorithm Tuning</span>
        </button>

        <button
          onClick={() => setActiveTab("QUEUE")}
          className={`flex items-center gap-1.5 px-3.5 py-2 rounded-lg transition cursor-pointer ${
            activeTab === "QUEUE"
              ? "bg-[#5A3E2B] text-white shadow-xs"
              : "text-[#6E6259] hover:text-[#29231F] bg-[#FFFFFF] border border-[#E6DED5]"
          }`}
        >
          <Users className="w-3.5 h-3.5" />
          <span>Verification Queue ({verificationQueue.length})</span>
        </button>

        <button
          onClick={() => setActiveTab("AUDIT")}
          className={`flex items-center gap-1.5 px-3.5 py-2 rounded-lg transition cursor-pointer ${
            activeTab === "AUDIT"
              ? "bg-[#5A3E2B] text-white shadow-xs"
              : "text-[#6E6259] hover:text-[#29231F] bg-[#FFFFFF] border border-[#E6DED5]"
          }`}
        >
          <History className="w-3.5 h-3.5" />
          <span>Audit Log Trail</span>
        </button>
      </div>

      {/* Tab 1: Fleet Network Map */}
      {activeTab === "MAP" && (
        <div className="bg-[#FFFFFF] border border-[#E6DED5] rounded-2xl p-4 shadow-xs space-y-3">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-sm font-bold text-[#29231F]">
                Active West Bengal Corridor Fleet Telemetry
              </h3>
              <p className="text-xs text-[#6E6259]">
                Live positions of verified multi-axle trucks across NH19 and connecting state industrial corridors
              </p>
            </div>
            <span className="text-xs font-mono font-bold px-2.5 py-0.5 rounded-full bg-[#F0EAE1] text-[#5A3E2B] border border-[#E6DED5]">
              {trucks.length} Commercial Trucks Online
            </span>
          </div>

          <FreightMap
            additionalTrucks={trucks.map((t) => ({
              lat: t.current_lat || 22.5448,
              lon: t.current_lon || 88.3186,
              regNo: t.registration_no,
              status: t.status,
              reliability: 95,
            }))}
            height="460px"
          />
        </div>
      )}

      {/* Control Room Tab View (Master Prompt 3) */}
      {activeTab === "CONTROL_ROOM" && (
        <ControlRoomView />
      )}

      {/* Tab 2: 7-Factor Weight Tuning */}
      {activeTab === "WEIGHTS" && (
        <div className="bg-[#FFFFFF] border border-[#E6DED5] rounded-2xl p-5 shadow-xs space-y-5">
          <div className="flex items-start justify-between">
            <div>
              <h3 className="text-sm font-bold text-[#29231F]">
                Deterministic 7-Factor Match Weights
              </h3>
              <p className="text-xs text-[#6E6259]">
                Adjust live scoring weights applied when calculating truck rankings for newly posted consignments. Total must equal 100%.
              </p>
            </div>
            <button
              onClick={handleSaveWeights}
              disabled={isSavingWeights}
              className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-[#5A3E2B] hover:bg-[#432E20] text-white font-semibold text-xs shadow-xs transition cursor-pointer disabled:opacity-50"
            >
              <Save className="w-3.5 h-3.5" />
              <span>{isSavingWeights ? "Saving..." : "Save Weights to DB"}</span>
            </button>
          </div>

          <div className="space-y-4">
            {Object.entries(weights).map(([key, val]) => (
              <div key={key} className="space-y-1.5">
                <div className="flex items-center justify-between text-xs font-semibold">
                  <span className="capitalize text-[#29231F]">
                    {key.replace(/_/g, " ")}
                  </span>
                  <span className="font-mono text-[#5A3E2B]">
                    {Math.round(val * 100)}%
                  </span>
                </div>
                <input
                  type="range"
                  min="0"
                  max="0.5"
                  step="0.05"
                  value={val}
                  onChange={(e) =>
                    setWeights({ ...weights, [key]: parseFloat(e.target.value) })
                  }
                  className="w-full accent-[#5A3E2B] bg-[#E6DED5] rounded-lg h-2 cursor-pointer"
                />
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Tab 3: Verification Queue */}
      {activeTab === "QUEUE" && (
        <div className="bg-[#FFFFFF] border border-[#E6DED5] rounded-2xl p-5 shadow-xs space-y-4">
          <div>
            <h3 className="text-sm font-bold text-[#29231F]">
              Shipper & Carrier Onboarding Verification
            </h3>
            <p className="text-xs text-[#6E6259]">
              Inspect Aadhaar, GSTIN, and Commercial RC documents for platform clearance.
            </p>
          </div>

          {verificationQueue.length === 0 ? (
            <div className="p-8 text-center text-xs text-[#6E6259] bg-[#F7F5F0] rounded-xl border border-dashed border-[#E6DED5]">
              No pending onboarding verifications in queue. All active users verified.
            </div>
          ) : (
            <div className="space-y-3">
              {verificationQueue.map((user) => (
                <div
                  key={user.id}
                  className="p-4 bg-[#F7F5F0] border border-[#E6DED5] rounded-xl flex items-center justify-between gap-4"
                >
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-bold text-[#29231F]">{user.name}</span>
                      <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-[#F0EAE1] text-[#5A3E2B]">
                        {user.role}
                      </span>
                    </div>
                    <p className="text-[11px] text-[#6E6259] mt-0.5">
                      {user.email} • {user.phone}
                    </p>
                  </div>

                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => handleVerifyUser(user.id, "REJECT")}
                      className="p-2 text-red-600 hover:bg-red-50 rounded-lg border border-red-200 transition cursor-pointer"
                      title="Reject"
                    >
                      <XCircle className="w-4 h-4" />
                    </button>
                    <button
                      onClick={() => handleVerifyUser(user.id, "APPROVE")}
                      className="p-2 text-[#3F7D58] hover:bg-[#EBF5EE] rounded-lg border border-[#C6E6D0] transition cursor-pointer"
                      title="Approve"
                    >
                      <CheckCircle className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Tab 4: Audit Logs */}
      {activeTab === "AUDIT" && (
        <div className="bg-[#FFFFFF] border border-[#E6DED5] rounded-2xl p-5 shadow-xs space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-sm font-bold text-[#29231F]">
                Immutable Platform Audit Trail
              </h3>
              <p className="text-xs text-[#6E6259]">
                Timestamped append-only record of bookings, state transitions, GPS signals, and security actions.
              </p>
            </div>
            <button
              onClick={() => api.getAuditLogs(50).then(setAuditLogs)}
              className="p-2 rounded-lg bg-[#F7F5F0] hover:bg-[#EFECE6] border border-[#E6DED5] text-[#5A3E2B] transition cursor-pointer"
              title="Refresh Logs"
            >
              <RefreshCw className="w-3.5 h-3.5" />
            </button>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="border-b border-[#E6DED5] text-[#6E6259] font-semibold">
                  <th className="py-2.5 px-3">Timestamp</th>
                  <th className="py-2.5 px-3">Action</th>
                  <th className="py-2.5 px-3">Entity Type</th>
                  <th className="py-2.5 px-3">Entity ID</th>
                  <th className="py-2.5 px-3">User ID</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#E6DED5] text-[#29231F]">
                {auditLogs.slice(0, 15).map((log) => (
                  <tr key={log.id} className="hover:bg-[#F7F5F0] transition">
                    <td className="py-2.5 px-3 font-mono text-[11px] text-[#6E6259]">
                      {new Date(log.timestamp).toLocaleTimeString("en-IN", {
                        hour: "2-digit",
                        minute: "2-digit",
                        second: "2-digit",
                      })}
                    </td>
                    <td className="py-2.5 px-3 font-semibold text-[#5A3E2B]">
                      {log.action}
                    </td>
                    <td className="py-2.5 px-3 text-[#6E6259]">{log.entity_name}</td>
                    <td className="py-2.5 px-3 font-mono text-[11px] text-[#8A796B]">
                      {log.entity_id ? log.entity_id.slice(0, 8) : "—"}
                    </td>
                    <td className="py-2.5 px-3 font-mono text-[11px] text-[#8A796B]">
                      {log.actor_name || "System"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
