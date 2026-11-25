"use client";

import React, { useState, useEffect, useCallback } from "react";
import {
  X,
  Truck,
  UserCheck,
  UserX,
  ShieldAlert,
  Clock,
  History,
  AlertCircle,
  CheckCircle2,
  Phone,
  FileBadge,
} from "lucide-react";
import { Truck as TruckType, VehicleAssignment } from "@/types";
import { api } from "@/lib/api";

interface VehicleAssignmentModalProps {
  isOpen: boolean;
  onClose: () => void;
  truck: any | null;
  currentUser?: any;
  onTruckUpdated?: () => void;
}

export default function VehicleAssignmentModal({
  isOpen,
  onClose,
  truck,
  currentUser,
  onTruckUpdated,
}: VehicleAssignmentModalProps) {
  const [assignments, setAssignments] = useState<VehicleAssignment[]>([]);
  const [drivers, setDrivers] = useState<any[]>([]);
  const [selectedDriverId, setSelectedDriverId] = useState("");
  const [assignmentNotes, setAssignmentNotes] = useState("");
  const [safetyHoldReason, setSafetyHoldReason] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [successMsg, setSuccessMsg] = useState("");
  const [errorMsg, setErrorMsg] = useState("");

  const loadData = useCallback(async () => {
    if (!truck) return;
    setLoading(true);
    setErrorMsg("");
    try {
      const [hist, driverList] = await Promise.all([
        api.getTruckAssignments(truck.id).catch(() => []),
        api.listDrivers().catch(() => []),
      ]);
      setAssignments(hist || []);
      setDrivers(driverList || []);
      if (driverList.length > 0 && !selectedDriverId) {
        setSelectedDriverId(driverList[0].id);
      }
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to load assignment data");
    } finally {
      setLoading(false);
    }
  }, [truck, selectedDriverId]);

  useEffect(() => {
    if (isOpen && truck) {
      loadData();
      setSuccessMsg("");
      setErrorMsg("");
      setAssignmentNotes(`Assigned by ${currentUser?.name || "Fleet Operator"}`);
      setSafetyHoldReason("");
    }
  }, [isOpen, truck, loadData, currentUser]);

  if (!isOpen || !truck) return null;

  const handleAssignDriver = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedDriverId) {
      setErrorMsg("Please select a driver from the fleet roster.");
      return;
    }
    setBusy(true);
    setErrorMsg("");
    try {
      await api.assignTruckDriver(truck.id, selectedDriverId, assignmentNotes);
      setSuccessMsg("Driver assigned successfully. Conflicting active assignments resolved.");
      await loadData();
      onTruckUpdated?.();
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to assign driver");
    } finally {
      setBusy(false);
    }
  };

  const handleUnassignDriver = async () => {
    setBusy(true);
    setErrorMsg("");
    try {
      await api.unassignTruckDriver(truck.id);
      setSuccessMsg("Driver unassigned from vehicle.");
      await loadData();
      onTruckUpdated?.();
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to unassign driver");
    } finally {
      setBusy(false);
    }
  };

  const handleToggleSafetyHold = async (hold: boolean) => {
    setBusy(true);
    setErrorMsg("");
    try {
      await api.setTruckSafetyHold(truck.id, hold, safetyHoldReason || "Safety inspection");
      setSuccessMsg(hold ? "Vehicle placed on SAFETY HOLD (excluded from matching)." : "Vehicle cleared from SAFETY HOLD.");
      onTruckUpdated?.();
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to update safety hold");
    } finally {
      setBusy(false);
    }
  };

  const isSafetyHeld = truck.status === "SAFETY_HOLD";
  const isMaintenance = truck.status === "MAINTENANCE";

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4 overflow-y-auto">
      <div className="bg-white border border-[#E6DED5] rounded-2xl w-full max-w-2xl max-h-[90vh] flex flex-col shadow-2xl overflow-hidden my-auto animate-in fade-in zoom-in-95 duration-150">
        {/* Header */}
        <div className="p-5 border-b border-[#E6DED5] flex items-center justify-between bg-[#FDFCFB]">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-[#5A3E2B] text-white flex items-center justify-center shadow-xs">
              <Truck size={20} />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="font-bold text-base text-[#29231F]">Fleet & Vehicle Assignment</h3>
                <span className="font-mono font-bold text-xs px-2 py-0.5 rounded-full bg-[#F0EAE1] text-[#5A3E2B] border border-[#E6DED5]">
                  {truck.registration_no || truck.id}
                </span>
                <span
                  className={`text-[10px] font-bold px-2 py-0.5 rounded-full border ${
                    isSafetyHeld
                      ? "bg-[#FAEDED] text-[#C53030] border-[#F1C4C4]"
                      : isMaintenance
                      ? "bg-[#FEF3C7] text-[#92400E] border-[#FDE68A]"
                      : "bg-[#EBF7EE] text-[#24613B] border-[#BDE5C8]"
                  }`}
                >
                  {truck.status || "AVAILABLE"}
                </span>
              </div>
              <p className="text-xs text-[#6E6259]">
                Ownership: {truck.ownership_type || "EXTERNAL_TRANSPORTER"} · Driver Conflict Prevention Enforced
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 text-[#6E6259] hover:text-[#29231F] hover:bg-[#F7F5F0] rounded-lg transition cursor-pointer"
          >
            <X size={18} />
          </button>
        </div>

        {/* Body */}
        <div className="p-6 overflow-y-auto space-y-5 text-xs text-[#29231F]">
          {successMsg && (
            <div className="p-3 bg-[#EBF7EE] border border-[#BDE5C8] rounded-xl text-[#24613B] font-medium flex items-center gap-2">
              <CheckCircle2 size={16} />
              <span>{successMsg}</span>
            </div>
          )}
          {errorMsg && (
            <div className="p-3 bg-[#FAEDED] border border-[#F1C4C4] rounded-xl text-[#C53030] font-medium flex items-center gap-2">
              <AlertCircle size={16} />
              <span>{errorMsg}</span>
            </div>
          )}

          {/* Active Assignment Status */}
          <div className="p-4 bg-[#F7F5F0] rounded-xl border border-[#E6DED5] flex items-center justify-between gap-4">
            <div>
              <span className="text-[10px] font-bold uppercase tracking-wider text-[#8A796B]">
                Active Vehicle Assignment
              </span>
              <div className="text-sm font-bold text-[#29231F] mt-0.5">
                {truck.driver_name || "No Driver Currently Assigned"}
              </div>
              {truck.driver_phone && (
                <div className="text-[11px] text-[#6E6259] flex items-center gap-1.5 mt-0.5">
                  <Phone size={12} />
                  <span>{truck.driver_phone}</span>
                </div>
              )}
            </div>

            {truck.driver_id && (
              <button
                type="button"
                onClick={handleUnassignDriver}
                disabled={busy}
                className="px-3 py-1.5 bg-white hover:bg-[#FAEDED] text-[#C53030] border border-[#F1C4C4] rounded-lg font-bold text-xs flex items-center gap-1.5 transition cursor-pointer"
              >
                <UserX size={14} /> Unassign Driver
              </button>
            )}
          </div>

          {/* Assign Driver Form */}
          <form onSubmit={handleAssignDriver} className="p-4 bg-white rounded-xl border border-[#E6DED5] space-y-3">
            <div className="flex items-center gap-2">
              <UserCheck size={16} className="text-[#5A3E2B]" />
              <h4 className="font-bold text-xs text-[#29231F]">Assign Driver to this Truck</h4>
            </div>
            <p className="text-[11px] text-[#6E6259]">
              LoadLink architecture ensures at most 1 active vehicle per driver. Re-assigning a driver will automatically unassign them from any previous vehicle.
            </p>

            <div className="space-y-2">
              <label className="block">
                <span className="text-[10px] font-bold uppercase text-[#6E6259]">Select Driver from Roster</span>
                <select
                  value={selectedDriverId}
                  onChange={(e) => setSelectedDriverId(e.target.value)}
                  className="w-full text-xs p-2.5 bg-[#F7F5F0] border border-[#E6DED5] rounded-lg mt-0.5 font-medium"
                >
                  <option value="">-- Choose a Driver --</option>
                  {drivers.map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.name} ({d.license_number || "Verified"} · {d.is_assigned ? `Active on ${d.active_truck_reg || "truck"}` : "Unassigned"})
                    </option>
                  ))}
                </select>
              </label>

              <label className="block">
                <span className="text-[10px] font-bold uppercase text-[#6E6259]">Assignment Notes / Instructions</span>
                <input
                  type="text"
                  value={assignmentNotes}
                  onChange={(e) => setAssignmentNotes(e.target.value)}
                  placeholder="e.g. Assigned for Kolkata-Durgapur dispatch run"
                  className="w-full text-xs p-2 bg-[#F7F5F0] border border-[#E6DED5] rounded-lg mt-0.5"
                />
              </label>
            </div>

            <button
              type="submit"
              disabled={busy || !selectedDriverId}
              className="w-full py-2.5 bg-[#5A3E2B] text-white font-bold text-xs rounded-lg hover:bg-[#432E20] transition disabled:opacity-50 flex items-center justify-center gap-1.5 shadow-xs cursor-pointer"
            >
              {busy ? "Updating Assignment..." : "Confirm Driver Assignment"}
            </button>
          </form>

          {/* Operational Safety Hold / Compliance Controls */}
          <div className="p-4 bg-[#FDFCFB] rounded-xl border border-[#E6DED5] space-y-3">
            <div className="flex items-center gap-2">
              <ShieldAlert size={16} className={isSafetyHeld ? "text-[#C53030]" : "text-[#5A3E2B]"} />
              <h4 className="font-bold text-xs text-[#29231F]">Compliance & Safety Hold Operations</h4>
            </div>
            <p className="text-[11px] text-[#6E6259]">
              Vehicles placed on <b>SAFETY_HOLD</b> or <b>MAINTENANCE</b> are strictly filtered out and excluded from the 7-Factor Matching Engine to protect shipper cargo.
            </p>

            <div className="flex flex-col sm:flex-row gap-2">
              <input
                type="text"
                value={safetyHoldReason}
                onChange={(e) => setSafetyHoldReason(e.target.value)}
                placeholder="Reason (e.g. RTO fitness expired, brake inspection, GPS fault)"
                className="flex-1 text-xs p-2 bg-white border border-[#E6DED5] rounded-lg"
              />
              {isSafetyHeld ? (
                <button
                  type="button"
                  onClick={() => handleToggleSafetyHold(false)}
                  disabled={busy}
                  className="px-4 py-2 bg-[#3F7D58] hover:bg-[#346647] text-white font-bold text-xs rounded-lg transition whitespace-nowrap cursor-pointer"
                >
                  Release Safety Hold
                </button>
              ) : (
                <button
                  type="button"
                  onClick={() => handleToggleSafetyHold(true)}
                  disabled={busy}
                  className="px-4 py-2 bg-[#C53030] hover:bg-[#A82828] text-white font-bold text-xs rounded-lg transition whitespace-nowrap cursor-pointer"
                >
                  Apply Safety Hold
                </button>
              )}
            </div>
          </div>

          {/* Assignment History Audit Log */}
          <div className="space-y-2">
            <div className="flex items-center gap-1.5 text-xs font-bold text-[#6E6259]">
              <History size={14} />
              <span>Assignment History Audit Trail</span>
            </div>

            <div className="space-y-2 max-h-48 overflow-y-auto">
              {assignments.map((a) => (
                <div
                  key={a.id}
                  className="p-3 bg-[#F7F5F0] rounded-lg border border-[#E6DED5] flex items-center justify-between text-xs"
                >
                  <div>
                    <div className="font-bold text-[#29231F] flex items-center gap-2">
                      <span>{a.driver_name || "Driver"}</span>
                      {a.is_active ? (
                        <span className="text-[9px] font-bold px-1.5 py-0.2 rounded bg-[#EBF7EE] text-[#24613B]">
                          ACTIVE
                        </span>
                      ) : (
                        <span className="text-[9px] font-bold px-1.5 py-0.2 rounded bg-[#EFECE6] text-[#6E6259]">
                          CONCLUDED
                        </span>
                      )}
                    </div>
                    <div className="text-[10px] text-[#8A796B] mt-0.5">
                      Assigned: {new Date(a.assigned_at).toLocaleString("en-IN")}
                      {a.unassigned_at && ` · Unassigned: ${new Date(a.unassigned_at).toLocaleString("en-IN")}`}
                    </div>
                  </div>
                  <div className="text-[10px] text-right text-[#6E6259]">
                    <div>{a.assignment_notes || "Assignment record"}</div>
                    {a.assigned_by_name && <div className="italic">By: {a.assigned_by_name}</div>}
                  </div>
                </div>
              ))}
              {assignments.length === 0 && (
                <p className="text-xs text-[#8A796B] italic text-center py-4">
                  No historical assignments logged for this vehicle.
                </p>
              )}
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-[#E6DED5] bg-[#FDFCFB] flex items-center justify-end">
          <button
            onClick={onClose}
            className="px-4 py-2 bg-[#F7F5F0] hover:bg-[#EFECE6] border border-[#E6DED5] rounded-lg text-xs font-bold text-[#29231F] transition cursor-pointer"
          >
            Done
          </button>
        </div>
      </div>
    </div>
  );
}
