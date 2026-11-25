"use client";

import React, { useState, useEffect, useCallback } from "react";
import {
  X,
  CreditCard,
  IndianRupee,
  CheckCircle2,
  AlertTriangle,
  Receipt,
  Building,
  ArrowRight,
  Clock,
  ShieldCheck,
  FileText,
  AlertCircle,
  Check,
} from "lucide-react";
import { DirectPayment, PlatformInvoice, PaymentMethod } from "@/types";
import { api } from "@/lib/api";

interface PaymentsModalProps {
  isOpen: boolean;
  onClose: () => void;
  bookingId: string;
  currentUser?: any;
  onStatusUpdated?: () => void;
}

const fmt = (n: number) =>
  new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  }).format(n || 0);

export default function PaymentsModal({
  isOpen,
  onClose,
  bookingId,
  currentUser,
  onStatusUpdated,
}: PaymentsModalProps) {
  const [activeTab, setActiveTab] = useState<"direct" | "invoice">("direct");
  const [payment, setPayment] = useState<DirectPayment | null>(null);
  const [invoice, setInvoice] = useState<PlatformInvoice | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState("");
  const [successMsg, setSuccessMsg] = useState("");

  // Report Payment Form
  const [payAmount, setPayAmount] = useState<number>(0);
  const [payMethod, setPayMethod] = useState<PaymentMethod>("NEFT");
  const [payRef, setPayRef] = useState("");
  const [payEvidence, setPayEvidence] = useState("/uploads/bank_neft_slip.pdf");
  const [payNotes, setPayNotes] = useState("");

  // Transporter Ack Form
  const [transNotes, setTransNotes] = useState("");
  const [disputeReason, setDisputeReason] = useState("");

  const isTransporterOrDriver =
    currentUser?.role === "TRANSPORTER" ||
    currentUser?.role === "DRIVER" ||
    currentUser?.role === "FLEET_MANAGER";

  const loadData = useCallback(async () => {
    if (!bookingId) return;
    setLoading(true);
    setErrorMsg("");
    try {
      const pData = await api.getDirectPayment(bookingId);
      setPayment(pData);
      if (pData) {
        setPayAmount(pData.remaining_balance_inr || pData.agreed_freight_inr || 18000);
      }
      const invData = await api.getPlatformInvoice(bookingId);
      setInvoice(invData);
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to load payment records");
    } finally {
      setLoading(false);
    }
  }, [bookingId]);

  useEffect(() => {
    if (isOpen) {
      loadData();
      setErrorMsg("");
      setSuccessMsg("");
    }
  }, [isOpen, loadData]);

  const handleReportPayment = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!payRef) {
      setErrorMsg("Bank transaction UTR or payment reference is mandatory.");
      return;
    }
    setSubmitting(true);
    setErrorMsg("");
    setSuccessMsg("");
    try {
      await api.reportDirectPayment(bookingId, {
        amount_paid_inr: payAmount,
        payment_method: payMethod,
        payment_reference: payRef,
        payment_evidence_url: payEvidence,
        dealer_notes: payNotes,
      });
      setSuccessMsg("Payment reported successfully. Awaiting transporter bank verification.");
      await loadData();
      onStatusUpdated?.();
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to report payment");
    } finally {
      setSubmitting(false);
    }
  };

  const handleAcknowledgePayment = async (action: "CONFIRM" | "DISPUTE") => {
    if (!payment) return;
    if (action === "DISPUTE" && !disputeReason) {
      setErrorMsg("Please specify the dispute reason before rejecting payment.");
      return;
    }
    setSubmitting(true);
    setErrorMsg("");
    setSuccessMsg("");
    try {
      await api.acknowledgeDirectPayment(payment.id, {
        action,
        transporter_notes: transNotes || (action === "CONFIRM" ? "Payment confirmed received in account." : undefined),
        dispute_reason: action === "DISPUTE" ? disputeReason : undefined,
      });
      setSuccessMsg(
        action === "CONFIRM"
          ? "Payment confirmed! Freight settlement marked complete."
          : "Payment disputed. Notification sent to dealer and dispute team."
      );
      await loadData();
      onStatusUpdated?.();
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to update payment acknowledgment");
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
            <div className="p-2.5 bg-emerald-500/10 border border-emerald-500/20 rounded-xl text-emerald-400">
              <CreditCard className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-lg font-semibold text-white">Direct Freight Payments & Platform Invoices</h2>
                <span className="text-xs px-2 py-0.5 rounded-full bg-slate-800 text-slate-300 font-mono">
                  {bookingId.slice(0, 8)}...
                </span>
              </div>
              <p className="text-xs text-slate-400">
                Dealer-to-transporter direct settlement & separate LoadLink service billing
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
            onClick={() => setActiveTab("direct")}
            className={`pb-3 px-3 font-medium transition border-b-2 flex items-center gap-2 ${
              activeTab === "direct"
                ? "border-emerald-500 text-emerald-400"
                : "border-transparent text-slate-400 hover:text-slate-200"
            }`}
          >
            <IndianRupee className="w-4 h-4" /> 1. Direct Freight Settlement
          </button>
          <button
            onClick={() => setActiveTab("invoice")}
            className={`pb-3 px-3 font-medium transition border-b-2 flex items-center gap-2 ${
              activeTab === "invoice"
                ? "border-blue-500 text-blue-400"
                : "border-transparent text-slate-400 hover:text-slate-200"
            }`}
          >
            <Receipt className="w-4 h-4" /> 2. Separate Platform Invoice
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

          {/* TAB 1: DIRECT FREIGHT SETTLEMENT */}
          {activeTab === "direct" && (
            <div className="space-y-4">
              {/* Architecture Principle Box */}
              <div className="p-3 bg-emerald-500/10 border border-emerald-500/20 rounded-xl text-xs text-emerald-300">
                <strong>Marketplace Architecture:</strong> The Dealer pays the Transporter directly. LoadLink does not hold or pool freight funds. A reported payment does not automatically become confirmed until verified by the payee.
              </div>

              {loading ? (
                <div className="py-12 text-center text-slate-400">Loading freight settlement status...</div>
              ) : (
                <div className="space-y-4">
                  {/* Payment Summary Cards */}
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
                    <div className="bg-slate-950/60 border border-slate-800 p-3 rounded-xl">
                      <span className="text-slate-500 block">Agreed Freight</span>
                      <span className="text-base font-bold text-white">
                        {fmt(payment?.agreed_freight_inr || 0)}
                      </span>
                    </div>
                    <div className="bg-slate-950/60 border border-slate-800 p-3 rounded-xl">
                      <span className="text-slate-500 block">Reported Paid</span>
                      <span className="text-base font-bold text-emerald-400">
                        {fmt(payment?.amount_paid_inr || 0)}
                      </span>
                    </div>
                    <div className="bg-slate-950/60 border border-slate-800 p-3 rounded-xl">
                      <span className="text-slate-500 block">Remaining Balance</span>
                      <span className="text-base font-bold text-amber-400">
                        {fmt(payment?.remaining_balance_inr || 0)}
                      </span>
                    </div>
                    <div className="bg-slate-950/60 border border-slate-800 p-3 rounded-xl">
                      <span className="text-slate-500 block">Settlement State</span>
                      <span className="text-xs font-bold uppercase tracking-wider text-indigo-400 block mt-1">
                        {payment?.payment_status?.replace(/_/g, " ") || "PENDING"}
                      </span>
                    </div>
                  </div>

                  {/* Payment Details if Reported */}
                  {payment?.payment_reference && (
                    <div className="bg-slate-950/60 border border-slate-800 rounded-xl p-4 space-y-2 text-xs">
                      <h4 className="font-semibold text-slate-300">Latest Reported Transfer</h4>
                      <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                        <div>
                          <span className="text-slate-500 block">Method:</span>
                          <span className="font-semibold text-slate-200">{payment.payment_method}</span>
                        </div>
                        <div>
                          <span className="text-slate-500 block">Bank UTR / Ref:</span>
                          <span className="font-mono text-slate-200">{payment.payment_reference}</span>
                        </div>
                        <div>
                          <span className="text-slate-500 block">Reported At:</span>
                          <span className="text-slate-200">
                            {payment.dealer_reported_at ? new Date(payment.dealer_reported_at).toLocaleString("en-IN") : "N/A"}
                          </span>
                        </div>
                      </div>
                      {payment.dealer_notes && (
                        <p className="text-slate-400 italic">Dealer remarks: {payment.dealer_notes}</p>
                      )}
                      {payment.transporter_notes && (
                        <div className="p-2 bg-slate-900 rounded-lg text-emerald-300 mt-2">
                          <strong>Transporter Confirmation:</strong> {payment.transporter_notes}
                        </div>
                      )}
                      {payment.dispute_reason && (
                        <div className="p-2 bg-red-500/10 border border-red-500/20 rounded-lg text-red-300 mt-2">
                          <strong>Payment Disputed:</strong> {payment.dispute_reason}
                        </div>
                      )}
                    </div>
                  )}

                  {/* DEALER FORM: Report Direct Payment */}
                  {payment?.payment_status !== "CONFIRMED_BY_TRANSPORTER" && (
                    <form onSubmit={handleReportPayment} className="bg-slate-950/40 border border-slate-800 rounded-xl p-4 space-y-3">
                      <h4 className="text-xs font-semibold text-slate-300 uppercase tracking-wider flex items-center gap-2">
                        <CreditCard className="w-4 h-4 text-emerald-400" />
                        Report Direct Freight Transfer (Shipper / Dealer)
                      </h4>
                      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                        <div>
                          <label className="block text-xs font-medium text-slate-400 mb-1">Amount Paid (INR) *</label>
                          <input
                            type="number"
                            required
                            value={payAmount}
                            onChange={(e) => setPayAmount(parseFloat(e.target.value) || 0)}
                            className="w-full bg-slate-900 border border-slate-800 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-emerald-500"
                          />
                        </div>
                        <div>
                          <label className="block text-xs font-medium text-slate-400 mb-1">Payment Method</label>
                          <select
                            value={payMethod}
                            onChange={(e) => setPayMethod(e.target.value as PaymentMethod)}
                            className="w-full bg-slate-900 border border-slate-800 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-emerald-500"
                          >
                            <option value="NEFT">NEFT Transfer</option>
                            <option value="RTGS">RTGS Transfer</option>
                            <option value="IMPS">IMPS Instant</option>
                            <option value="UPI">UPI Direct</option>
                            <option value="CHEQUE">Bank Cheque</option>
                          </select>
                        </div>
                        <div>
                          <label className="block text-xs font-medium text-slate-400 mb-1">Bank UTR / Ref Number *</label>
                          <input
                            type="text"
                            required
                            placeholder="e.g. SBIN202611228812"
                            value={payRef}
                            onChange={(e) => setPayRef(e.target.value)}
                            className="w-full bg-slate-900 border border-slate-800 rounded-lg px-3 py-2 text-sm text-white font-mono focus:outline-none focus:border-emerald-500"
                          />
                        </div>
                      </div>

                      <div>
                        <label className="block text-xs font-medium text-slate-400 mb-1">Transfer Notes / Payee Account</label>
                        <input
                          type="text"
                          placeholder="e.g. Credited to Transporter Current A/C at SBI Dankuni"
                          value={payNotes}
                          onChange={(e) => setPayNotes(e.target.value)}
                          className="w-full bg-slate-900 border border-slate-800 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-emerald-500"
                        />
                      </div>

                      <button
                        type="submit"
                        disabled={submitting}
                        className="w-full py-2 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white rounded-lg text-xs font-semibold transition flex items-center justify-center gap-2"
                      >
                        <Check className="w-4 h-4" />
                        {submitting ? "Reporting..." : "Submit Payment Record to Transporter"}
                      </button>
                    </form>
                  )}

                  {/* TRANSPORTER ACTIONS: Confirm or Dispute */}
                  {payment?.payment_status === "REPORTED_BY_DEALER" && isTransporterOrDriver && (
                    <div className="bg-slate-950/80 border border-emerald-500/30 rounded-xl p-4 space-y-3">
                      <h4 className="text-xs font-semibold text-emerald-400 uppercase tracking-wider flex items-center gap-2">
                        <ShieldCheck className="w-4 h-4" />
                        Transporter Acknowledgment Actions
                      </h4>
                      <p className="text-xs text-slate-300">
                        Verify your bank statement for UTR <code>{payment.payment_reference}</code> of {fmt(payment.amount_paid_inr)}.
                      </p>

                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                        <button
                          type="button"
                          onClick={() => handleAcknowledgePayment("CONFIRM")}
                          disabled={submitting}
                          className="py-2.5 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white rounded-xl text-xs font-semibold transition flex items-center justify-center gap-2"
                        >
                          <CheckCircle2 className="w-4 h-4" />
                          Confirm Receipt in Account
                        </button>
                        <button
                          type="button"
                          onClick={() => handleAcknowledgePayment("DISPUTE")}
                          disabled={submitting}
                          className="py-2.5 bg-red-600/80 hover:bg-red-500 disabled:opacity-50 text-white rounded-xl text-xs font-semibold transition flex items-center justify-center gap-2"
                        >
                          <AlertTriangle className="w-4 h-4" />
                          Dispute Reported Payment
                        </button>
                      </div>

                      <div className="pt-2">
                        <input
                          type="text"
                          placeholder="Optional remarks or reason if disputing..."
                          value={disputeReason || transNotes}
                          onChange={(e) => {
                            setDisputeReason(e.target.value);
                            setTransNotes(e.target.value);
                          }}
                          className="w-full bg-slate-900 border border-slate-800 rounded-lg px-3 py-1.5 text-xs text-white focus:outline-none"
                        />
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {/* TAB 2: SEPARATE PLATFORM INVOICE */}
          {activeTab === "invoice" && (
            <div className="space-y-4">
              <div className="p-3 bg-blue-500/10 border border-blue-500/20 rounded-xl text-xs text-blue-300">
                <strong>Platform Fee Separation:</strong> LoadLink charges a separate booking/service platform fee. The platform fee is <strong>never deducted</strong> from the transporter's freight funds.
              </div>

              {loading ? (
                <div className="py-12 text-center text-slate-400">Loading invoice details...</div>
              ) : !invoice ? (
                <div className="py-10 text-center border border-dashed border-slate-800 rounded-xl p-8">
                  <Receipt className="w-8 h-8 text-slate-600 mx-auto mb-2" />
                  <p className="text-slate-300 font-medium">No platform invoice generated yet</p>
                </div>
              ) : (
                <div className="bg-slate-950/80 border border-slate-800 rounded-xl p-5 space-y-4">
                  <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                    <div>
                      <span className="text-xs text-slate-500 block">TAX INVOICE NUMBER</span>
                      <span className="font-mono text-base font-bold text-white">{invoice.invoice_number}</span>
                    </div>
                    <span className="text-xs px-2.5 py-1 rounded-full bg-blue-500/20 text-blue-400 font-semibold uppercase">
                      {invoice.status}
                    </span>
                  </div>

                  <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 text-xs">
                    <div>
                      <span className="text-slate-500 block">Billed To Customer:</span>
                      <span className="font-medium text-slate-200">{invoice.billed_to_name}</span>
                    </div>
                    <div>
                      <span className="text-slate-500 block">Service Fee Type:</span>
                      <span className="font-medium text-slate-200">{invoice.fee_type?.replace(/_/g, " ")}</span>
                    </div>
                    <div>
                      <span className="text-slate-500 block">Due Date:</span>
                      <span className="font-medium text-slate-200">
                        {new Date(invoice.due_date).toLocaleDateString("en-IN")}
                      </span>
                    </div>
                  </div>

                  <div className="border-t border-slate-800 pt-3 space-y-2 text-xs">
                    <div className="flex justify-between text-slate-400">
                      <span>Freight Benchmark:</span>
                      <span>{fmt(invoice.freight_benchmark_inr)}</span>
                    </div>
                    <div className="flex justify-between text-slate-300">
                      <span>LoadLink Platform Base Fee:</span>
                      <span className="font-semibold">{fmt(invoice.base_fee_inr)}</span>
                    </div>
                    <div className="flex justify-between text-slate-400">
                      <span>GST (18% Goods & Services Tax):</span>
                      <span>{fmt(invoice.gst_amount_inr)}</span>
                    </div>
                    <div className="border-t border-slate-800 pt-2 flex justify-between text-sm font-bold text-white">
                      <span>Total Invoice Payable:</span>
                      <span className="text-emerald-400 text-base">{fmt(invoice.total_payable_inr)}</span>
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
