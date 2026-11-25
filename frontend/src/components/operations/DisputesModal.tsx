"use client";

import React, { useState, useEffect, useCallback } from "react";
import {
  X,
  AlertTriangle,
  FileText,
  Send,
  Upload,
  CheckCircle2,
  Clock,
  User,
  ShieldAlert,
  Bot,
  Brain,
  Check,
  ChevronRight,
  MessageSquare,
  AlertCircle,
  HelpCircle,
  IndianRupee,
} from "lucide-react";
import { DisputeCase, Grievance, DisputeCategory, DisputeStatus } from "@/types";
import { api } from "@/lib/api";

interface DisputesModalProps {
  isOpen: boolean;
  onClose: () => void;
  bookingId?: string;
  shipmentId?: string;
  currentUser?: any;
  onStatusUpdated?: () => void;
}

const fmt = (n: number) =>
  new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  }).format(n || 0);

const DISPUTE_CATEGORIES: { value: DisputeCategory; label: string }[] = [
  { value: "CARGO_DAMAGE", label: "Cargo Damage during Highway Transit" },
  { value: "CARGO_SHORTAGE", label: "Cargo Shortage / Quantity Mismatch" },
  { value: "NON_DELIVERY", label: "Non-Delivery of Consignment" },
  { value: "DELIVERY_REFUSAL", label: "Consignee Delivery Refusal" },
  { value: "UNAUTHORIZED_CANCELLATION", label: "Unauthorized Post-Dispatch Cancellation" },
  { value: "PAYMENT_DEFAULT", label: "Direct Freight Payment Default" },
  { value: "FREIGHT_AMOUNT_DISPUTE", label: "Freight Amount Discrepancy" },
  { value: "UNREASONABLE_TRANSIT_DELAY", label: "Unreasonable Corridor Transit Delay" },
  { value: "ADDITIONAL_CHARGES_DETENTION", label: "Detention / Unloading Delay Charges" },
  { value: "DRIVER_TRANSPORTER_MISCONDUCT", label: "Driver or Transporter Misconduct" },
  { value: "DOCUMENTATION_DISCREPANCY", label: "Documentation or E-Way Bill Discrepancy" },
];

export default function DisputesModal({
  isOpen,
  onClose,
  bookingId,
  shipmentId,
  currentUser,
  onStatusUpdated,
}: DisputesModalProps) {
  const [activeTab, setActiveTab] = useState<"cases" | "file_dispute" | "grievances">("cases");
  const [disputes, setDisputes] = useState<DisputeCase[]>([]);
  const [selectedDispute, setSelectedDispute] = useState<DisputeCase | null>(null);
  const [grievances, setGrievances] = useState<Grievance[]>([]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState("");
  const [successMsg, setSuccessMsg] = useState("");

  // New Dispute Form
  const [newCat, setNewCat] = useState<DisputeCategory>("CARGO_DAMAGE");
  const [newTitle, setNewTitle] = useState("");
  const [newDesc, setNewDesc] = useState("");
  const [newAmount, setNewAmount] = useState<number>(0);
  const [newEvidenceUrl, setNewEvidenceUrl] = useState("/uploads/dispute_evidence_1.pdf");

  // Chat message in dispute
  const [chatMsg, setChatMsg] = useState("");

  // New Grievance Form
  const [grvSubject, setGrvSubject] = useState("");
  const [grvDesc, setGrvDesc] = useState("");
  const [grvCategory, setGrvCategory] = useState("OPERATIONAL_GRIEVANCE");

  const isDisputeOfficer =
    currentUser?.role === "DISPUTE_OFFICER" || currentUser?.role === "ADMIN";

  const loadAll = useCallback(async () => {
    setLoading(true);
    setErrorMsg("");
    try {
      const dList = await api.listDisputeCases();
      setDisputes(dList);
      if (dList.length > 0 && !selectedDispute) {
        setSelectedDispute(dList[0]);
      } else if (selectedDispute) {
        const refreshed = dList.find((d) => d.id === selectedDispute.id);
        if (refreshed) setSelectedDispute(refreshed);
      }
      const gList = await api.listGrievances();
      setGrievances(gList);
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to load disputes");
    } finally {
      setLoading(false);
    }
  }, [selectedDispute]);

  useEffect(() => {
    if (isOpen) {
      loadAll();
      setErrorMsg("");
      setSuccessMsg("");
    }
  }, [isOpen, loadAll]);

  const handleCreateDispute = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTitle || !newDesc) {
      setErrorMsg("Title and description are required.");
      return;
    }
    setSubmitting(true);
    setErrorMsg("");
    setSuccessMsg("");
    try {
      const created = await api.createDisputeCase({
        booking_id: bookingId,
        shipment_id: shipmentId,
        category: newCat,
        title: newTitle,
        description: newDesc,
        disputed_amount_inr: newAmount,
        evidence_urls: newEvidenceUrl ? [newEvidenceUrl] : [],
      });
      setSuccessMsg(`Dispute case ${created.case_number} registered! AI triage initiated.`);
      await loadAll();
      setSelectedDispute(created);
      setActiveTab("cases");
      setNewTitle("");
      setNewDesc("");
      onStatusUpdated?.();
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to create dispute case");
    } finally {
      setSubmitting(false);
    }
  };

  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!chatMsg || !selectedDispute) return;
    try {
      await api.postDisputeMessage(selectedDispute.id, {
        message: chatMsg,
        is_officer_internal_note: false,
      });
      setChatMsg("");
      await loadAll();
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to post message");
    }
  };

  const handleCreateGrievance = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!grvSubject || !grvDesc) {
      setErrorMsg("Subject and description are required.");
      return;
    }
    setSubmitting(true);
    setErrorMsg("");
    setSuccessMsg("");
    try {
      const grv = await api.createGrievance({
        subject: grvSubject,
        description: grvDesc,
        category: grvCategory,
      });
      setSuccessMsg(`Grievance ticket ${grv.ticket_number} created with 3-day SLA response target.`);
      setGrvSubject("");
      setGrvDesc("");
      await loadAll();
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to file grievance");
    } finally {
      setSubmitting(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-fade-in">
      <div className="relative w-full max-w-4xl bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[92vh]">
        {/* Header */}
        <div className="flex items-center justify-between p-5 border-b border-slate-800 bg-slate-900/90 sticky top-0 z-10">
          <div className="flex items-center gap-3">
            <div className="p-2.5 bg-amber-500/10 border border-amber-500/20 rounded-xl text-amber-400">
              <ShieldAlert className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-lg font-semibold text-white">Dispute Adjudication & Grievance Resolution</h2>
                <span className="text-xs px-2 py-0.5 rounded-full bg-slate-800 text-slate-300 font-mono">
                  {disputes.length} Cases Open
                </span>
              </div>
              <p className="text-xs text-slate-400">
                11 claim categories, evidence logs, SLA timestamps, and AI-assisted triage
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
            onClick={() => setActiveTab("cases")}
            className={`pb-3 px-3 font-medium transition border-b-2 flex items-center gap-2 ${
              activeTab === "cases"
                ? "border-amber-500 text-amber-400"
                : "border-transparent text-slate-400 hover:text-slate-200"
            }`}
          >
            <ShieldAlert className="w-4 h-4" /> Active Dispute Cases ({disputes.length})
          </button>
          <button
            onClick={() => setActiveTab("file_dispute")}
            className={`pb-3 px-3 font-medium transition border-b-2 flex items-center gap-2 ${
              activeTab === "file_dispute"
                ? "border-amber-500 text-amber-400"
                : "border-transparent text-slate-400 hover:text-slate-200"
            }`}
          >
            <AlertTriangle className="w-4 h-4" /> Open New Dispute Case
          </button>
          <button
            onClick={() => setActiveTab("grievances")}
            className={`pb-3 px-3 font-medium transition border-b-2 flex items-center gap-2 ${
              activeTab === "grievances"
                ? "border-blue-500 text-blue-400"
                : "border-transparent text-slate-400 hover:text-slate-200"
            }`}
          >
            <HelpCircle className="w-4 h-4" /> Platform Grievance Desk ({grievances.length})
          </button>
        </div>

        {/* Body */}
        <div className="p-6 overflow-y-auto space-y-4 flex-1">
          {errorMsg && (
            <div className="p-3 bg-red-500/10 border border-red-500/20 rounded-xl text-red-400 text-sm flex items-center gap-2">
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span>{errorMsg}</span>
            </div>
          )}
          {successMsg && (
            <div className="p-3 bg-emerald-500/10 border border-emerald-500/20 rounded-xl text-emerald-400 text-sm flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 shrink-0" />
              <span>{successMsg}</span>
            </div>
          )}

          {/* TAB 1: CASES LIST & DETAIL VIEWER */}
          {activeTab === "cases" && (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 min-h-[420px]">
              {/* Cases List Sidebar */}
              <div className="md:col-span-1 border-r border-slate-800 pr-3 space-y-2 max-h-[500px] overflow-y-auto">
                <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider block mb-2">
                  Registered Claims
                </span>
                {loading ? (
                  <div className="text-xs text-slate-500 text-center py-8">Loading cases...</div>
                ) : disputes.length === 0 ? (
                  <div className="text-xs text-slate-500 text-center py-8 border border-dashed border-slate-800 rounded-lg p-4">
                    No active disputes filed for this corridor.
                  </div>
                ) : (
                  disputes.map((d) => (
                    <button
                      key={d.id}
                      onClick={() => setSelectedDispute(d)}
                      className={`w-full text-left p-3 rounded-xl border transition text-xs space-y-1 block ${
                        selectedDispute?.id === d.id
                          ? "bg-amber-500/10 border-amber-500/40 text-amber-200"
                          : "bg-slate-950/60 border-slate-800 text-slate-300 hover:border-slate-700"
                      }`}
                    >
                      <div className="flex items-center justify-between font-mono font-semibold">
                        <span>{d.case_number}</span>
                        <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-900 border border-slate-800">
                          {d.status}
                        </span>
                      </div>
                      <p className="font-medium text-slate-200 truncate">{d.title}</p>
                      <div className="flex justify-between text-slate-500 text-[11px]">
                        <span>{d.category.replace(/_/g, " ")}</span>
                        {d.disputed_amount_inr ? <span>{fmt(d.disputed_amount_inr)}</span> : null}
                      </div>
                    </button>
                  ))
                )}
              </div>

              {/* Case Details Pane */}
              <div className="md:col-span-2 pl-1 space-y-4">
                {selectedDispute ? (
                  <div className="space-y-4">
                    {/* Top Case Meta */}
                    <div className="flex items-start justify-between border-b border-slate-800 pb-3">
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="text-base font-bold text-white font-mono">{selectedDispute.case_number}</span>
                          <span className="text-xs px-2.5 py-0.5 rounded-full bg-amber-500/10 border border-amber-500/20 text-amber-400 font-bold uppercase">
                            {selectedDispute.status}
                          </span>
                        </div>
                        <h3 className="text-sm font-semibold text-slate-200 mt-1">{selectedDispute.title}</h3>
                      </div>
                      {selectedDispute.disputed_amount_inr ? (
                        <div className="text-right">
                          <span className="text-[10px] text-slate-500 block uppercase">Disputed Value</span>
                          <span className="text-base font-bold text-amber-400">{fmt(selectedDispute.disputed_amount_inr)}</span>
                        </div>
                      ) : null}
                    </div>

                    {/* AI Assisted Triage Advisory */}
                    {selectedDispute.ai_classification && (
                      <div className="p-3.5 bg-slate-950 border border-indigo-500/30 rounded-xl space-y-2 text-xs">
                        <div className="flex items-center justify-between text-indigo-400 font-semibold">
                          <span className="flex items-center gap-1.5">
                            <Bot className="w-4 h-4" /> AI Triage Assessment ({selectedDispute.ai_classification.ai_triage_model || "LoadLink-Triage-v2"})
                          </span>
                          <span className="text-[10px] px-2 py-0.5 rounded bg-indigo-500/20 text-indigo-300 font-bold uppercase">
                            Urgency: {selectedDispute.ai_classification.urgency || "MEDIUM"}
                          </span>
                        </div>
                        <p className="text-slate-300 text-[11px]">
                          <strong>Recommended Audit Focus:</strong> {selectedDispute.ai_classification.recommended_focus || "Standard operational review"}
                        </p>
                        <div className="pt-1 flex items-center justify-between text-[10px] text-slate-400 border-t border-slate-800">
                          <span>Priority Score: {selectedDispute.ai_classification.priority_score || 50}/100</span>
                          <span className="text-amber-400 font-semibold">
                            Human Officer Review Required — No Auto-Deduction
                          </span>
                        </div>
                      </div>
                    )}

                    {/* Description */}
                    <div className="bg-slate-950/60 border border-slate-800 rounded-xl p-3 text-xs space-y-1">
                      <span className="text-slate-500 block">Statement of Facts:</span>
                      <p className="text-slate-200 leading-relaxed">{selectedDispute.description}</p>
                    </div>

                    {/* Evidence Files */}
                    {selectedDispute.evidence && selectedDispute.evidence.length > 0 && (
                      <div className="space-y-1.5 text-xs">
                        <span className="text-slate-500 block font-semibold">Submitted Evidence ({selectedDispute.evidence.length})</span>
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                          {selectedDispute.evidence.map((ev) => (
                            <div key={ev.id} className="p-2 bg-slate-950 border border-slate-800 rounded-lg flex items-center justify-between">
                              <div className="truncate pr-2">
                                <span className="font-medium text-slate-200 block truncate">{ev.title}</span>
                                <span className="text-[10px] text-slate-500">{ev.evidence_type}</span>
                              </div>
                              <span className="text-[10px] text-indigo-400 font-mono">Verified File</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Resolution Proposal */}
                    {selectedDispute.resolution_proposal && (
                      <div className="p-3 bg-emerald-500/10 border border-emerald-500/20 rounded-xl text-xs space-y-2">
                        <div className="flex items-center justify-between">
                          <strong className="text-emerald-300">Proposed Officer Resolution:</strong>
                          <span className="text-[10px] text-slate-400">
                            Officer: {selectedDispute.assigned_officer_name || "Dispute Officer"}
                          </span>
                        </div>
                        <p className="text-slate-200">{selectedDispute.resolution_proposal}</p>
                      </div>
                    )}

                    {/* Message Thread */}
                    <div className="bg-slate-950 border border-slate-800 rounded-xl p-3 space-y-3 text-xs">
                      <span className="font-semibold text-slate-400 block">Case Message Thread</span>
                      <div className="space-y-2 max-h-[160px] overflow-y-auto">
                        {selectedDispute.messages && selectedDispute.messages.length > 0 ? (
                          selectedDispute.messages.map((m) => (
                            <div key={m.id} className="p-2 bg-slate-900 rounded-lg">
                              <div className="flex justify-between text-[10px] text-slate-500 mb-1">
                                <strong className="text-slate-300">{m.sender_name || "Participant"} ({m.sender_role || "User"})</strong>
                                <span>{new Date(m.created_at).toLocaleTimeString("en-IN")}</span>
                              </div>
                              <p className="text-slate-200">{m.message}</p>
                            </div>
                          ))
                        ) : (
                          <div className="text-slate-500 text-center py-3 italic">No messages posted yet.</div>
                        )}
                      </div>

                      <form onSubmit={handleSendMessage} className="flex gap-2 pt-2 border-t border-slate-800">
                        <input
                          type="text"
                          placeholder="Post a response or document note..."
                          value={chatMsg}
                          onChange={(e) => setChatMsg(e.target.value)}
                          className="flex-1 bg-slate-900 border border-slate-800 rounded-lg px-3 py-1.5 text-xs text-white focus:outline-none focus:border-amber-500"
                        />
                        <button
                          type="submit"
                          className="px-3 py-1.5 bg-amber-600 hover:bg-amber-500 text-white rounded-lg text-xs font-medium transition"
                        >
                          <Send className="w-3.5 h-3.5" />
                        </button>
                      </form>
                    </div>
                  </div>
                ) : (
                  <div className="py-24 text-center text-slate-500 text-xs">
                    Select a dispute case to inspect evidence, messages, and resolution options.
                  </div>
                )}
              </div>
            </div>
          )}

          {/* TAB 2: FILE NEW DISPUTE FORM */}
          {activeTab === "file_dispute" && (
            <form onSubmit={handleCreateDispute} className="space-y-4">
              <div className="p-3 bg-amber-500/10 border border-amber-500/20 rounded-xl text-xs text-amber-300">
                File a dispute case for consignment damage, detention charges, or payment discrepancy. Case ID (DSP-XXXX) is generated automatically.
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">Dispute Category *</label>
                <select
                  value={newCat}
                  onChange={(e) => setNewCat(e.target.value as DisputeCategory)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-amber-500"
                >
                  {DISPUTE_CATEGORIES.map((c) => (
                    <option key={c.value} value={c.value}>
                      {c.label}
                    </option>
                  ))}
                </select>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-slate-300 mb-1">Claim Subject / Title *</label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. Broken packaging and cargo spillage on NH19"
                    value={newTitle}
                    onChange={(e) => setNewTitle(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-amber-500"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-300 mb-1">Disputed Amount (INR)</label>
                  <input
                    type="number"
                    value={newAmount}
                    onChange={(e) => setNewAmount(parseFloat(e.target.value) || 0)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-amber-500"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">Detailed Description of Claim *</label>
                <textarea
                  rows={4}
                  required
                  placeholder="Detail the timeline, breach of agreement terms, physical damage observations, or unpaid amounts..."
                  value={newDesc}
                  onChange={(e) => setNewDesc(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-amber-500"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">Initial Evidence Document / Photo URL</label>
                <input
                  type="text"
                  value={newEvidenceUrl}
                  onChange={(e) => setNewEvidenceUrl(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-amber-500"
                />
              </div>

              <button
                type="submit"
                disabled={submitting}
                className="w-full py-2.5 bg-amber-600 hover:bg-amber-500 disabled:opacity-50 text-white rounded-xl font-medium transition text-sm flex items-center justify-center gap-2"
              >
                <AlertTriangle className="w-4 h-4" />
                {submitting ? "Opening Case..." : "Register Dispute Case & Trigger AI Triage"}
              </button>
            </form>
          )}

          {/* TAB 3: GRIEVANCES & 3-DAY SLA */}
          {activeTab === "grievances" && (
            <div className="space-y-4">
              <div className="p-3 bg-blue-500/10 border border-blue-500/20 rounded-xl text-xs text-blue-300 flex items-start gap-2">
                <HelpCircle className="w-4 h-4 shrink-0 mt-0.5" />
                <span>
                  <strong>Statutory Grievance Redressal:</strong> Every platform grievance ticket generates a 3-day statutory SLA target. Dedicated Dispute Officers track and resolve operational escalations.
                </span>
              </div>

              {/* File Grievance Form */}
              <form onSubmit={handleCreateGrievance} className="bg-slate-950/60 border border-slate-800 rounded-xl p-4 space-y-3">
                <h4 className="text-xs font-semibold text-slate-300 uppercase tracking-wider">
                  File Platform Grievance / Operational Escalation
                </h4>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-medium text-slate-400 mb-1">Grievance Subject *</label>
                    <input
                      type="text"
                      required
                      placeholder="e.g. Unresponsive carrier or weighbridge gate delay"
                      value={grvSubject}
                      onChange={(e) => setGrvSubject(e.target.value)}
                      className="w-full bg-slate-900 border border-slate-800 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-slate-400 mb-1">Category</label>
                    <select
                      value={grvCategory}
                      onChange={(e) => setGrvCategory(e.target.value)}
                      className="w-full bg-slate-900 border border-slate-800 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500"
                    >
                      <option value="OPERATIONAL_GRIEVANCE">Operational Transit Issue</option>
                      <option value="BILLING_ESCALATION">Billing or Fee Escalation</option>
                      <option value="COMPLIANCE_CONCERN">Safety or Driver Compliance</option>
                      <option value="TECHNICAL_SUPPORT">Platform System Bug</option>
                    </select>
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-medium text-slate-400 mb-1">Grievance Description *</label>
                  <textarea
                    rows={2}
                    required
                    placeholder="Provide details of the incident or unresolved issue..."
                    value={grvDesc}
                    onChange={(e) => setGrvDesc(e.target.value)}
                    className="w-full bg-slate-900 border border-slate-800 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500"
                  />
                </div>

                <button
                  type="submit"
                  disabled={submitting}
                  className="w-full py-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white rounded-lg text-xs font-semibold transition"
                >
                  {submitting ? "Submitting..." : "Submit Grievance (Generate GRV Ticket)"}
                </button>
              </form>

              {/* Grievance Tickets List */}
              <div className="space-y-2">
                <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider block">
                  Logged Grievance Tickets ({grievances.length})
                </span>
                {grievances.map((g) => (
                  <div key={g.id} className="p-3 bg-slate-950 border border-slate-800 rounded-xl space-y-1.5 text-xs">
                    <div className="flex items-center justify-between">
                      <span className="font-mono font-bold text-white">{g.ticket_number}</span>
                      <span className="text-[10px] px-2 py-0.5 rounded-full bg-blue-500/20 text-blue-300 font-bold uppercase">
                        {g.status}
                      </span>
                    </div>
                    <p className="font-medium text-slate-200">{g.subject}</p>
                    <p className="text-slate-400 text-[11px]">{g.description}</p>
                    <div className="flex items-center justify-between text-[10px] text-slate-500 pt-1 border-t border-slate-900">
                      <span>SLA Due: <strong className="text-amber-400 font-mono">{new Date(g.due_date).toLocaleDateString("en-IN")}</strong></span>
                      <span>Assigned Officer: {g.assigned_officer_name || "Queue Allocation"}</span>
                    </div>
                    {g.resolution_notes && (
                      <div className="p-2 bg-emerald-500/10 border border-emerald-500/20 rounded-lg text-emerald-300 text-[11px] mt-1">
                        <strong>Resolution:</strong> {g.resolution_notes}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
