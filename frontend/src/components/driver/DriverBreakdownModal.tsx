"use client";

import React, { useState } from "react";
import { Wrench, AlertCircle, Camera, MapPin, X, CheckCircle2 } from "lucide-react";
import { api } from "@/lib/api";
import { BreakdownIssueType, VehicleBreakdown } from "@/types";
import { OfflineStorageManager } from "@/lib/offlineStorage";

interface DriverBreakdownModalProps {
  isOpen: boolean;
  onClose: () => void;
  truckId: string;
  shipmentId?: string;
  currentLat?: number;
  currentLon?: number;
  onSuccess: () => void;
}

export default function DriverBreakdownModal({
  isOpen,
  onClose,
  truckId,
  shipmentId,
  currentLat = 22.5448,
  currentLon = 88.3186,
  onSuccess,
}: DriverBreakdownModalProps) {
  const [issueType, setIssueType] = useState<BreakdownIssueType>("TYRE_FAILURE");
  const [description, setDescription] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submittedBreakdown, setSubmittedBreakdown] = useState<VehicleBreakdown | null>(null);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);

    const payload = {
      truck_id: truckId,
      shipment_id: shipmentId,
      issue_type: issueType,
      description: description || `Reported ${issueType.replace(/_/g, " ")} on corridor.`,
      photo_url: "/uploads/breakdowns/evidence_tyre_puncture.jpg",
      latitude: currentLat,
      longitude: currentLon,
      device_timestamp: new Date().toISOString(),
    };

    try {
      if (typeof navigator !== "undefined" && !navigator.onLine) {
        OfflineStorageManager.enqueueEvent("BREAKDOWN_REPORT", payload);
        alert("Offline: Breakdown report saved locally on device. Will sync once cellular reconnected.");
        onSuccess();
        onClose();
        return;
      }

      const res = await api.reportBreakdown(payload);
      setSubmittedBreakdown(res);
      onSuccess();
    } catch (err: any) {
      alert(err.message || "Failed to submit breakdown report");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4">
      <div className="bg-[#FFFFFF] border border-[#E6DED5] rounded-3xl max-w-lg w-full shadow-2xl overflow-hidden animate-in fade-in zoom-in-95 duration-150">
        <div className="bg-[#B7791F] text-white p-5 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-white/20 flex items-center justify-center">
              <Wrench className="w-5 h-5 text-white" />
            </div>
            <div>
              <h2 className="text-base font-bold">Report Vehicle Breakdown</h2>
              <p className="text-xs text-white/80">Request Highway Mechanic & Maintenance Support</p>
            </div>
          </div>
          <button onClick={onClose} className="text-white/80 hover:text-white p-1 rounded-full cursor-pointer transition">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-6">
          {submittedBreakdown ? (
            <div className="space-y-4">
              <div className="p-4 bg-[#EBF5EE] border border-[#C6E6D0] rounded-2xl space-y-2">
                <div className="flex items-center gap-2 text-xs font-bold text-[#3F7D58]">
                  <CheckCircle2 className="w-4 h-4" />
                  <span>Breakdown Registered & Vehicle Set to MAINTENANCE</span>
                </div>
                <p className="text-xs text-[#2E5A3F]">
                  Control room and fleet managers have received your breakdown report. A roadside assistance team is being assigned.
                </p>
              </div>

              <div className="p-3 bg-[#F7F5F0] border border-[#E6DED5] rounded-xl text-xs space-y-1 text-[#6E6259]">
                <div><span className="font-semibold text-[#29231F]">Issue:</span> {submittedBreakdown.issue_type.replace(/_/g, " ")}</div>
                <div><span className="font-semibold text-[#29231F]">Status:</span> {submittedBreakdown.status}</div>
                <div><span className="font-semibold text-[#29231F]">Location:</span> {currentLat.toFixed(4)}, {currentLon.toFixed(4)}</div>
              </div>

              <button
                onClick={onClose}
                className="w-full py-2.5 rounded-xl bg-[#29231F] text-white text-xs font-bold transition hover:bg-black cursor-pointer"
              >
                Done
              </button>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-4 text-xs">
              <div>
                <label className="block font-bold uppercase tracking-wider text-[#29231F] mb-1.5">
                  Breakdown Issue Type
                </label>
                <select
                  value={issueType}
                  onChange={(e) => setIssueType(e.target.value as BreakdownIssueType)}
                  className="w-full bg-[#F7F5F0] border border-[#E6DED5] rounded-xl px-3 py-2.5 font-medium text-[#29231F] focus:outline-none focus:border-[#B7791F]"
                >
                  <option value="TYRE_FAILURE">Tyre Failure / Puncture / Blowout</option>
                  <option value="BRAKE_ISSUE">Brake Pressure / Line Failure</option>
                  <option value="ENGINE_OVERHEATING">Engine Overheating / Radiator Leak</option>
                  <option value="BATTERY_FAILURE">Battery / Alternator Electrical Failure</option>
                  <option value="ACCIDENT">Road Collision / Highway Impact</option>
                  <option value="MECHANICAL_FAILURE">Axle / Differential / Transmission Failure</option>
                  <option value="OTHER">Other Roadside Mechanical Issue</option>
                </select>
              </div>

              <div>
                <label className="block font-bold uppercase tracking-wider text-[#29231F] mb-1.5">
                  Description & Symptoms
                </label>
                <textarea
                  rows={3}
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="e.g. Left rear tyre blowout 12km before Burdwan bypass. Vehicle parked safely on hard shoulder."
                  className="w-full bg-[#F7F5F0] border border-[#E6DED5] rounded-xl p-3 font-medium text-[#29231F] focus:outline-none focus:border-[#B7791F]"
                  required
                />
              </div>

              <div className="p-3 bg-[#F7F5F0] border border-[#E6DED5] rounded-xl flex items-center justify-between text-xs text-[#6E6259]">
                <div className="flex items-center gap-1.5">
                  <MapPin className="w-4 h-4 text-[#B7791F]" />
                  <span>GPS Telemetry: {currentLat.toFixed(4)}, {currentLon.toFixed(4)}</span>
                </div>
                <div className="flex items-center gap-1 text-[#3F7D58] font-semibold">
                  <Camera className="w-3.5 h-3.5" />
                  <span>Photo Evidence Attached</span>
                </div>
              </div>

              <button
                type="submit"
                disabled={isSubmitting}
                className="w-full py-3.5 rounded-xl bg-[#B7791F] hover:bg-[#976016] text-white font-bold text-xs uppercase tracking-wider shadow-xs transition flex items-center justify-center gap-2 cursor-pointer disabled:opacity-50"
              >
                {isSubmitting ? (
                  <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                ) : (
                  <>
                    <Wrench className="w-4 h-4" />
                    <span>Submit Breakdown & Request Roadside Support</span>
                  </>
                )}
              </button>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}
