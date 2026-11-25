"use client";

import React, { useState, useEffect } from "react";
import { Plus, Sparkles, Truck, MapPin, IndianRupee, ShieldCheck, CheckCircle2, AlertTriangle, FileText, Star, Eye, RefreshCw, Info, ChevronRight } from "lucide-react";
import { Load, Match, Shipment } from "@/types";
import { api } from "@/lib/api";
import FreightMap from "@/components/map/FreightMap";
import PostLoadModal from "@/components/dealer/PostLoadModal";
import MatchBreakdownModal from "@/components/dealer/MatchBreakdownModal";

interface DealerViewProps {
  loads: Load[];
  shipments: Shipment[];
  onRefresh: () => void;
}

export default function DealerView({ loads, shipments, onRefresh }: DealerViewProps) {
  const initialLoad = loads.find((l) => l.status !== "COMPLETED" && l.status !== "CANCELLED") || loads[0] || null;
  const [selectedLoad, setSelectedLoad] = useState<Load | null>(initialLoad);
  const [matches, setMatches] = useState<Match[]>([]);
  const [diagnostics, setDiagnostics] = useState<any>(null);
  const [selectedMatch, setSelectedMatch] = useState<Match | null>(null);
  const [isPostModalOpen, setIsPostModalOpen] = useState(false);
  const [isMatchModalOpen, setIsMatchModalOpen] = useState(false);
  const [loadingMatches, setLoadingMatches] = useState(false);

  // Active Shipment Tracking Selection
  const [selectedShipment, setSelectedShipment] = useState<Shipment | null>(
    shipments.find((s) => s.state !== "COMPLETED" && s.state !== "CANCELLED") || shipments[0] || null
  );

  // Rating Modal state
  const [isRatingModalOpen, setIsRatingModalOpen] = useState(false);
  const [ratingScore, setRatingScore] = useState(5);
  const [ratingComment, setRatingComment] = useState("");

  // Sync selected load
  useEffect(() => {
    if (loads.length > 0 && !selectedLoad) {
      const active = loads.find((l) => l.status !== "COMPLETED" && l.status !== "CANCELLED") || loads[0];
      setSelectedLoad(active);
    }
  }, [loads, selectedLoad]);

  // Sync selected shipment
  useEffect(() => {
    if (shipments.length > 0 && !selectedShipment) {
      const active = shipments.find((s) => s.state !== "COMPLETED" && s.state !== "CANCELLED");
      setSelectedShipment(active || shipments[0]);
    }
  }, [shipments, selectedShipment]);

  // Load matches & diagnostics when selectedLoad changes
  const fetchMatchesForLoad = async (loadId: string) => {
    setLoadingMatches(true);
    try {
      const data = await api.getMatches(loadId);
      setMatches(data || []);
      if (!data || data.length === 0) {
        // Fetch diagnostics to explain rejection reasons
        const diag = await api.getMatchDiagnostics(loadId).catch(() => null);
        setDiagnostics(diag);
      } else {
        setDiagnostics(null);
      }
    } catch {
      setMatches([]);
      const diag = await api.getMatchDiagnostics(loadId).catch(() => null);
      setDiagnostics(diag);
    } finally {
      setLoadingMatches(false);
    }
  };

  useEffect(() => {
    if (selectedLoad) {
      fetchMatchesForLoad(selectedLoad.id);
    }
  }, [selectedLoad]);

  const handleForceRegenerateMatches = async () => {
    if (!selectedLoad) return;
    setLoadingMatches(true);
    try {
      await api.generateMatches(selectedLoad.id);
      await fetchMatchesForLoad(selectedLoad.id);
      onRefresh();
    } catch (err: any) {
      alert(err.message || "Failed to recalculate matches");
    } finally {
      setLoadingMatches(false);
    }
  };

  const handleVerifyPOD = async (shipmentId: string, action: "VERIFY" | "REJECT") => {
    try {
      await api.verifyPOD(shipmentId, action);
      alert(`POD marked as ${action === "VERIFY" ? "Verified! Consignment marked completed." : "Rejected for resubmission."}`);
      onRefresh();
    } catch (err: any) {
      alert(err.message || "Failed to verify POD");
    }
  };

  const handleSubmitRating = async () => {
    if (!selectedShipment) return;
    try {
      await api.submitRating({
        shipment_id: selectedShipment.id,
        score: ratingScore,
        tags: ["On-Time Pickup", "Professional Driver", "Secure Lashing"],
        comment: ratingComment,
      });
      alert("Carrier rating submitted successfully! Trust score updated.");
      setIsRatingModalOpen(false);
      onRefresh();
    } catch (err: any) {
      alert(err.message || "Failed to submit rating");
    }
  };

  return (
    <div className="space-y-6">
      {/* Enterprise Header Banner */}
      <div className="bg-[#FFFFFF] border border-[#E6DED5] p-5 rounded-2xl shadow-xs flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2.5">
            <h1 className="text-xl font-bold text-[#29231F]">
              Dealer Freight Management Portal
            </h1>
            <span className="text-[11px] font-semibold px-2.5 py-0.5 rounded-full bg-[#F0EAE1] text-[#5A3E2B] border border-[#E6DED5]">
              Verified Shipper (96% Trust Index)
            </span>
          </div>
          <p className="text-xs text-[#6E6259] mt-1">
            Deterministic 7-factor truck ranking, real-time corridor GPS tracking, and digital POD approvals.
          </p>
        </div>

        <button
          onClick={() => setIsPostModalOpen(true)}
          className="flex items-center gap-2 px-4 py-2.5 rounded-lg bg-[#5A3E2B] hover:bg-[#432E20] text-white font-semibold text-xs shadow-xs transition cursor-pointer"
        >
          <Plus className="w-4 h-4" />
          <span>Post New Consignment</span>
        </button>
      </div>

      {/* Main Grid: Left = Posted Loads & Ranked Matches, Right = Live Shipment Tracking & POD */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column (5 Cols): Consignments & Matches */}
        <div className="lg:col-span-5 space-y-6">
          {/* Active Loads Selector */}
          <div className="bg-[#FFFFFF] border border-[#E6DED5] rounded-2xl p-4 shadow-xs">
            <div className="flex items-center justify-between mb-3">
              <span className="text-xs font-bold uppercase tracking-wider text-[#29231F]">
                Posted Consignments ({loads.length})
              </span>
              <span className="text-[11px] text-[#6E6259]">Select to inspect matches</span>
            </div>

            <div className="space-y-2.5 max-h-56 overflow-y-auto pr-1">
              {loads.length === 0 ? (
                <div className="p-6 text-center text-xs text-[#6E6259] border border-dashed border-[#E6DED5] rounded-xl">
                  No active consignments. Click &quot;Post New Consignment&quot; to get started.
                </div>
              ) : (
                loads.map((l) => {
                  const isSelected = selectedLoad?.id === l.id;
                  return (
                    <div
                      key={l.id}
                      onClick={() => setSelectedLoad(l)}
                      className={`p-3.5 rounded-xl border cursor-pointer transition-all ${
                        isSelected
                          ? "bg-[#F7F5F0] border-[#5A3E2B] shadow-xs"
                          : "bg-[#FFFFFF] border-[#E6DED5] hover:border-[#C8BDB0]"
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-1.5 truncate max-w-[200px]">
                          <span className="text-xs font-bold text-[#29231F] truncate">
                            {l.cargo_type} ({l.cargo_weight_tons}T)
                          </span>
                          {(l.is_demo || l.id.startsWith("DEMO-")) && (
                            <span className="text-[9px] font-bold px-1.5 py-0.5 rounded bg-[#FEF3C7] text-[#92400E] border border-[#FDE68A] shrink-0">
                              DEMO DATA
                            </span>
                          )}
                        </div>
                        <span
                          className={`text-[10px] uppercase font-bold px-2 py-0.5 rounded-full ${
                            l.status === "COMPLETED"
                              ? "bg-[#EBF5EE] text-[#3F7D58] border border-[#C6E6D0]"
                              : l.status === "CONFIRMED"
                              ? "bg-[#F0EAE1] text-[#5A3E2B] border border-[#E6DED5]"
                              : "bg-[#FEF6E7] text-[#B7791F] border border-[#FCDCA0]"
                          }`}
                        >
                          {l.status}
                        </span>
                      </div>

                      <div className="flex items-center gap-1.5 text-[11px] text-[#6E6259] mt-1.5">
                        <MapPin className="w-3 h-3 text-[#5A3E2B] flex-shrink-0" />
                        <span className="truncate">{l.origin_name}</span>
                        <span>→</span>
                        <span className="truncate">{l.destination_name}</span>
                      </div>

                      <div className="flex items-center justify-between mt-2 pt-2 border-t border-[#E6DED5] text-[11px]">
                        <span className="text-[#6E6259]">
                          Target Budget:{" "}
                          <strong className="text-[#29231F] font-mono">
                            ₹{(l.target_budget || l.estimated_benchmark_price || 0).toLocaleString("en-IN")}
                          </strong>
                        </span>
                        <span className="text-[#5A3E2B] font-semibold flex items-center gap-1">
                          <Sparkles className="w-3 h-3 text-[#B7791F]" />
                          <span>Candidates ({l.matches_count || 0})</span>
                        </span>
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          </div>

          {/* Ranked Truck Matches with Zero-Match Diagnostics */}
          <div className="bg-[#FFFFFF] border border-[#E6DED5] rounded-2xl p-4 shadow-xs">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <Sparkles className="w-4 h-4 text-[#B7791F]" />
                <span className="text-xs font-bold uppercase tracking-wider text-[#29231F]">
                  Deterministic Ranked Fleet
                </span>
              </div>
              <button
                onClick={handleForceRegenerateMatches}
                disabled={loadingMatches || !selectedLoad}
                title="Recalculate 7-factor candidate scores"
                className="text-[11px] text-[#5A3E2B] font-semibold flex items-center gap-1 hover:underline cursor-pointer disabled:opacity-50"
              >
                <RefreshCw className={`w-3 h-3 ${loadingMatches ? "animate-spin" : ""}`} />
                <span>Recalculate</span>
              </button>
            </div>

            {loadingMatches ? (
              <div className="py-8 text-center text-xs text-[#6E6259]">
                <div className="w-5 h-5 border-2 border-[#5A3E2B] border-t-transparent rounded-full animate-spin mx-auto mb-2" />
                Evaluating 7-factor weights for candidate fleet...
              </div>
            ) : matches.length === 0 ? (
              /* Zero-Match Diagnostic Box (Human readable rejection explanation) */
              <div className="p-4 bg-[#F7F5F0] border border-[#E6DED5] rounded-xl space-y-3">
                <div className="flex items-start gap-2 text-xs text-[#29231F]">
                  <Info className="w-4 h-4 text-[#B7791F] flex-shrink-0 mt-0.5" />
                  <div>
                    <p className="font-semibold text-[#29231F]">
                      No Immediate Matches for this Consignment
                    </p>
                    <p className="text-[#6E6259] mt-0.5 text-[11px]">
                      Our deterministic filter evaluated active trucks across the West Bengal corridor against strict requirements.
                    </p>
                  </div>
                </div>

                {diagnostics && ((diagnostics.rejection_summary && diagnostics.rejection_summary.length > 0) || (diagnostics.detailed_reasons && diagnostics.detailed_reasons.length > 0)) ? (
                  <div className="space-y-1.5 pt-2 border-t border-[#E6DED5]">
                    <span className="text-[10px] font-bold uppercase tracking-wider text-[#6E6259]">
                      Hard Constraint Rejection Breakdown ({diagnostics.rejected_trucks || 0} evaluated trucks):
                    </span>
                    <ul className="space-y-1 text-[11px] text-[#6E6259]">
                      {(diagnostics.rejection_summary && diagnostics.rejection_summary.length > 0
                        ? diagnostics.rejection_summary
                        : diagnostics.detailed_reasons
                      ).map((r: string, i: number) => (
                        <li key={i} className="flex items-center gap-1.5">
                          <span className="w-1.5 h-1.5 rounded-full bg-[#B7791F]" />
                          <span>{r}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                ) : (
                  <div className="text-[11px] text-[#6E6259] pt-2 border-t border-[#E6DED5]">
                    No candidate trucks currently evaluated or online within the pickup corridor.
                  </div>
                )}

                <button
                  onClick={handleForceRegenerateMatches}
                  className="w-full py-2.5 px-3 rounded-lg bg-[#5A3E2B] text-white text-xs font-semibold hover:bg-[#432E20] transition cursor-pointer flex items-center justify-center gap-1.5 shadow-xs"
                >
                  <Sparkles className="w-3.5 h-3.5 text-[#B7791F]" />
                  <span>Run 7-Factor Matching Engine</span>
                </button>
              </div>
            ) : (
              <div className="space-y-3 max-h-80 overflow-y-auto pr-1">
                {matches.map((m, idx) => (
                  <div
                    key={m.id}
                    className="bg-[#FFFFFF] border border-[#E6DED5] hover:border-[#C8BDB0] rounded-xl p-3.5 transition shadow-xs"
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span className="w-5 h-5 rounded-full bg-[#F0EAE1] text-[10px] font-mono font-bold flex items-center justify-center text-[#5A3E2B]">
                          #{idx + 1}
                        </span>
                        <div>
                          <span className="text-xs font-bold text-[#29231F]">{m.truck_registration_no}</span>
                          <span className="text-[11px] text-[#6E6259] ml-1.5">• {m.driver_name}</span>
                        </div>
                      </div>

                      <div className="text-right">
                        <span className="text-sm font-black font-mono text-[#3F7D58]">{m.total_score}</span>
                        <span className="text-[10px] text-[#8A796B] font-mono">/100</span>
                      </div>
                    </div>

                    {/* Badges / Predictive Tags */}
                    <div className="flex flex-wrap gap-1.5 mt-1.5">
                      {m.is_demo && (
                        <div className="px-2 py-0.5 rounded bg-[#EFF6FF] border border-[#BFDBFE] text-[10px] text-[#1E40AF] font-bold inline-flex items-center gap-1">
                          <span className="w-1.5 h-1.5 rounded-full bg-[#3B82F6]" />
                          <span>DEMO DATA · Unverified</span>
                        </div>
                      )}
                      {m.is_coming_near_you && (
                        <div className="px-2 py-0.5 rounded bg-[#FEF6E7] border border-[#FCDCA0] text-[10px] text-[#B7791F] font-semibold inline-block">
                          Predictive: In-Transit Truck Approaching Pickup Hub
                        </div>
                      )}
                    </div>

                    {/* Algorithm Rationale Summary */}
                    <p className="text-[11px] text-[#6E6259] mt-2 line-clamp-2 leading-relaxed bg-[#F7F5F0] p-2 rounded-lg border border-[#E6DED5]">
                      {m.explanation_summary}
                    </p>

                    <div className="flex items-center justify-between mt-3 pt-2 border-t border-[#E6DED5] text-[11px]">
                      <span className="text-[#6E6259]">
                        Reliability: <strong className="text-[#3F7D58]">{m.driver_reliability_score}%{m.is_demo ? " (Synthetic Demo)" : ""}</strong>
                      </span>
                      <button
                        onClick={() => {
                          setSelectedMatch(m);
                          setIsMatchModalOpen(true);
                        }}
                        className="flex items-center gap-1 text-[#5A3E2B] font-semibold hover:underline cursor-pointer"
                      >
                        <span>Score Breakdown & Book</span>
                        <ChevronRight className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Right Column (7 Cols): Live Tracking, Route Telemetry, and POD Approval */}
        <div className="lg:col-span-7 space-y-6">
          {/* Active Shipment Header */}
          <div className="bg-[#FFFFFF] border border-[#E6DED5] rounded-2xl p-4 shadow-xs relative isolate">
            <div className="flex items-center justify-between mb-3">
              <span className="text-xs font-bold uppercase tracking-wider text-[#29231F]">
                Corridor Telemetry & Route Map
              </span>
              {selectedShipment && (
                <span className="text-xs font-mono font-bold px-2.5 py-0.5 rounded-full bg-[#F0EAE1] text-[#5A3E2B] border border-[#E6DED5]">
                  Shipment #{selectedShipment.id.slice(0, 8)} • {selectedShipment.state}
                </span>
              )}
            </div>

            {/* Freight Map Component - Stable single instance across load/shipment modes */}
            <FreightMap
              origin={
                selectedShipment
                  ? {
                      lat: selectedShipment.origin_lat,
                      lon: selectedShipment.origin_lon,
                      name: selectedShipment.origin_name,
                    }
                  : selectedLoad
                  ? {
                      lat: selectedLoad.origin_lat,
                      lon: selectedLoad.origin_lon,
                      name: selectedLoad.origin_name,
                    }
                  : undefined
              }
              destination={
                selectedShipment
                  ? {
                      lat: selectedShipment.destination_lat,
                      lon: selectedShipment.destination_lon,
                      name: selectedShipment.destination_name,
                    }
                  : selectedLoad
                  ? {
                      lat: selectedLoad.destination_lat,
                      lon: selectedLoad.destination_lon,
                      name: selectedLoad.destination_name,
                    }
                  : undefined
              }
              truckLocation={
                selectedShipment
                  ? {
                      lat: selectedShipment.current_lat || selectedShipment.origin_lat,
                      lon: selectedShipment.current_lon || selectedShipment.origin_lon,
                      regNo: selectedShipment.truck_registration_no,
                      isStale: selectedShipment.is_location_stale,
                    }
                  : undefined
              }
              height="340px"
              interactive={!isMatchModalOpen && !isPostModalOpen && !isRatingModalOpen}
            />

            {/* Shipment Milestones Timeline */}
            {selectedShipment && (
              <div className="mt-4 pt-3 border-t border-[#E6DED5]">
                <div className="flex items-center justify-between text-xs mb-2">
                  <span className="font-semibold text-[#29231F]">Consignment Journey</span>
                  <span className="text-[11px] text-[#6E6259]">
                    Rate: <strong className="text-[#29231F] font-mono">₹{(selectedShipment.agreed_freight || 0).toLocaleString("en-IN")}</strong>
                  </span>
                </div>

                <div className="grid grid-cols-5 gap-1.5 text-center text-[10px] font-medium">
                  <div className={`p-1.5 rounded ${["CONFIRMED", "DRIVER_EN_ROUTE", "ARRIVED_PICKUP", "LOADING", "LOADED", "IN_TRANSIT", "NEAR_DESTINATION", "DELIVERED", "COMPLETED"].includes(selectedShipment.state) ? "bg-[#5A3E2B] text-white" : "bg-[#F7F5F0] text-[#8A796B]"}`}>
                    Confirmed
                  </div>
                  <div className={`p-1.5 rounded ${["ARRIVED_PICKUP", "LOADING", "LOADED", "IN_TRANSIT", "NEAR_DESTINATION", "DELIVERED", "COMPLETED"].includes(selectedShipment.state) ? "bg-[#5A3E2B] text-white" : "bg-[#F7F5F0] text-[#8A796B]"}`}>
                    Pickup Gate
                  </div>
                  <div className={`p-1.5 rounded ${["LOADED", "IN_TRANSIT", "NEAR_DESTINATION", "DELIVERED", "COMPLETED"].includes(selectedShipment.state) ? "bg-[#5A3E2B] text-white" : "bg-[#F7F5F0] text-[#8A796B]"}`}>
                    In Transit
                  </div>
                  <div className={`p-1.5 rounded ${["DELIVERED", "COMPLETED"].includes(selectedShipment.state) ? "bg-[#5A3E2B] text-white" : "bg-[#F7F5F0] text-[#8A796B]"}`}>
                    Delivered
                  </div>
                  <div className={`p-1.5 rounded ${selectedShipment.state === "COMPLETED" ? "bg-[#3F7D58] text-white font-bold" : "bg-[#F7F5F0] text-[#8A796B]"}`}>
                    Settled (POD)
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Digital Proof of Delivery (POD) Approval Card */}
          {selectedShipment && (selectedShipment.has_pod || selectedShipment.pod_verification_status) && (
            <div className="bg-[#FFFFFF] border border-[#E6DED5] rounded-2xl p-4 shadow-xs space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <FileText className="w-4 h-4 text-[#5A3E2B]" />
                  <span className="text-xs font-bold uppercase tracking-wider text-[#29231F]">
                    Digital Proof of Delivery (ePOD)
                  </span>
                </div>
                <span
                  className={`text-[10px] font-bold uppercase px-2 py-0.5 rounded-full ${
                    selectedShipment.pod_verification_status === "VERIFIED"
                      ? "bg-[#EBF5EE] text-[#3F7D58] border border-[#C6E6D0]"
                      : selectedShipment.pod_verification_status === "PENDING_REVIEW"
                      ? "bg-[#FEF6E7] text-[#B7791F] border border-[#FCDCA0]"
                      : "bg-[#F7F5F0] text-[#6E6259]"
                  }`}
                >
                  {selectedShipment.pod_verification_status || "PENDING_REVIEW"}
                </span>
              </div>

              <div className="p-3 bg-[#F7F5F0] border border-[#E6DED5] rounded-xl flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 text-xs">
                <div>
                  <p className="font-semibold text-[#29231F]">
                    Consignee: {(selectedShipment as any).pod_receiver_name || "Site Gate Security"}
                  </p>
                  <p className="text-[11px] text-[#6E6259]">
                    Contact: {(selectedShipment as any).pod_receiver_phone || "+91-98300-XXXXX"} • Notes: {(selectedShipment as any).pod_signature_notes || "Clean delivery receipt stamped"}
                  </p>
                </div>

                {selectedShipment.pod_verification_status === "PENDING_REVIEW" && (
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => handleVerifyPOD(selectedShipment.id, "REJECT")}
                      className="px-3 py-1.5 rounded-lg border border-red-300 text-red-700 hover:bg-red-50 text-xs font-semibold transition cursor-pointer"
                    >
                      Reject
                    </button>
                    <button
                      onClick={() => handleVerifyPOD(selectedShipment.id, "VERIFY")}
                      className="px-3.5 py-1.5 rounded-lg bg-[#3F7D58] hover:bg-[#346648] text-white text-xs font-semibold shadow-xs transition cursor-pointer flex items-center gap-1"
                    >
                      <CheckCircle2 className="w-3.5 h-3.5" />
                      <span>Approve & Release Payment</span>
                    </button>
                  </div>
                )}
              </div>

              {/* Carrier Rating CTA if Completed */}
              {selectedShipment.state === "COMPLETED" && (
                <div className="flex items-center justify-between pt-2 border-t border-[#E6DED5]">
                  <span className="text-xs text-[#6E6259]">
                    Shipment closed. Rate carrier Rajesh Yadav to update reliability index.
                  </span>
                  <button
                    onClick={() => setIsRatingModalOpen(true)}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#F0EAE1] hover:bg-[#E6DED5] text-[#5A3E2B] text-xs font-bold transition cursor-pointer"
                  >
                    <Star className="w-3.5 h-3.5 text-[#B7791F] fill-[#B7791F]" />
                    <span>Rate Carrier</span>
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Post Load Modal */}
      <PostLoadModal
        isOpen={isPostModalOpen}
        onClose={() => setIsPostModalOpen(false)}
        onLoadCreated={(newLoad) => {
          setSelectedLoad(newLoad);
          onRefresh();
        }}
      />

      {/* Match Breakdown & Booking Modal */}
      <MatchBreakdownModal
        isOpen={isMatchModalOpen}
        onClose={() => setIsMatchModalOpen(false)}
        match={selectedMatch}
        load={selectedLoad}
        onBookingCreated={onRefresh}
      />

      {/* Carrier Rating Modal */}
      {isRatingModalOpen && (
        <div
          onWheel={(e) => e.stopPropagation()}
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-xs p-4 overflow-y-auto"
        >
          <div className="bg-[#FFFFFF] border border-[#E6DED5] rounded-2xl max-w-md w-full p-6 shadow-2xl relative my-8 isolate">
            <h3 className="text-base font-bold text-[#29231F]">Submit Carrier Performance Rating</h3>
            <p className="text-xs text-[#6E6259] mt-1">
              Feedback directly affects the 7-factor carrier reliability algorithm.
            </p>

            <div className="mt-4 flex items-center justify-center gap-2">
              {[1, 2, 3, 4, 5].map((star) => (
                <button
                  key={star}
                  onClick={() => setRatingScore(star)}
                  className="p-1 text-2xl transition cursor-pointer"
                >
                  <Star
                    className={`w-7 h-7 ${
                      star <= ratingScore
                        ? "text-[#B7791F] fill-[#B7791F]"
                        : "text-[#E6DED5]"
                    }`}
                  />
                </button>
              ))}
            </div>

            <textarea
              rows={3}
              value={ratingComment}
              onChange={(e) => setRatingComment(e.target.value)}
              placeholder="e.g. Prompt arrival at pickup dock, safe lashing, polite driver."
              className="mt-4 w-full bg-[#F7F5F0] border border-[#E6DED5] rounded-lg p-2.5 text-xs text-[#29231F] focus:outline-none focus:border-[#5A3E2B]"
            />

            <div className="mt-4 flex items-center justify-end gap-2.5">
              <button
                onClick={() => setIsRatingModalOpen(false)}
                className="px-3.5 py-1.5 text-xs text-[#6E6259] hover:text-[#29231F]"
              >
                Cancel
              </button>
              <button
                onClick={handleSubmitRating}
                className="px-4 py-2 rounded-lg bg-[#5A3E2B] hover:bg-[#432E20] text-white text-xs font-semibold cursor-pointer shadow-xs"
              >
                Submit Performance Review
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
