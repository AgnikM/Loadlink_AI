"use client";

import React, { useState, useEffect, useCallback } from "react";
import {
  X,
  FileText,
  ShieldCheck,
  CheckCircle2,
  Clock,
  AlertTriangle,
  Copy,
  Check,
  Building2,
  Truck,
  IndianRupee,
  Edit3,
  ChevronDown,
  ChevronUp,
} from "lucide-react";
import { FreightAgreement } from "@/types";
import { api } from "@/lib/api";

interface DirectFreightAgreementModalProps {
  isOpen: boolean;
  onClose: () => void;
  bookingId: string;
  currentUser?: any;
  onAgreementUpdated?: () => void;
}

const fmt = (n: number) =>
  new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  }).format(n || 0);

export default function DirectFreightAgreementModal({
  isOpen,
  onClose,
  bookingId,
  currentUser,
  onAgreementUpdated,
}: DirectFreightAgreementModalProps) {
  const [agreement, setAgreement] = useState<FreightAgreement | null>(null);
  const [loading, setLoading] = useState(true);
  const [actionBusy, setActionBusy] = useState(false);
  const [errorMsg, setErrorMsg] = useState("");
  const [successMsg, setSuccessMsg] = useState("");
  const [signatureText, setSignatureText] = useState("");
  const [agreementAgreed, setAgreementAgreed] = useState(false);
  const [copiedHash, setCopiedHash] = useState(false);
  const [showAmendForm, setShowAmendForm] = useState(false);

  // Amend form state
  const [amendFreight, setAmendFreight] = useState<number>(0);
  const [amendCharges, setAmendCharges] = useState<number>(0);
  const [amendPickupTerms, setAmendPickupTerms] = useState<string>("");
  const [amendDetention, setAmendDetention] = useState<string>("");

  const loadAgreement = useCallback(async () => {
    if (!bookingId) return;
    setLoading(true);
    setErrorMsg("");
    try {
      const data = await api.getBookingAgreement(bookingId);
      setAgreement(data);
      setAmendFreight(data.agreed_freight_inr || 0);
      setAmendCharges(data.additional_charges_inr || 0);
      setAmendPickupTerms(data.pickup_delivery_terms || "");
      setAmendDetention(data.delay_detention_rules || "");
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to load freight agreement");
    } finally {
      setLoading(false);
    }
  }, [bookingId]);

  useEffect(() => {
    if (isOpen) {
      loadAgreement();
      setSuccessMsg("");
      setErrorMsg("");
      setSignatureText(currentUser?.name ? `Signed by ${currentUser.name}` : "Digital Signature");
      setAgreementAgreed(false);
    }
  }, [isOpen, loadAgreement, currentUser]);

  if (!isOpen) return null;

  const handleCopyHash = () => {
    if (agreement?.content_sha256) {
      navigator.clipboard.writeText(agreement.content_sha256);
      setCopiedHash(true);
      setTimeout(() => setCopiedHash(false), 2000);
    }
  };

  const handleAcceptAgreement = async () => {
    if (!agreementAgreed) {
      setErrorMsg("Please check the confirmation box to verify your agreement.");
      return;
    }
    setActionBusy(true);
    setErrorMsg("");
    try {
      const updated = await api.acceptAgreement(
        bookingId,
        signatureText || `Accepted by ${currentUser?.name || "Authorized Representative"}`
      );
      setAgreement(updated);
      setSuccessMsg("Freight agreement successfully accepted and recorded in the audit trail.");
      onAgreementUpdated?.();
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to accept agreement");
    } finally {
      setActionBusy(false);
    }
  };

  const handleAmendAgreement = async (e: React.FormEvent) => {
    e.preventDefault();
    setActionBusy(true);
    setErrorMsg("");
    try {
      const updated = await api.amendAgreement(bookingId, {
        agreed_freight_inr: Number(amendFreight),
        additional_charges_inr: Number(amendCharges),
        pickup_delivery_terms: amendPickupTerms,
        delay_detention_rules: amendDetention,
      });
      setAgreement(updated);
      setShowAmendForm(false);
      setSuccessMsg(`Agreement terms updated to Version ${updated.version}. Prior acceptances cleared for mutual re-signing.`);
      onAgreementUpdated?.();
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to amend agreement");
    } finally {
      setActionBusy(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4 overflow-y-auto">
      <div className="bg-[#FFFFFF] border border-[#E6DED5] rounded-2xl w-full max-w-3xl max-h-[90vh] flex flex-col shadow-2xl overflow-hidden my-auto animate-in fade-in zoom-in-95 duration-150">
        {/* Header */}
        <div className="p-5 border-b border-[#E6DED5] flex items-center justify-between bg-[#FDFCFB]">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-[#5A3E2B] text-white flex items-center justify-center shadow-xs">
              <FileText size={20} />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="font-bold text-base text-[#29231F]">Direct Freight Agreement</h3>
                {agreement && (
                  <span className="text-[10px] font-mono font-bold px-2 py-0.5 rounded-full bg-[#F0EAE1] text-[#5A3E2B] border border-[#E6DED5]">
                    v{agreement.version}.0
                  </span>
                )}
                {agreement?.is_fully_executed ? (
                  <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-[#EBF7EE] text-[#24613B] border border-[#BDE5C8] flex items-center gap-1">
                    <CheckCircle2 size={11} /> Fully Executed
                  </span>
                ) : (
                  <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-[#FEF3C7] text-[#92400E] border-[#FDE68A] flex items-center gap-1">
                    <Clock size={11} /> Pending Signatures
                  </span>
                )}
              </div>
              <p className="text-xs text-[#6E6259]">
                Marketplace contract directly between Shipper & Transporter · LoadLink Recordkeeping
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

        {/* Content Body */}
        <div className="p-6 overflow-y-auto space-y-5 text-xs text-[#29231F]">
          {loading ? (
            <div className="py-12 text-center text-[#6E6259] space-y-2">
              <Clock size={28} className="mx-auto animate-spin text-[#5A3E2B]" />
              <p>Fetching legal contract and immutable content hash...</p>
            </div>
          ) : errorMsg && !agreement ? (
            <div className="p-4 bg-[#FAEDED] border border-[#F1C4C4] rounded-xl text-[#C53030]">
              {errorMsg}
            </div>
          ) : agreement ? (
            <>
              {/* Notifications */}
              {successMsg && (
                <div className="p-3 bg-[#EBF7EE] border border-[#BDE5C8] rounded-xl text-[#24613B] font-medium flex items-center gap-2">
                  <CheckCircle2 size={16} />
                  <span>{successMsg}</span>
                </div>
              )}
              {errorMsg && (
                <div className="p-3 bg-[#FAEDED] border border-[#F1C4C4] rounded-xl text-[#C53030] font-medium flex items-center gap-2">
                  <AlertTriangle size={16} />
                  <span>{errorMsg}</span>
                </div>
              )}

              {/* SHA-256 Canonical Integrity Card */}
              <div className="p-3.5 bg-[#F7F5F0] rounded-xl border border-[#E6DED5] flex items-center justify-between gap-3">
                <div className="min-w-0">
                  <div className="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wider text-[#8A796B]">
                    <ShieldCheck size={13} className="text-[#3F7D58]" />
                    <span>Cryptographic Content Hash (SHA-256)</span>
                  </div>
                  <div className="font-mono text-[11px] text-[#29231F] font-semibold truncate select-all mt-0.5">
                    {agreement.content_sha256}
                  </div>
                </div>
                <button
                  onClick={handleCopyHash}
                  className="px-2.5 py-1.5 bg-white hover:bg-[#EFECE6] border border-[#E6DED5] rounded-lg text-xs font-semibold text-[#5A3E2B] flex items-center gap-1 shrink-0 transition"
                >
                  {copiedHash ? <Check size={13} className="text-[#3F7D58]" /> : <Copy size={13} />}
                  <span>{copiedHash ? "Copied" : "Copy"}</span>
                </button>
              </div>

              {/* Parties Acceptance Grid */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* Dealer Party */}
                <div
                  className={`p-4 rounded-xl border ${
                    agreement.is_accepted_by_dealer
                      ? "bg-[#F4FBF6] border-[#BDE5C8]"
                      : "bg-white border-[#E6DED5]"
                  }`}
                >
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-[10px] font-bold uppercase tracking-wider text-[#5A3E2B] flex items-center gap-1">
                      <Building2 size={12} /> Party 1: Shipper / Dealer
                    </span>
                    <span
                      className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                        agreement.is_accepted_by_dealer
                          ? "bg-[#EBF7EE] text-[#24613B]"
                          : "bg-[#FEF3C7] text-[#92400E]"
                      }`}
                    >
                      {agreement.is_accepted_by_dealer ? "✓ Accepted" : "Pending"}
                    </span>
                  </div>
                  <div className="font-bold text-sm text-[#29231F]">
                    {agreement.dealer_name || "Shipper"}
                  </div>
                  <div className="text-[11px] text-[#6E6259]">
                    {agreement.dealer_org_name || "Commercial Consignor"}
                  </div>
                  {agreement.is_accepted_by_dealer && (
                    <div className="mt-2 pt-2 border-t border-[#BDE5C8]/60 text-[10px] text-[#24613B] font-mono">
                      Timestamp: {new Date(agreement.acceptances.find((a) => a.user_role === "DEALER")?.accepted_at || Date.now()).toLocaleString("en-IN")}
                    </div>
                  )}
                </div>

                {/* Transporter Party */}
                <div
                  className={`p-4 rounded-xl border ${
                    agreement.is_accepted_by_transporter
                      ? "bg-[#F4FBF6] border-[#BDE5C8]"
                      : "bg-white border-[#E6DED5]"
                  }`}
                >
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-[10px] font-bold uppercase tracking-wider text-[#5A3E2B] flex items-center gap-1">
                      <Truck size={12} /> Party 2: Transporter / Carrier
                    </span>
                    <span
                      className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                        agreement.is_accepted_by_transporter
                          ? "bg-[#EBF7EE] text-[#24613B]"
                          : "bg-[#FEF3C7] text-[#92400E]"
                      }`}
                    >
                      {agreement.is_accepted_by_transporter ? "✓ Accepted" : "Pending"}
                    </span>
                  </div>
                  <div className="font-bold text-sm text-[#29231F]">
                    {agreement.transporter_name || "Carrier Representative"}
                  </div>
                  <div className="text-[11px] text-[#6E6259]">
                    {agreement.transporter_org_name || "Licensed Fleet Carrier"}
                  </div>
                  {agreement.is_accepted_by_transporter && (
                    <div className="mt-2 pt-2 border-t border-[#BDE5C8]/60 text-[10px] text-[#24613B] font-mono">
                      Timestamp: {new Date(agreement.acceptances.find((a) => a.user_role === "TRANSPORTER" || a.user_role === "DRIVER")?.accepted_at || Date.now()).toLocaleString("en-IN")}
                    </div>
                  )}
                </div>
              </div>

              {/* Commercial Valuation Grid */}
              <div className="bg-[#FDFCFB] p-4 rounded-xl border border-[#E6DED5] grid grid-cols-3 gap-3 text-center">
                <div className="border-r border-[#E6DED5] pr-2">
                  <div className="text-[10px] font-bold uppercase text-[#8A796B]">Agreed Base Freight</div>
                  <div className="text-base font-black font-mono text-[#29231F] mt-0.5">
                    {fmt(agreement.agreed_freight_inr)}
                  </div>
                </div>
                <div className="border-r border-[#E6DED5] pr-2">
                  <div className="text-[10px] font-bold uppercase text-[#8A796B]">Additional Charges</div>
                  <div className="text-base font-black font-mono text-[#6E6259] mt-0.5">
                    {fmt(agreement.additional_charges_inr)}
                  </div>
                </div>
                <div>
                  <div className="text-[10px] font-bold uppercase text-[#5A3E2B]">Total Contract Value</div>
                  <div className="text-base font-black font-mono text-[#5A3E2B] mt-0.5">
                    {fmt(agreement.total_contract_value_inr)}
                  </div>
                </div>
              </div>

              {/* Operational & Cargo Details */}
              <div className="p-4 bg-white rounded-xl border border-[#E6DED5] space-y-2">
                <h4 className="font-bold text-xs uppercase tracking-wider text-[#8A796B]">
                  Consignment & Assigned Vehicle Details
                </h4>
                <div className="grid grid-cols-2 gap-2 text-xs">
                  <div>
                    <span className="text-[#6E6259]">Cargo Summary: </span>
                    <span className="font-semibold text-[#29231F]">{agreement.cargo_details}</span>
                  </div>
                  <div>
                    <span className="text-[#6E6259]">Vehicle Reg: </span>
                    <span className="font-mono font-bold text-[#29231F]">
                      {agreement.vehicle_details?.registration_no || "WB Fleet"}
                    </span>
                  </div>
                  <div>
                    <span className="text-[#6E6259]">Vehicle Type: </span>
                    <span className="font-semibold text-[#29231F]">
                      {agreement.vehicle_details?.truck_type || "Commercial Truck"} ({agreement.vehicle_details?.capacity_tons || 16}T)
                    </span>
                  </div>
                  <div>
                    <span className="text-[#6E6259]">Driver: </span>
                    <span className="font-semibold text-[#29231F]">
                      {agreement.driver_details?.name || "Assigned Driver"} ({agreement.driver_details?.license || "RTO Verified"})
                    </span>
                  </div>
                </div>
              </div>

              {/* Legal Terms Specifications */}
              <div className="space-y-2">
                <h4 className="font-bold text-xs uppercase tracking-wider text-[#8A796B]">
                  Standard Terms & Dispute Framework
                </h4>
                <div className="space-y-2 text-[11px] text-[#6E6259]">
                  <div className="p-3 bg-[#F7F5F0] rounded-lg border border-[#E6DED5]">
                    <b className="text-[#29231F]">Pickup & Delivery: </b>
                    {agreement.pickup_delivery_terms}
                  </div>
                  <div className="p-3 bg-[#F7F5F0] rounded-lg border border-[#E6DED5]">
                    <b className="text-[#29231F]">Delay & Detention: </b>
                    {agreement.delay_detention_rules}
                  </div>
                  <div className="p-3 bg-[#F7F5F0] rounded-lg border border-[#E6DED5]">
                    <b className="text-[#29231F]">Insurance & Liabilities: </b>
                    {agreement.insurance_requirements}
                  </div>
                  <div className="p-3 bg-[#F7F5F0] rounded-lg border border-[#E6DED5]">
                    <b className="text-[#29231F]">Claims & Disputes: </b>
                    {agreement.claims_dispute_conditions}
                  </div>
                </div>
              </div>

              {/* Digital Acceptance Section */}
              {!agreement.is_fully_executed && (
                <div className="p-4 bg-[#FDFCFB] rounded-xl border border-[#5A3E2B]/30 space-y-3">
                  <div className="flex items-center gap-2">
                    <ShieldCheck size={18} className="text-[#5A3E2B]" />
                    <h4 className="font-bold text-xs text-[#29231F]">Digital Contract Acceptance</h4>
                  </div>
                  <p className="text-[11px] text-[#6E6259]">
                    Explicit electronic assent binds both parties to version v{agreement.version}.0 under the Indian Information Technology Act provisions for digital contracts.
                  </p>

                  <div className="space-y-2">
                    <label className="block">
                      <span className="text-[10px] font-bold text-[#6E6259] uppercase">Authorized Signatory Name</span>
                      <input
                        type="text"
                        value={signatureText}
                        onChange={(e) => setSignatureText(e.target.value)}
                        placeholder="e.g. Ramesh Kumar (Authorized Signatory)"
                        className="w-full text-xs p-2.5 bg-white border border-[#E6DED5] rounded-lg mt-0.5"
                      />
                    </label>

                    <label className="flex items-start gap-2 pt-1 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={agreementAgreed}
                        onChange={(e) => setAgreementAgreed(e.target.checked)}
                        className="mt-0.5 accent-[#5A3E2B]"
                      />
                      <span className="text-[11px] text-[#29231F] font-medium leading-tight">
                        I hereby confirm that I represent my organization, have reviewed all terms of this agreement, and give digital consent to bind my party to this freight agreement.
                      </span>
                    </label>
                  </div>

                  <button
                    onClick={handleAcceptAgreement}
                    disabled={actionBusy || !agreementAgreed}
                    className="w-full py-2.5 bg-[#3F7D58] hover:bg-[#346647] text-white text-xs font-bold rounded-lg transition disabled:opacity-50 flex items-center justify-center gap-1.5 shadow-xs cursor-pointer"
                  >
                    {actionBusy ? "Recording Assent..." : `Accept & Digitally Sign Agreement v${agreement.version}.0`}
                  </button>
                </div>
              )}

              {/* Amend Agreement Collapsible Section */}
              <div className="border border-[#E6DED5] rounded-xl overflow-hidden">
                <button
                  type="button"
                  onClick={() => setShowAmendForm(!showAmendForm)}
                  className="w-full p-3 bg-[#F7F5F0] hover:bg-[#EFECE6] flex items-center justify-between text-xs font-bold text-[#29231F] transition"
                >
                  <span className="flex items-center gap-2">
                    <Edit3 size={14} className="text-[#5A3E2B]" />
                    <span>Amend Commercial Terms (Requires Mutual Re-Signing)</span>
                  </span>
                  {showAmendForm ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                </button>

                {showAmendForm && (
                  <form onSubmit={handleAmendAgreement} className="p-4 bg-white space-y-3 border-t border-[#E6DED5]">
                    <div className="grid grid-cols-2 gap-3">
                      <label>
                        <span className="text-[10px] font-bold text-[#6E6259] uppercase">Agreed Freight (₹)</span>
                        <input
                          type="number"
                          value={amendFreight}
                          onChange={(e) => setAmendFreight(Number(e.target.value))}
                          className="w-full text-xs p-2 bg-[#F7F5F0] border border-[#E6DED5] rounded-lg font-mono"
                          required
                        />
                      </label>
                      <label>
                        <span className="text-[10px] font-bold text-[#6E6259] uppercase">Additional Charges (₹)</span>
                        <input
                          type="number"
                          value={amendCharges}
                          onChange={(e) => setAmendCharges(Number(e.target.value))}
                          className="w-full text-xs p-2 bg-[#F7F5F0] border border-[#E6DED5] rounded-lg font-mono"
                        />
                      </label>
                    </div>

                    <label className="block">
                      <span className="text-[10px] font-bold text-[#6E6259] uppercase">Pickup & Delivery Terms</span>
                      <textarea
                        value={amendPickupTerms}
                        onChange={(e) => setAmendPickupTerms(e.target.value)}
                        rows={2}
                        className="w-full text-xs p-2 bg-[#F7F5F0] border border-[#E6DED5] rounded-lg"
                      />
                    </label>

                    <label className="block">
                      <span className="text-[10px] font-bold text-[#6E6259] uppercase">Delay & Detention Rules</span>
                      <textarea
                        value={amendDetention}
                        onChange={(e) => setAmendDetention(e.target.value)}
                        rows={2}
                        className="w-full text-xs p-2 bg-[#F7F5F0] border border-[#E6DED5] rounded-lg"
                      />
                    </label>

                    <button
                      type="submit"
                      disabled={actionBusy}
                      className="w-full py-2 bg-[#5A3E2B] text-white text-xs font-bold rounded-lg hover:bg-[#432E20] transition disabled:opacity-50 cursor-pointer"
                    >
                      {actionBusy ? "Creating Amendment..." : `Publish Amendment (Creates v${agreement.version + 1}.0)`}
                    </button>
                  </form>
                )}
              </div>
            </>
          ) : null}
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-[#E6DED5] bg-[#FDFCFB] flex items-center justify-between">
          <span className="text-[10px] text-[#8A796B]">
            Automated Facilitation by LoadLink AI Marketplace Engine
          </span>
          <button
            onClick={onClose}
            className="px-4 py-2 bg-[#F7F5F0] hover:bg-[#EFECE6] border border-[#E6DED5] rounded-lg text-xs font-bold text-[#29231F] transition"
          >
            Close Agreement
          </button>
        </div>
      </div>
    </div>
  );
}
