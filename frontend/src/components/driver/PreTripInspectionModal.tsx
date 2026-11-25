"use client";

import React, { useState } from "react";
import { ShieldCheck, AlertTriangle, CheckSquare, Square, X, CheckCircle2 } from "lucide-react";
import { api } from "@/lib/api";
import { PreTripInspection } from "@/types";

interface PreTripInspectionModalProps {
  isOpen: boolean;
  onClose: () => void;
  truckId: string;
  onSuccess: () => void;
}

export default function PreTripInspectionModal({
  isOpen,
  onClose,
  truckId,
  onSuccess,
}: PreTripInspectionModalProps) {
  const [checklist, setChecklist] = useState({
    tyres_ok: true,
    brakes_ok: true,
    lights_ok: true,
    indicators_ok: true,
    mirrors_ok: true,
    steering_ok: true,
    engine_indicators_ok: true,
    oil_level_ok: true,
    coolant_level_ok: true,
    documents_valid: true,
    cargo_securing_equipment_ok: true,
  });

  const [defectNotes, setDefectNotes] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [inspectionResult, setInspectionResult] = useState<PreTripInspection | null>(null);

  if (!isOpen) return null;

  const toggleItem = (key: keyof typeof checklist) => {
    setChecklist((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  const hasCriticalDefect = (
    !checklist.brakes_ok ||
    !checklist.tyres_ok ||
    !checklist.steering_ok ||
    !checklist.cargo_securing_equipment_ok
  );

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);

    const payload = {
      truck_id: truckId,
      ...checklist,
      defect_description: defectNotes || (hasCriticalDefect ? "Critical pre-trip defect flagged by driver." : undefined),
      inspection_evidence_photos: ["/uploads/inspections/pre_trip_walkaround.jpg"],
    };

    try {
      const res = await api.submitPreTripInspection(payload);
      setInspectionResult(res);
      onSuccess();
    } catch (err: any) {
      alert(err.message || "Failed to submit pre-trip inspection");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4">
      <div className="bg-[#FFFFFF] border border-[#E6DED5] rounded-3xl max-w-lg w-full shadow-2xl overflow-hidden max-h-[90vh] flex flex-col animate-in fade-in zoom-in-95 duration-150">
        <div className="bg-[#29231F] text-white p-5 flex items-center justify-between shrink-0">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-white/10 flex items-center justify-center">
              <ShieldCheck className="w-5 h-5 text-white" />
            </div>
            <div>
              <h2 className="text-base font-bold">Pre-Trip Safety Inspection</h2>
              <p className="text-xs text-white/80">Mandatory 11-Point Highway Readiness Verification</p>
            </div>
          </div>
          <button onClick={onClose} className="text-white/80 hover:text-white p-1 rounded-full cursor-pointer transition">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-6 overflow-y-auto space-y-4 text-xs">
          {inspectionResult ? (
            <div className="space-y-4">
              {inspectionResult.safety_hold_triggered ? (
                <div className="p-4 bg-[#FEF2F2] border border-[#FCA5A5] rounded-2xl space-y-2">
                  <div className="flex items-center gap-2 text-xs font-bold text-[#DC2626]">
                    <AlertTriangle className="w-4 h-4" />
                    <span>VEHICLE PLACED ON SAFETY_HOLD</span>
                  </div>
                  <p className="text-xs text-[#991B1B]">
                    Critical defects were identified during pre-trip checklist. Vehicle dispatch is automatically blocked. Only an authorized Fleet Manager or Compliance Officer can clear this safety hold after inspection and repair verification.
                  </p>
                </div>
              ) : (
                <div className="p-4 bg-[#EBF5EE] border border-[#C6E6D0] rounded-2xl space-y-2">
                  <div className="flex items-center gap-2 text-xs font-bold text-[#3F7D58]">
                    <CheckCircle2 className="w-4 h-4" />
                    <span>Pre-Trip Inspection Passed</span>
                  </div>
                  <p className="text-xs text-[#2E5A3F]">
                    All 11 safety and mechanical points verified. Vehicle is roadworthy and approved for highway dispatch.
                  </p>
                </div>
              )}

              <button
                onClick={onClose}
                className="w-full py-2.5 rounded-xl bg-[#29231F] text-white text-xs font-bold transition hover:bg-black cursor-pointer"
              >
                Close Checklist
              </button>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-4">
              {hasCriticalDefect && (
                <div className="p-3 bg-[#FEF2F2] border border-[#FCA5A5] rounded-xl flex items-center gap-2 text-xs text-[#DC2626] font-semibold">
                  <AlertTriangle className="w-4 h-4 shrink-0" />
                  <span>Warning: Defective brakes, tyres, steering, or cargo securing will trigger a SAFETY_HOLD.</span>
                </div>
              )}

              <div className="grid grid-cols-1 md:grid-cols-2 gap-2.5">
                {[
                  { key: "tyres_ok", label: "Tyres & Pressure (Critical)", critical: true },
                  { key: "brakes_ok", label: "Service & Air Brakes (Critical)", critical: true },
                  { key: "steering_ok", label: "Steering & Axle Alignment (Critical)", critical: true },
                  { key: "cargo_securing_equipment_ok", label: "Cargo Straps & Chains (Critical)", critical: true },
                  { key: "lights_ok", label: "Headlights & Tail Lamps", critical: false },
                  { key: "indicators_ok", label: "Turn Indicators & Hazard Flashers", critical: false },
                  { key: "mirrors_ok", label: "Rear View & Side Mirrors", critical: false },
                  { key: "engine_indicators_ok", label: "Instrument Cluster & Warning Lamps", critical: false },
                  { key: "oil_level_ok", label: "Engine Lubricating Oil Level", critical: false },
                  { key: "coolant_level_ok", label: "Radiator Coolant Level", critical: false },
                  { key: "documents_valid", label: "e-Way Bill, RC, PUC & Insurance Valid", critical: false },
                ].map((item) => {
                  const val = checklist[item.key as keyof typeof checklist];
                  return (
                    <button
                      key={item.key}
                      type="button"
                      onClick={() => toggleItem(item.key as keyof typeof checklist)}
                      className={`p-2.5 rounded-xl border flex items-center justify-between text-left transition cursor-pointer ${
                        val
                          ? "bg-[#EBF5EE] border-[#C6E6D0] text-[#2E5A3F]"
                          : "bg-[#FEF2F2] border-[#FCA5A5] text-[#991B1B]"
                      }`}
                    >
                      <span className="font-semibold">{item.label}</span>
                      {val ? (
                        <CheckSquare className="w-4 h-4 text-[#3F7D58] shrink-0" />
                      ) : (
                        <Square className="w-4 h-4 text-[#DC2626] shrink-0" />
                      )}
                    </button>
                  );
                })}
              </div>

              <div>
                <label className="block font-bold uppercase tracking-wider text-[#29231F] mb-1">
                  Defect Description / Observations
                </label>
                <textarea
                  rows={2}
                  value={defectNotes}
                  onChange={(e) => setDefectNotes(e.target.value)}
                  placeholder="Record any wear, tear, or mechanical observations before starting journey..."
                  className="w-full bg-[#F7F5F0] border border-[#E6DED5] rounded-xl p-3 font-medium text-[#29231F] focus:outline-none focus:border-[#29231F]"
                />
              </div>

              <button
                type="submit"
                disabled={isSubmitting}
                className="w-full py-3.5 rounded-xl bg-[#29231F] hover:bg-black text-white font-bold text-xs uppercase tracking-wider shadow-xs transition flex items-center justify-center gap-2 cursor-pointer disabled:opacity-50"
              >
                {isSubmitting ? (
                  <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                ) : (
                  <>
                    <ShieldCheck className="w-4 h-4" />
                    <span>Submit Pre-Trip Safety Signoff</span>
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
