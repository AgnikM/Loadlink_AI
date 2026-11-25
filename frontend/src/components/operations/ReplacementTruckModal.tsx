"use client";

import React, { useState, useEffect } from "react";
import { Truck, ArrowLeftRight, CheckCircle2, ShieldAlert, X, Lock, Check } from "lucide-react";
import { api } from "@/lib/api";
import { TruckOut, TruckReplacement } from "@/types";

interface ReplacementTruckModalProps {
  isOpen: boolean;
  onClose: () => void;
  shipmentId: string;
  originalTruckRegistration?: string;
  onSuccess: () => void;
}

export default function ReplacementTruckModal({
  isOpen,
  onClose,
  shipmentId,
  originalTruckRegistration = "WB-19-AF-0184",
  onSuccess,
}: ReplacementTruckModalProps) {
  const [step, setStep] = useState<"SELECT_TRUCK" | "APPROVALS" | "CUSTODY" | "DISPATCHED">("SELECT_TRUCK");
  const [eligibleTrucks, setEligibleTrucks] = useState<TruckOut[]>([]);
  const [selectedTruck, setSelectedTruck] = useState<TruckOut | null>(null);
  const [replacementWorkflow, setReplacementWorkflow] = useState<TruckReplacement | null>(null);
  const [reason, setReason] = useState("Severe transmission failure on NH19 corridor requiring transhipment");
  const [newSealNumber, setNewSealNumber] = useState("SEAL-REPL-992201");
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    if (isOpen && shipmentId) {
      api.getEligibleReplacementTrucks(shipmentId)
        .then(setEligibleTrucks)
        .catch(() => setEligibleTrucks([]));
    }
  }, [isOpen, shipmentId]);

  if (!isOpen) return null;

  const handleInitiate = async () => {
    if (!selectedTruck) return;
    setIsSubmitting(true);
    try {
      const res = await api.initiateReplacement({
        shipment_id: shipmentId,
        replacement_truck_id: selectedTruck.id,
        replacement_driver_id: selectedTruck.driver_id || "unassigned",
        reason,
      });
      setReplacementWorkflow(res);
      setStep("APPROVALS");
    } catch (err: any) {
      alert(err.message || "Failed to initiate replacement workflow");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleApprove = async (role: "DEALER" | "TRANSPORTER") => {
    if (!replacementWorkflow) return;
    setIsSubmitting(true);
    try {
      const res = await api.approveReplacement(replacementWorkflow.id, {
        approver_role: role,
        approved: true,
      });
      setReplacementWorkflow(res);
      if (res.dealer_approved && res.transporter_approved) {
        setStep("CUSTODY");
      }
    } catch (err: any) {
      alert(err.message || "Approval failed");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleCustodyTransfer = async () => {
    if (!replacementWorkflow) return;
    setIsSubmitting(true);
    try {
      const res = await api.recordCustodyTransfer(replacementWorkflow.id, {
        transfer_cargo_condition: "INTACT",
        new_seal_number: newSealNumber,
        transfer_photos: ["/uploads/replacements/cargo_transfer_handover.jpg"],
        driver_acknowledgement: true,
      });
      setReplacementWorkflow(res);

      // Now complete atomic reassignment
      const completed = await api.completeReplacement(replacementWorkflow.id);
      setReplacementWorkflow(completed);
      setStep("DISPATCHED");
      onSuccess();
    } catch (err: any) {
      alert(err.message || "Custody transfer failed");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4">
      <div className="bg-[#FFFFFF] border border-[#E6DED5] rounded-3xl max-w-xl w-full shadow-2xl overflow-hidden animate-in fade-in zoom-in-95 duration-150">
        <div className="bg-[#5A3E2B] text-white p-5 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-white/20 flex items-center justify-center">
              <ArrowLeftRight className="w-5 h-5 text-white" />
            </div>
            <div>
              <h2 className="text-base font-bold">Emergency Replacement Vehicle Workflow</h2>
              <p className="text-xs text-white/80">Breakdown Transhipment & Audited Cargo Custody Transfer</p>
            </div>
          </div>
          <button onClick={onClose} className="text-white/80 hover:text-white p-1 rounded-full cursor-pointer transition">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-6 space-y-5 text-xs">
          {/* Step 1: Select Eligible Replacement Truck */}
          {step === "SELECT_TRUCK" && (
            <div className="space-y-4">
              <div className="p-3.5 bg-[#FEF6E7] border border-[#FCDCA0] rounded-xl text-xs text-[#B7791F]">
                Original Broken Vehicle: <span className="font-bold">{originalTruckRegistration}</span>. Select an eligible verified truck on the corridor with capacity fit.
              </div>

              <div>
                <label className="block font-bold uppercase tracking-wider text-[#29231F] mb-1.5">
                  Available Eligible Corridor Fleets ({eligibleTrucks.length})
                </label>
                {eligibleTrucks.length === 0 ? (
                  <div className="p-4 bg-[#F7F5F0] rounded-xl border text-center text-[#6E6259]">
                    No eligible trucks with sufficient payload capacity currently online.
                  </div>
                ) : (
                  <div className="space-y-2 max-h-56 overflow-y-auto">
                    {eligibleTrucks.map((t) => (
                      <button
                        key={t.id}
                        type="button"
                        onClick={() => setSelectedTruck(t)}
                        className={`w-full p-3 rounded-xl border text-left flex items-center justify-between transition cursor-pointer ${
                          selectedTruck?.id === t.id
                            ? "bg-[#F0EAE1] border-[#5A3E2B] ring-1 ring-[#5A3E2B]"
                            : "bg-[#F7F5F0] border-[#E6DED5] hover:bg-[#EAE4DC]"
                        }`}
                      >
                        <div>
                          <div className="font-bold text-[#29231F]">{t.registration_no}</div>
                          <div className="text-[11px] text-[#6E6259]">
                            {t.capacity_tons}T {t.truck_type.replace(/_/g, " ")} • Driver: {t.driver_name || "Assigned Driver"}
                          </div>
                        </div>
                        <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-[#EBF5EE] text-[#3F7D58]">
                          Ready for Loading
                        </span>
                      </button>
                    ))}
                  </div>
                )}
              </div>

              <div>
                <label className="block font-bold uppercase tracking-wider text-[#29231F] mb-1">
                  Reason for Transhipment
                </label>
                <input
                  type="text"
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                  className="w-full bg-[#F7F5F0] border border-[#E6DED5] rounded-xl px-3 py-2 text-xs font-medium text-[#29231F] focus:outline-none focus:border-[#5A3E2B]"
                />
              </div>

              <button
                type="button"
                disabled={!selectedTruck || isSubmitting}
                onClick={handleInitiate}
                className="w-full py-3 rounded-xl bg-[#5A3E2B] hover:bg-[#463021] text-white font-bold text-xs uppercase tracking-wider transition disabled:opacity-50 cursor-pointer"
              >
                Initiate Replacement & Request Dual Approval
              </button>
            </div>
          )}

          {/* Step 2: Dual Approval */}
          {step === "APPROVALS" && replacementWorkflow && (
            <div className="space-y-4">
              <div className="p-4 bg-[#F7F5F0] border border-[#E6DED5] rounded-2xl space-y-2">
                <span className="font-bold uppercase tracking-wider text-[#29231F] text-[11px]">
                  Approval Governance (Shipper & Transporter)
                </span>
                <p className="text-[#6E6259]">
                  Both parties must verify and approve the replacement vehicle before cargo custody can be transferred.
                </p>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className="p-3.5 bg-[#FFFFFF] border border-[#E6DED5] rounded-xl flex items-center justify-between">
                  <div>
                    <span className="font-bold text-[#29231F]">Dealer / Shipper</span>
                    <p className="text-[10px] text-[#6E6259]">{replacementWorkflow.dealer_approved ? "Approved" : "Pending Approval"}</p>
                  </div>
                  {replacementWorkflow.dealer_approved ? (
                    <CheckCircle2 className="w-5 h-5 text-[#3F7D58]" />
                  ) : (
                    <button
                      type="button"
                      onClick={() => handleApprove("DEALER")}
                      disabled={isSubmitting}
                      className="px-2.5 py-1 rounded bg-[#3F7D58] text-white text-[10px] font-bold cursor-pointer"
                    >
                      Approve
                    </button>
                  )}
                </div>

                <div className="p-3.5 bg-[#FFFFFF] border border-[#E6DED5] rounded-xl flex items-center justify-between">
                  <div>
                    <span className="font-bold text-[#29231F]">Transporter / Fleet</span>
                    <p className="text-[10px] text-[#6E6259]">{replacementWorkflow.transporter_approved ? "Approved" : "Pending Approval"}</p>
                  </div>
                  {replacementWorkflow.transporter_approved ? (
                    <CheckCircle2 className="w-5 h-5 text-[#3F7D58]" />
                  ) : (
                    <button
                      type="button"
                      onClick={() => handleApprove("TRANSPORTER")}
                      disabled={isSubmitting}
                      className="px-2.5 py-1 rounded bg-[#3F7D58] text-white text-[10px] font-bold cursor-pointer"
                    >
                      Approve
                    </button>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* Step 3: Cargo Custody Transfer */}
          {step === "CUSTODY" && replacementWorkflow && (
            <div className="space-y-4">
              <div className="p-4 bg-[#EBF5EE] border border-[#C6E6D0] rounded-2xl text-xs space-y-1 text-[#2E5A3F]">
                <div className="font-bold">Dual Approvals Confirmed!</div>
                <p>Now perform physical cargo transfer, apply tamper-evident container seal, and log driver custody acknowledgement.</p>
              </div>

              <div>
                <label className="block font-bold uppercase tracking-wider text-[#29231F] mb-1">
                  New Tamper-Evident Seal Number
                </label>
                <input
                  type="text"
                  value={newSealNumber}
                  onChange={(e) => setNewSealNumber(e.target.value)}
                  className="w-full bg-[#F7F5F0] border border-[#E6DED5] rounded-xl px-3 py-2 text-xs font-mono font-bold text-[#29231F] focus:outline-none focus:border-[#3F7D58]"
                  required
                />
              </div>

              <div className="p-3 bg-[#F7F5F0] border border-[#E6DED5] rounded-xl text-[11px] text-[#6E6259] space-y-1">
                <div>📸 Custody Transfer Photos: 2 Attached (Intact condition)</div>
                <div>✍️ Receiving Driver Acknowledgement: Confirmed</div>
              </div>

              <button
                type="button"
                disabled={isSubmitting}
                onClick={handleCustodyTransfer}
                className="w-full py-3.5 rounded-xl bg-[#3F7D58] hover:bg-[#346648] text-white font-bold text-xs uppercase tracking-wider transition flex items-center justify-center gap-2 cursor-pointer disabled:opacity-50"
              >
                {isSubmitting ? (
                  <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                ) : (
                  <>
                    <Lock className="w-4 h-4" />
                    <span>Record Custody & Dispatch Replacement Truck</span>
                  </>
                )}
              </button>
            </div>
          )}

          {/* Step 4: Dispatched */}
          {step === "DISPATCHED" && (
            <div className="space-y-4 text-center">
              <div className="w-12 h-12 rounded-full bg-[#EBF5EE] text-[#3F7D58] flex items-center justify-center mx-auto">
                <CheckCircle2 className="w-7 h-7" />
              </div>
              <h3 className="text-base font-bold text-[#29231F]">
                Replacement Truck Dispatched Successfully
              </h3>
              <p className="text-xs text-[#6E6259]">
                Cargo safely transferred under auditable seal {newSealNumber}. Shipment tracking and live ETA have been reassigned to {replacementWorkflow?.replacement_truck_reg || selectedTruck?.registration_no}.
              </p>
              <button
                onClick={onClose}
                className="w-full py-2.5 rounded-xl bg-[#29231F] text-white text-xs font-bold transition hover:bg-black cursor-pointer"
              >
                Done
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
