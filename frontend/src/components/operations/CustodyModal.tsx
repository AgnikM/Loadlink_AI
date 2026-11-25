"use client";

import React, { useState, useEffect, useCallback } from "react";
import {
  X,
  Package,
  ShieldCheck,
  CheckCircle2,
  AlertTriangle,
  Clock,
  Camera,
  FileCheck,
  MapPin,
  Check,
  Truck,
  UserCheck,
  AlertCircle,
  FileText,
} from "lucide-react";
import { CustodyEvent, CustodyEventType, CargoCondition, DeliveryType } from "@/types";
import { api } from "@/lib/api";

interface CustodyModalProps {
  isOpen: boolean;
  onClose: () => void;
  shipmentId: string;
  currentUser?: any;
  onStatusUpdated?: () => void;
}

export default function CustodyModal({
  isOpen,
  onClose,
  shipmentId,
  currentUser,
  onStatusUpdated,
}: CustodyModalProps) {
  const [activeTab, setActiveTab] = useState<"timeline" | "loading" | "incident" | "delivery">("timeline");
  const [events, setEvents] = useState<CustodyEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState("");
  const [successMsg, setSuccessMsg] = useState("");

  // Loading Handover State
  const [loadSeal, setLoadSeal] = useState("");
  const [loadSealIntact, setLoadSealIntact] = useState(true);
  const [loadCondition, setLoadCondition] = useState<CargoCondition>("INTACT");
  const [loadWeight, setLoadWeight] = useState<number>(18.0);
  const [loadDriverAck, setLoadDriverAck] = useState(true);
  const [loadNotes, setLoadNotes] = useState("");

  // Incident State
  const [incDesc, setIncDesc] = useState("");
  const [incSealIntact, setIncSealIntact] = useState(false);
  const [incCondition, setIncCondition] = useState<CargoCondition>("DAMAGED");
  const [incLocation, setIncLocation] = useState("NH19 Corridor, Burdwan Bypass");

  // Delivery Handover State
  const [delType, setDelType] = useState<DeliveryType>("FULL_DELIVERY");
  const [delReceiverName, setDelReceiverName] = useState("");
  const [delReceiverPhone, setDelReceiverPhone] = useState("");
  const [delOtp, setDelOtp] = useState("582910");
  const [delWeight, setDelWeight] = useState<number>(18.0);
  const [delQuantity, setDelQuantity] = useState<number>(1.0);
  const [delQtyDiscrepancy, setDelQtyDiscrepancy] = useState<number>(0.0);
  const [delDamageReported, setDelDamageReported] = useState(false);
  const [delDamageDesc, setDelDamageDesc] = useState("");
  const [delNotes, setDelNotes] = useState("");

  const loadEvents = useCallback(async () => {
    if (!shipmentId) return;
    setLoading(true);
    setErrorMsg("");
    try {
      const data = await api.listCustodyEvents(shipmentId);
      setEvents(data);
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to load custody timeline");
    } finally {
      setLoading(false);
    }
  }, [shipmentId]);

  useEffect(() => {
    if (isOpen) {
      loadEvents();
      setErrorMsg("");
      setSuccessMsg("");
    }
  }, [isOpen, loadEvents]);

  const handleRecordLoading = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setErrorMsg("");
    setSuccessMsg("");
    try {
      await api.recordLoadingHandover(shipmentId, {
        seal_number: loadSeal || undefined,
        seal_intact: loadSealIntact,
        cargo_condition: loadCondition,
        recorded_weight_tons: loadWeight,
        photographs: ["/uploads/loading_evidence_photo.jpg"],
        driver_acknowledged: loadDriverAck,
        driver_notes: loadNotes,
      });
      setSuccessMsg("Loading handover recorded successfully. Consignment is now LOADED.");
      await loadEvents();
      setActiveTab("timeline");
      onStatusUpdated?.();
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to record loading handover");
    } finally {
      setSubmitting(false);
    }
  };

  const handleRecordIncident = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!incDesc) {
      setErrorMsg("Incident description is required.");
      return;
    }
    setSubmitting(true);
    setErrorMsg("");
    setSuccessMsg("");
    try {
      await api.recordTransitIncident(shipmentId, {
        damage_description: incDesc,
        seal_intact: incSealIntact,
        cargo_condition: incCondition,
        location_name: incLocation,
        photographs: ["/uploads/incident_evidence.jpg"],
      });
      setSuccessMsg("In-transit incident logged into immutable custody audit log.");
      await loadEvents();
      setActiveTab("timeline");
      onStatusUpdated?.();
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to log transit incident");
    } finally {
      setSubmitting(false);
    }
  };

  const handleRecordDelivery = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!delReceiverName) {
      setErrorMsg("Receiver name is required.");
      return;
    }
    setSubmitting(true);
    setErrorMsg("");
    setSuccessMsg("");
    try {
      await api.recordDeliveryHandover(shipmentId, {
        delivery_type: delType,
        receiver_name: delReceiverName,
        receiver_phone: delReceiverPhone || "+91 98300 00000",
        delivery_otp: delOtp,
        receiver_acknowledged: delType !== "REFUSAL",
        recorded_weight_tons: delWeight,
        recorded_quantity: delQuantity,
        quantity_discrepancy: delQtyDiscrepancy,
        damage_reported: delDamageReported || delType === "REFUSAL",
        damage_description: delDamageDesc,
        driver_notes: delNotes,
        photographs: ["/uploads/digital_pod_signed.pdf"],
      });
      setSuccessMsg(
        delType === "REFUSAL"
          ? "Consignment refusal recorded. Shipment moved to DISPUTED."
          : "Delivery completed successfully! Digital POD generated."
      );
      await loadEvents();
      setActiveTab("timeline");
      onStatusUpdated?.();
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to record delivery handover");
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
            <div className="p-2.5 bg-blue-500/10 border border-blue-500/20 rounded-xl text-blue-400">
              <Package className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-lg font-semibold text-white">Digital Cargo Custody & Handover</h2>
                <span className="text-xs px-2 py-0.5 rounded-full bg-slate-800 text-slate-300 font-mono">
                  {shipmentId.slice(0, 8)}...
                </span>
              </div>
              <p className="text-xs text-slate-400">
                Tamper-evident chain of custody, weight verification, and digital POD
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
            onClick={() => setActiveTab("timeline")}
            className={`pb-3 px-3 font-medium transition border-b-2 flex items-center gap-2 ${
              activeTab === "timeline"
                ? "border-blue-500 text-blue-400"
                : "border-transparent text-slate-400 hover:text-slate-200"
            }`}
          >
            <Clock className="w-4 h-4" /> Custody Timeline ({events.length})
          </button>
          <button
            onClick={() => setActiveTab("loading")}
            className={`pb-3 px-3 font-medium transition border-b-2 flex items-center gap-2 ${
              activeTab === "loading"
                ? "border-blue-500 text-blue-400"
                : "border-transparent text-slate-400 hover:text-slate-200"
            }`}
          >
            <Truck className="w-4 h-4" /> 1. Loading Handover
          </button>
          <button
            onClick={() => setActiveTab("incident")}
            className={`pb-3 px-3 font-medium transition border-b-2 flex items-center gap-2 ${
              activeTab === "incident"
                ? "border-amber-500 text-amber-400"
                : "border-transparent text-slate-400 hover:text-slate-200"
            }`}
          >
            <AlertTriangle className="w-4 h-4" /> 2. Log Transit Incident
          </button>
          <button
            onClick={() => setActiveTab("delivery")}
            className={`pb-3 px-3 font-medium transition border-b-2 flex items-center gap-2 ${
              activeTab === "delivery"
                ? "border-emerald-500 text-emerald-400"
                : "border-transparent text-slate-400 hover:text-slate-200"
            }`}
          >
            <FileCheck className="w-4 h-4" /> 3. Delivery & POD
          </button>
        </div>

        {/* Body Content */}
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

          {/* TAB 1: TIMELINE */}
          {activeTab === "timeline" && (
            <div className="space-y-4">
              {loading ? (
                <div className="py-12 text-center text-slate-400">Loading custody events...</div>
              ) : events.length === 0 ? (
                <div className="py-12 text-center border border-dashed border-slate-800 rounded-xl p-8">
                  <Package className="w-8 h-8 text-slate-600 mx-auto mb-2" />
                  <p className="text-slate-300 font-medium">No custody events recorded yet</p>
                  <p className="text-xs text-slate-500 mt-1">
                    Record loading handover when vehicle departs from shipper origin.
                  </p>
                </div>
              ) : (
                <div className="relative pl-6 space-y-6 before:absolute before:left-2 before:top-2 before:bottom-2 before:w-0.5 before:bg-slate-800">
                  {events.map((ev) => (
                    <div key={ev.id} className="relative">
                      <div
                        className={`absolute -left-6 top-1 w-4 h-4 rounded-full border-2 bg-slate-900 ${
                          ev.event_type === "DELIVERY_HANDOVER"
                            ? "border-emerald-500"
                            : ev.event_type === "TRANSIT_INCIDENT"
                            ? "border-amber-500"
                            : "border-blue-500"
                        }`}
                      />
                      <div className="p-4 bg-slate-950/60 border border-slate-800 rounded-xl space-y-2">
                        <div className="flex items-center justify-between">
                          <span
                            className={`text-xs px-2.5 py-0.5 rounded-full font-semibold ${
                              ev.event_type === "DELIVERY_HANDOVER"
                                ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                                : ev.event_type === "TRANSIT_INCIDENT"
                                ? "bg-amber-500/10 text-amber-400 border border-amber-500/20"
                                : "bg-blue-500/10 text-blue-400 border border-blue-500/20"
                            }`}
                          >
                            {ev.event_type.replace(/_/g, " ")}
                          </span>
                          <span className="text-xs text-slate-500 font-mono">
                            {new Date(ev.created_at).toLocaleString("en-IN")}
                          </span>
                        </div>

                        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs pt-1">
                          <div className="bg-slate-900/80 p-2 rounded-lg">
                            <span className="text-slate-500 block">Condition</span>
                            <span
                              className={`font-medium ${
                                ev.cargo_condition === "INTACT" ? "text-emerald-400" : "text-amber-400"
                              }`}
                            >
                              {ev.cargo_condition}
                            </span>
                          </div>
                          <div className="bg-slate-900/80 p-2 rounded-lg">
                            <span className="text-slate-500 block">Seal Number</span>
                            <span className="font-mono text-slate-300">
                              {ev.seal_number || "None"} {ev.seal_intact ? "(Intact)" : "(Compromised)"}
                            </span>
                          </div>
                          <div className="bg-slate-900/80 p-2 rounded-lg">
                            <span className="text-slate-500 block">Recorded Weight</span>
                            <span className="font-medium text-slate-300">
                              {ev.recorded_weight_tons ? `${ev.recorded_weight_tons} MT` : "N/A"}
                            </span>
                          </div>
                          <div className="bg-slate-900/80 p-2 rounded-lg">
                            <span className="text-slate-500 block">Logged By</span>
                            <span className="font-medium text-slate-300">{ev.recorded_by_name || "Driver"}</span>
                          </div>
                        </div>

                        {ev.weight_discrepancy_tons !== undefined && ev.weight_discrepancy_tons !== 0 && (
                          <div className="p-2 bg-red-500/10 border border-red-500/20 rounded-lg text-xs text-red-300 flex items-center justify-between">
                            <span>Weight Discrepancy Observed:</span>
                            <span className="font-bold font-mono">{ev.weight_discrepancy_tons} MT</span>
                          </div>
                        )}

                        {ev.damage_description && (
                          <div className="text-xs p-2 bg-amber-500/10 border border-amber-500/20 rounded-lg text-amber-300">
                            <strong>Damage / Incident Note:</strong> {ev.damage_description}
                          </div>
                        )}

                        {ev.driver_notes && (
                          <p className="text-xs text-slate-400 italic">Notes: {ev.driver_notes}</p>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* TAB 2: LOADING HANDOVER FORM */}
          {activeTab === "loading" && (
            <form onSubmit={handleRecordLoading} className="space-y-4">
              <div className="p-3 bg-blue-500/10 border border-blue-500/20 rounded-xl text-xs text-blue-300">
                At shipper loading point, verify physical consignment seal, photograph loaded truck, and record initial weighbridge slip.
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-medium text-slate-300 mb-1">Security Seal Number</label>
                  <input
                    type="text"
                    placeholder="e.g. SL-WB-88190"
                    value={loadSeal}
                    onChange={(e) => setLoadSeal(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-300 mb-1">Recorded Weight (MT)</label>
                  <input
                    type="number"
                    step="0.1"
                    value={loadWeight}
                    onChange={(e) => setLoadWeight(parseFloat(e.target.value) || 0)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-medium text-slate-300 mb-1">Cargo Condition</label>
                  <select
                    value={loadCondition}
                    onChange={(e) => setLoadCondition(e.target.value as CargoCondition)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500"
                  >
                    <option value="INTACT">INTACT (Clean & Undamaged)</option>
                    <option value="PARTIALLY_DAMAGED">PARTIALLY DAMAGED</option>
                    <option value="SEAL_COMPROMISED">SEAL COMPROMISED</option>
                  </select>
                </div>
                <div className="flex items-center gap-3 pt-6">
                  <input
                    type="checkbox"
                    id="sealIntact"
                    checked={loadSealIntact}
                    onChange={(e) => setLoadSealIntact(e.target.checked)}
                    className="w-4 h-4 rounded text-blue-600 bg-slate-950 border-slate-700"
                  />
                  <label htmlFor="sealIntact" className="text-xs text-slate-300">
                    Tamper-evident seal inspected and confirmed intact
                  </label>
                </div>
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">Loading Notes</label>
                <textarea
                  rows={2}
                  placeholder="Notes on lashing, weather protection, or loading bay..."
                  value={loadNotes}
                  onChange={(e) => setLoadNotes(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500"
                />
              </div>

              <div className="p-3 bg-slate-950 border border-slate-800 rounded-xl flex items-center justify-between text-xs">
                <span className="text-slate-400">Driver Acknowledgement:</span>
                <label className="flex items-center gap-2 cursor-pointer text-slate-200">
                  <input
                    type="checkbox"
                    checked={loadDriverAck}
                    onChange={(e) => setLoadDriverAck(e.target.checked)}
                    className="w-4 h-4 rounded text-blue-600 bg-slate-900 border-slate-700"
                  />
                  I confirm custody transfer of specified cargo
                </label>
              </div>

              <button
                type="submit"
                disabled={submitting}
                className="w-full py-2.5 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white rounded-xl font-medium transition text-sm flex items-center justify-center gap-2"
              >
                <Check className="w-4 h-4" />
                {submitting ? "Recording Handover..." : "Confirm Loading Handover"}
              </button>
            </form>
          )}

          {/* TAB 3: IN-TRANSIT INCIDENT FORM */}
          {activeTab === "incident" && (
            <form onSubmit={handleRecordIncident} className="space-y-4">
              <div className="p-3 bg-amber-500/10 border border-amber-500/20 rounded-xl text-xs text-amber-300">
                Log any highway incidents, seal damage, rain water seepage, or mechanical hold-ups along the corridor.
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">Location of Incident</label>
                <input
                  type="text"
                  value={incLocation}
                  onChange={(e) => setIncLocation(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-amber-500"
                />
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-medium text-slate-300 mb-1">Cargo Condition</label>
                  <select
                    value={incCondition}
                    onChange={(e) => setIncCondition(e.target.value as CargoCondition)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-amber-500"
                  >
                    <option value="DAMAGED">DAMAGED</option>
                    <option value="PARTIALLY_DAMAGED">PARTIALLY DAMAGED</option>
                    <option value="WET_RAIN_DAMAGE">WET / RAIN SEEPAGE</option>
                    <option value="SEAL_COMPROMISED">SEAL TAMPERED / BROKEN</option>
                  </select>
                </div>
                <div className="flex items-center gap-3 pt-6">
                  <input
                    type="checkbox"
                    id="incSeal"
                    checked={incSealIntact}
                    onChange={(e) => setIncSealIntact(e.target.checked)}
                    className="w-4 h-4 rounded text-amber-600 bg-slate-950 border-slate-700"
                  />
                  <label htmlFor="incSeal" className="text-xs text-slate-300">
                    Seal is still intact despite incident
                  </label>
                </div>
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">Damage Description</label>
                <textarea
                  rows={3}
                  required
                  placeholder="Describe specific cargo impact, packaging damage, or road event..."
                  value={incDesc}
                  onChange={(e) => setIncDesc(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-amber-500"
                />
              </div>

              <button
                type="submit"
                disabled={submitting}
                className="w-full py-2.5 bg-amber-600 hover:bg-amber-500 disabled:opacity-50 text-white rounded-xl font-medium transition text-sm flex items-center justify-center gap-2"
              >
                <AlertTriangle className="w-4 h-4" />
                {submitting ? "Logging Incident..." : "Submit Incident Report"}
              </button>
            </form>
          )}

          {/* TAB 4: DELIVERY HANDOVER & DIGITAL POD */}
          {activeTab === "delivery" && (
            <form onSubmit={handleRecordDelivery} className="space-y-4">
              <div className="p-3 bg-emerald-500/10 border border-emerald-500/20 rounded-xl text-xs text-emerald-300">
                At consignee gate, verify receiver identity, validate delivery OTP, inspect condition, and generate digital POD.
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">Delivery Outcome</label>
                <div className="grid grid-cols-3 gap-2">
                  <button
                    type="button"
                    onClick={() => setDelType("FULL_DELIVERY")}
                    className={`py-2 px-3 rounded-lg text-xs font-medium border text-center transition ${
                      delType === "FULL_DELIVERY"
                        ? "bg-emerald-500/20 border-emerald-500 text-emerald-300"
                        : "bg-slate-950 border-slate-800 text-slate-400 hover:border-slate-700"
                    }`}
                  >
                    Full Delivery
                  </button>
                  <button
                    type="button"
                    onClick={() => setDelType("PARTIAL_DELIVERY")}
                    className={`py-2 px-3 rounded-lg text-xs font-medium border text-center transition ${
                      delType === "PARTIAL_DELIVERY"
                        ? "bg-amber-500/20 border-amber-500 text-amber-300"
                        : "bg-slate-950 border-slate-800 text-slate-400 hover:border-slate-700"
                    }`}
                  >
                    Partial Delivery
                  </button>
                  <button
                    type="button"
                    onClick={() => setDelType("REFUSAL")}
                    className={`py-2 px-3 rounded-lg text-xs font-medium border text-center transition ${
                      delType === "REFUSAL"
                        ? "bg-red-500/20 border-red-500 text-red-300"
                        : "bg-slate-950 border-slate-800 text-slate-400 hover:border-slate-700"
                    }`}
                  >
                    Consignment Refusal
                  </button>
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <div>
                  <label className="block text-xs font-medium text-slate-300 mb-1">Receiver / Store Officer Name</label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. Manoj Karmakar"
                    value={delReceiverName}
                    onChange={(e) => setDelReceiverName(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-emerald-500"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-300 mb-1">Receiver Mobile</label>
                  <input
                    type="text"
                    placeholder="+91 98300 00000"
                    value={delReceiverPhone}
                    onChange={(e) => setDelReceiverPhone(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-emerald-500"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-300 mb-1">Delivery OTP</label>
                  <input
                    type="text"
                    value={delOtp}
                    onChange={(e) => setDelOtp(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm text-white font-mono focus:outline-none focus:border-emerald-500"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-slate-300 mb-1">Recorded Weight (MT)</label>
                  <input
                    type="number"
                    step="0.1"
                    value={delWeight}
                    onChange={(e) => setDelWeight(parseFloat(e.target.value) || 0)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-emerald-500"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-300 mb-1">Quantity Discrepancy (if any)</label>
                  <input
                    type="number"
                    step="0.01"
                    value={delQtyDiscrepancy}
                    onChange={(e) => setDelQtyDiscrepancy(parseFloat(e.target.value) || 0)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-emerald-500"
                  />
                </div>
              </div>

              {(delType === "PARTIAL_DELIVERY" || delType === "REFUSAL") && (
                <div>
                  <label className="block text-xs font-medium text-red-400 mb-1">
                    Discrepancy / Refusal Reason
                  </label>
                  <textarea
                    rows={2}
                    required
                    placeholder="Provide specific notes on broken seals, damage, or quantity shortfall..."
                    value={delDamageDesc}
                    onChange={(e) => setDelDamageDesc(e.target.value)}
                    className="w-full bg-slate-950 border border-red-500/40 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-red-500"
                  />
                </div>
              )}

              <button
                type="submit"
                disabled={submitting}
                className={`w-full py-2.5 rounded-xl font-medium transition text-sm flex items-center justify-center gap-2 text-white ${
                  delType === "REFUSAL"
                    ? "bg-red-600 hover:bg-red-500"
                    : "bg-emerald-600 hover:bg-emerald-500"
                } disabled:opacity-50`}
              >
                <FileCheck className="w-4 h-4" />
                {submitting
                  ? "Processing Delivery..."
                  : delType === "REFUSAL"
                  ? "Record Consignment Refusal"
                  : "Generate Digital POD & Complete Delivery"}
              </button>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}
