"use client";

import React, { useState, useEffect, useCallback } from "react";
import {
  X,
  Shield,
  ShieldCheck,
  ShieldAlert,
  AlertTriangle,
  CheckCircle2,
  FileText,
  Clock,
  IndianRupee,
  Upload,
  Check,
  Ban,
  Building,
  Info,
  Layers,
} from "lucide-react";
import { CargoInsurance, InsurancePolicyRule } from "@/types";
import { api } from "@/lib/api";

interface InsuranceModalProps {
  isOpen: boolean;
  onClose: () => void;
  targetId: string; // bookingId, shipmentId, or loadId
  currentUser?: any;
  onStatusUpdated?: () => void;
}

const fmt = (n: number) =>
  new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  }).format(n || 0);

export default function InsuranceModal({
  isOpen,
  onClose,
  targetId,
  currentUser,
  onStatusUpdated,
}: InsuranceModalProps) {
  const [activeTab, setActiveTab] = useState<"status" | "upload" | "verify" | "policies">("status");
  const [insurance, setInsurance] = useState<CargoInsurance | null>(null);
  const [policies, setPolicies] = useState<InsurancePolicyRule[]>([]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState("");
  const [successMsg, setSuccessMsg] = useState("");

  // Upload Form State
  const [policyNum, setPolicyNum] = useState("");
  const [insurerName, setInsurerName] = useState("National Insurance Co Ltd");
  const [policyholder, setPolicyholder] = useState("");
  const [insuredParty, setInsuredParty] = useState("");
  const [coverageAmt, setCoverageAmt] = useState<number>(1000000);
  const [validFrom, setValidFrom] = useState("");
  const [validTo, setValidTo] = useState("");
  const [exclusions, setExclusions] = useState("Loss arising from war, nuclear hazard, or willful misconduct.");
  const [certUrl, setCertUrl] = useState("/uploads/insurance_transit_policy.pdf");

  // Verify Form State
  const [verifyAction, setVerifyAction] = useState<"VERIFY" | "APPROVE_EXCEPTION" | "REJECT">("VERIFY");
  const [verifyNotes, setVerifyNotes] = useState("");

  const isComplianceOfficer =
    currentUser?.role === "COMPLIANCE_OFFICER" || currentUser?.role === "ADMIN";

  const loadData = useCallback(async () => {
    if (!targetId) return;
    setLoading(true);
    setErrorMsg("");
    try {
      const insData = await api.getCargoInsurance(targetId);
      setInsurance(insData);
      if (insData) {
        setPolicyNum(insData.policy_number || "");
        setInsurerName(insData.insurer_name || "National Insurance Co Ltd");
        setPolicyholder(insData.policyholder_name || "");
        setInsuredParty(insData.insured_party || "");
        setCoverageAmt(insData.coverage_amount_inr || 1000000);
      }
      const polData = await api.listInsurancePolicies();
      setPolicies(polData);
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to load insurance data");
    } finally {
      setLoading(false);
    }
  }, [targetId]);

  useEffect(() => {
    if (isOpen) {
      loadData();
      setErrorMsg("");
      setSuccessMsg("");
    }
  }, [isOpen, loadData]);

  const handleUploadPolicy = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!policyNum) {
      setErrorMsg("Policy number is required.");
      return;
    }
    setSubmitting(true);
    setErrorMsg("");
    setSuccessMsg("");
    try {
      await api.uploadCargoInsurance(targetId, {
        policy_number: policyNum,
        insurer_name: insurerName,
        policyholder_name: policyholder || "Commercial Consignor",
        insured_party: insuredParty || "Cargo Owner & Carrier",
        coverage_amount_inr: coverageAmt,
        valid_from: validFrom ? new Date(validFrom).toISOString() : new Date().toISOString(),
        valid_to: validTo ? new Date(validTo).toISOString() : new Date(Date.now() + 30 * 86400000).toISOString(),
        exclusions,
        certificate_url: certUrl,
      });
      setSuccessMsg("Insurance certificate uploaded. Enters PENDING_VERIFICATION queue for Compliance Officer review.");
      await loadData();
      setActiveTab("status");
      onStatusUpdated?.();
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to upload insurance policy");
    } finally {
      setSubmitting(false);
    }
  };

  const handleVerifyPolicy = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!insurance) return;
    setSubmitting(true);
    setErrorMsg("");
    setSuccessMsg("");
    try {
      await api.verifyCargoInsurance(insurance.id, {
        action: verifyAction,
        rejection_reason: verifyAction === "REJECT" ? verifyNotes : undefined,
        exception_reason: verifyAction === "APPROVE_EXCEPTION" ? verifyNotes : undefined,
      });
      setSuccessMsg(`Insurance policy updated to: ${verifyAction}`);
      await loadData();
      setActiveTab("status");
      onStatusUpdated?.();
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to verify insurance policy");
    } finally {
      setSubmitting(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-fade-in">
      <div className="relative w-full max-w-3xl bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className="flex items-center justify-between p-5 border-b border-slate-800 bg-slate-900/90 sticky top-0 z-10">
          <div className="flex items-center gap-3">
            <div className="p-2.5 bg-indigo-500/10 border border-indigo-500/20 rounded-xl text-indigo-400">
              <Shield className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-lg font-semibold text-white">Risk-Based Cargo Insurance</h2>
                <span className="text-xs px-2 py-0.5 rounded-full bg-slate-800 text-slate-300 font-mono">
                  {targetId.slice(0, 8)}...
                </span>
              </div>
              <p className="text-xs text-slate-400">
                Configurable underwriting policy, compliance dispatch gates, and policy verification
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 text-slate-400 hover:text-white rounded-lg hover:bg-slate-800 transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Tab Navigation */}
        <div className="flex border-b border-slate-800 bg-slate-950/40 px-5 pt-2 gap-2 text-sm">
          <button
            onClick={() => setActiveTab("status")}
            className={`pb-3 px-3 font-medium transition border-b-2 flex items-center gap-2 ${
              activeTab === "status"
                ? "border-indigo-500 text-indigo-400"
                : "border-transparent text-slate-400 hover:text-slate-200"
            }`}
          >
            <ShieldCheck className="w-4 h-4" /> Assessment & Dispatch Gate
          </button>
          <button
            onClick={() => setActiveTab("upload")}
            className={`pb-3 px-3 font-medium transition border-b-2 flex items-center gap-2 ${
              activeTab === "upload"
                ? "border-indigo-500 text-indigo-400"
                : "border-transparent text-slate-400 hover:text-slate-200"
            }`}
          >
            <Upload className="w-4 h-4" /> Upload Policy
          </button>
          {isComplianceOfficer && (
            <button
              onClick={() => setActiveTab("verify")}
              className={`pb-3 px-3 font-medium transition border-b-2 flex items-center gap-2 ${
                activeTab === "verify"
                  ? "border-emerald-500 text-emerald-400"
                  : "border-transparent text-slate-400 hover:text-slate-200"
              }`}
            >
              <Check className="w-4 h-4" /> Compliance Officer Review
            </button>
          )}
          <button
            onClick={() => setActiveTab("policies")}
            className={`pb-3 px-3 font-medium transition border-b-2 flex items-center gap-2 ${
              activeTab === "policies"
                ? "border-indigo-500 text-indigo-400"
                : "border-transparent text-slate-400 hover:text-slate-200"
            }`}
          >
            <Layers className="w-4 h-4" /> Approved Rules (v{policies[0]?.version || 1})
          </button>
        </div>

        {/* Modal Body */}
        <div className="p-6 overflow-y-auto space-y-4 flex-1">
          {errorMsg && (
            <div className="p-3 bg-red-500/10 border border-red-500/20 rounded-xl text-red-400 text-sm flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 shrink-0" />
              <span>{errorMsg}</span>
            </div>
          )}
          {successMsg && (
            <div className="p-3 bg-emerald-500/10 border border-emerald-500/20 rounded-xl text-emerald-400 text-sm flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 shrink-0" />
              <span>{successMsg}</span>
            </div>
          )}

          {/* TAB 1: STATUS & DISPATCH GATE */}
          {activeTab === "status" && (
            <div className="space-y-4">
              {loading ? (
                <div className="py-12 text-center text-slate-400">Loading risk assessment...</div>
              ) : !insurance ? (
                <div className="py-10 text-center border border-dashed border-slate-800 rounded-xl p-8">
                  <ShieldAlert className="w-8 h-8 text-slate-600 mx-auto mb-2" />
                  <p className="text-slate-300 font-medium">No insurance record assessed for this shipment</p>
                  <p className="text-xs text-slate-500 mt-1">Upload policy details to initiate underwriting clearance.</p>
                </div>
              ) : (
                <div className="space-y-4">
                  {/* Gate Alert Box */}
                  <div
                    className={`p-4 rounded-xl border flex items-start justify-between gap-3 ${
                      insurance.is_dispatch_allowed
                        ? "bg-emerald-500/10 border-emerald-500/20 text-emerald-300"
                        : "bg-red-500/10 border-red-500/20 text-red-300"
                    }`}
                  >
                    <div className="flex items-start gap-3">
                      {insurance.is_dispatch_allowed ? (
                        <CheckCircle2 className="w-5 h-5 text-emerald-400 shrink-0 mt-0.5" />
                      ) : (
                        <ShieldAlert className="w-5 h-5 text-red-400 shrink-0 mt-0.5" />
                      )}
                      <div>
                        <h4 className="font-semibold text-sm">
                          {insurance.is_dispatch_allowed
                            ? "Dispatch Cleared — Highway Transit Permitted"
                            : "Dispatch Blocked — Mandatory Insurance Verification Required"}
                        </h4>
                        <p className="text-xs mt-0.5 opacity-90">
                          {insurance.is_dispatch_allowed
                            ? "Consignment conforms to Bengal Corridor Insurance policy underwriting requirements."
                            : "Vehicle departure blocked at gate until policy is verified by Compliance Officer or an authorized executive exception is granted."}
                        </p>
                      </div>
                    </div>
                    <span
                      className={`text-xs px-2.5 py-1 rounded-full font-bold uppercase shrink-0 ${
                        insurance.is_dispatch_allowed
                          ? "bg-emerald-500/20 text-emerald-400"
                          : "bg-red-500/20 text-red-400"
                      }`}
                    >
                      {insurance.verification_status}
                    </span>
                  </div>

                  {/* Assessment Breakdown */}
                  <div className="bg-slate-950/60 border border-slate-800 rounded-xl p-4 space-y-3">
                    <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
                      Risk Assessment Assessment
                    </h4>
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-slate-300">Underwriting Determination:</span>
                      <span
                        className={`text-xs px-2.5 py-1 rounded-lg font-bold ${
                          insurance.assessment_result === "REQUIRED"
                            ? "bg-amber-500/10 text-amber-400 border border-amber-500/20"
                            : insurance.assessment_result === "REVIEW_REQUIRED"
                            ? "bg-red-500/10 text-red-400 border border-red-500/20"
                            : "bg-slate-800 text-slate-300"
                        }`}
                      >
                        {insurance.assessment_result}
                      </span>
                    </div>

                    {insurance.assessment_reasons && insurance.assessment_reasons.length > 0 && (
                      <div className="space-y-1.5 pt-1">
                        <span className="text-xs text-slate-500 block">Assessment Drivers:</span>
                        {insurance.assessment_reasons.map((r, i) => (
                          <div key={i} className="text-xs text-slate-300 bg-slate-900 p-2 rounded-lg flex items-start gap-2">
                            <Info className="w-3.5 h-3.5 text-indigo-400 shrink-0 mt-0.5" />
                            <span>{r}</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>

                  {/* Policy Certificate Information */}
                  {insurance.policy_number && (
                    <div className="bg-slate-950/60 border border-slate-800 rounded-xl p-4 space-y-3">
                      <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
                        Active Policy Details
                      </h4>
                      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
                        <div className="bg-slate-900 p-2.5 rounded-lg">
                          <span className="text-slate-500 block">Policy Number</span>
                          <span className="font-mono text-slate-200 font-semibold">{insurance.policy_number}</span>
                        </div>
                        <div className="bg-slate-900 p-2.5 rounded-lg">
                          <span className="text-slate-500 block">Insurer</span>
                          <span className="text-slate-200">{insurance.insurer_name}</span>
                        </div>
                        <div className="bg-slate-900 p-2.5 rounded-lg">
                          <span className="text-slate-500 block">Coverage Amount</span>
                          <span className="font-semibold text-emerald-400">{fmt(insurance.coverage_amount_inr)}</span>
                        </div>
                        <div className="bg-slate-900 p-2.5 rounded-lg">
                          <span className="text-slate-500 block">Valid Until</span>
                          <span className="text-slate-200">
                            {insurance.valid_to ? new Date(insurance.valid_to).toLocaleDateString("en-IN") : "Indefinite"}
                          </span>
                        </div>
                      </div>

                      {insurance.verified_by_name && (
                        <div className="p-2.5 bg-slate-900 rounded-lg text-xs flex items-center justify-between text-slate-400">
                          <span>Verified By: <strong className="text-slate-200">{insurance.verified_by_name}</strong></span>
                          <span>Timestamp: {insurance.verified_at ? new Date(insurance.verified_at).toLocaleString("en-IN") : "N/A"}</span>
                        </div>
                      )}

                      {insurance.exception_reason && (
                        <div className="p-2.5 bg-indigo-500/10 border border-indigo-500/20 rounded-lg text-xs text-indigo-300">
                          <strong>Approved Exception:</strong> {insurance.exception_reason}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {/* TAB 2: UPLOAD POLICY */}
          {activeTab === "upload" && (
            <form onSubmit={handleUploadPolicy} className="space-y-4">
              <div className="p-3 bg-indigo-500/10 border border-indigo-500/20 rounded-xl text-xs text-indigo-300 flex items-start gap-2">
                <Info className="w-4 h-4 shrink-0 mt-0.5" />
                <span>
                  <strong>Legal Notice:</strong> An uploaded certificate enters{" "}
                  <code>PENDING_VERIFICATION</code>. LoadLink does not automatically verify policies. A certified Compliance Officer must review the certificate before vehicle departure.
                </span>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-slate-300 mb-1">Policy Number *</label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. NIC-CARGO-2026-9901"
                    value={policyNum}
                    onChange={(e) => setPolicyNum(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-indigo-500"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-300 mb-1">Insurer Name *</label>
                  <input
                    type="text"
                    required
                    value={insurerName}
                    onChange={(e) => setInsurerName(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-indigo-500"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <div>
                  <label className="block text-xs font-medium text-slate-300 mb-1">Policyholder</label>
                  <input
                    type="text"
                    placeholder="Shipper or Transporter"
                    value={policyholder}
                    onChange={(e) => setPolicyholder(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-indigo-500"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-300 mb-1">Insured Party</label>
                  <input
                    type="text"
                    placeholder="Consignor / Consignee"
                    value={insuredParty}
                    onChange={(e) => setInsuredParty(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-indigo-500"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-300 mb-1">Coverage Amount (INR)</label>
                  <input
                    type="number"
                    value={coverageAmt}
                    onChange={(e) => setCoverageAmt(parseFloat(e.target.value) || 0)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-indigo-500"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-slate-300 mb-1">Policy Valid From</label>
                  <input
                    type="date"
                    value={validFrom}
                    onChange={(e) => setValidFrom(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-indigo-500"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-300 mb-1">Policy Valid To *</label>
                  <input
                    type="date"
                    value={validTo}
                    onChange={(e) => setValidTo(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-indigo-500"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">Standard Exclusions</label>
                <textarea
                  rows={2}
                  value={exclusions}
                  onChange={(e) => setExclusions(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-indigo-500"
                />
              </div>

              <button
                type="submit"
                disabled={submitting}
                className="w-full py-2.5 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white rounded-xl font-medium transition text-sm flex items-center justify-center gap-2"
              >
                <Upload className="w-4 h-4" />
                {submitting ? "Uploading Policy..." : "Submit Policy for Compliance Review"}
              </button>
            </form>
          )}

          {/* TAB 3: COMPLIANCE OFFICER REVIEW */}
          {activeTab === "verify" && isComplianceOfficer && (
            <form onSubmit={handleVerifyPolicy} className="space-y-4">
              <div className="p-3 bg-emerald-500/10 border border-emerald-500/20 rounded-xl text-xs text-emerald-300">
                You are authenticated as <strong>{currentUser?.name || "Compliance Officer"}</strong>. Review policy documentation and authenticate validity.
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-300 mb-2">Adjudication Action</label>
                <div className="grid grid-cols-3 gap-3">
                  <button
                    type="button"
                    onClick={() => setVerifyAction("VERIFY")}
                    className={`p-3 rounded-xl border text-center transition ${
                      verifyAction === "VERIFY"
                        ? "bg-emerald-500/20 border-emerald-500 text-emerald-300"
                        : "bg-slate-950 border-slate-800 text-slate-400"
                    }`}
                  >
                    <CheckCircle2 className="w-5 h-5 mx-auto mb-1 text-emerald-400" />
                    <span className="text-xs font-semibold block">Verify & Clear</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => setVerifyAction("APPROVE_EXCEPTION")}
                    className={`p-3 rounded-xl border text-center transition ${
                      verifyAction === "APPROVE_EXCEPTION"
                        ? "bg-indigo-500/20 border-indigo-500 text-indigo-300"
                        : "bg-slate-950 border-slate-800 text-slate-400"
                    }`}
                  >
                    <Shield className="w-5 h-5 mx-auto mb-1 text-indigo-400" />
                    <span className="text-xs font-semibold block">Approve Exception</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => setVerifyAction("REJECT")}
                    className={`p-3 rounded-xl border text-center transition ${
                      verifyAction === "REJECT"
                        ? "bg-red-500/20 border-red-500 text-red-300"
                        : "bg-slate-950 border-slate-800 text-slate-400"
                    }`}
                  >
                    <Ban className="w-5 h-5 mx-auto mb-1 text-red-400" />
                    <span className="text-xs font-semibold block">Reject Policy</span>
                  </button>
                </div>
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">
                  Compliance Officer Notes / Waiver Justification
                </label>
                <textarea
                  rows={3}
                  placeholder="Enter verification remarks or approved policy exception justification..."
                  value={verifyNotes}
                  onChange={(e) => setVerifyNotes(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-emerald-500"
                />
              </div>

              <button
                type="submit"
                disabled={submitting}
                className="w-full py-2.5 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white rounded-xl font-medium transition text-sm flex items-center justify-center gap-2"
              >
                <Check className="w-4 h-4" />
                {submitting ? "Applying Review..." : `Confirm ${verifyAction.replace(/_/g, " ")}`}
              </button>
            </form>
          )}

          {/* TAB 4: APPROVED POLICIES */}
          {activeTab === "policies" && (
            <div className="space-y-3">
              <p className="text-xs text-slate-400">
                Current underwriting thresholds configured by corridor compliance administration:
              </p>
              {policies.map((p) => (
                <div
                  key={p.id}
                  className={`p-4 rounded-xl border ${
                    p.is_active ? "bg-slate-950/80 border-indigo-500/40" : "bg-slate-950/40 border-slate-800 opacity-60"
                  }`}
                >
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm font-semibold text-white flex items-center gap-2">
                      {p.policy_name}
                      {p.is_active && (
                        <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-400 font-bold">
                          ACTIVE (v{p.version})
                        </span>
                      )}
                    </span>
                    <span className="text-xs text-slate-500 font-mono">
                      {new Date(p.created_at).toLocaleDateString("en-IN")}
                    </span>
                  </div>
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs">
                    <div className="bg-slate-900 p-2 rounded-lg">
                      <span className="text-slate-500 block">Max Uninsured Value</span>
                      <span className="font-semibold text-slate-200">{fmt(p.max_uninsured_value_inr)}</span>
                    </div>
                    <div className="bg-slate-900 p-2 rounded-lg">
                      <span className="text-slate-500 block">Review Threshold</span>
                      <span className="font-semibold text-amber-400">{fmt(p.review_threshold_inr)}</span>
                    </div>
                    <div className="bg-slate-900 p-2 rounded-lg">
                      <span className="text-slate-500 block">Hazardous Mandatory</span>
                      <span className="font-semibold text-slate-200">{p.hazardous_requires_insurance ? "YES" : "NO"}</span>
                    </div>
                    <div className="bg-slate-900 p-2 rounded-lg">
                      <span className="text-slate-500 block">High Fragility Mandate</span>
                      <span className="font-semibold text-slate-200">{p.fragile_high_requires_insurance ? "YES" : "NO"}</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
