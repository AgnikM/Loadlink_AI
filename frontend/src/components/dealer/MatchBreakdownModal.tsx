"use client";

import React, { useState } from "react";
import { X, CheckCircle2, Shield, Truck, Zap, Navigation, Award, IndianRupee, ArrowRight, ArrowLeftRight } from "lucide-react";
import { Match, Load } from "@/types";
import { api } from "@/lib/api";

interface MatchBreakdownModalProps {
  isOpen: boolean;
  onClose: () => void;
  match: Match | null;
  load: Load | null;
  onBookingCreated: () => void;
}

export default function MatchBreakdownModal({
  isOpen,
  onClose,
  match,
  load,
  onBookingCreated,
}: MatchBreakdownModalProps) {
  const [offeredPrice, setOfferedPrice] = useState(
    match && load ? (load.target_budget || load.estimated_benchmark_price || 19500) : 19500
  );
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [successState, setSuccessState] = useState(false);

  if (!isOpen || !match || !load) return null;

  const handleSendBooking = async () => {
    setIsSubmitting(true);
    try {
      await api.createBooking({
        load_id: load.id,
        truck_id: match.truck_id,
        offered_price: Number(offeredPrice),
      });
      setSuccessState(true);
      setTimeout(() => {
        setSuccessState(false);
        onBookingCreated();
        onClose();
      }, 1400);
    } catch (err: any) {
      alert(err.message || "Failed to create booking request");
    } finally {
      setIsSubmitting(false);
    }
  };

  const factors = [
    {
      key: "route_compatibility",
      label: "Route Alignment (Corridor Angle)",
      weight: "25%",
      score: match.factor_breakdown.route_compatibility,
      icon: <Navigation className="w-4 h-4 text-[#5A3E2B]" />,
      desc: "Directional highway congruence along freight corridor",
    },
    {
      key: "availability_feasibility",
      label: "Availability / Window Feasibility",
      weight: "20%",
      score: match.factor_breakdown.availability_feasibility,
      icon: <Zap className="w-4 h-4 text-[#3F7D58]" />,
      desc: "ETA margin before pickup gate window closes",
    },
    {
      key: "pickup_proximity",
      label: "Pickup Proximity (Road Distance)",
      weight: "15%",
      score: match.factor_breakdown.pickup_proximity,
      icon: <Truck className="w-4 h-4 text-[#B7791F]" />,
      desc: `${match.road_eta_km} km to pickup facility (${match.road_eta_mins} mins)`,
    },
    {
      key: "capacity_fit",
      label: "Capacity Utilization Fit",
      weight: "10%",
      score: match.factor_breakdown.capacity_fit,
      icon: <Shield className="w-4 h-4 text-[#5A3E2B]" />,
      desc: `${load.cargo_weight_tons}T load on ${match.truck_capacity_tons}T vehicle`,
    },
    {
      key: "price_competitiveness",
      label: "Freight Price Efficiency",
      weight: "10%",
      score: match.factor_breakdown.price_competitiveness,
      icon: <IndianRupee className="w-4 h-4 text-[#8A796B]" />,
      desc: "Corridor rate index benchmark congruence",
    },
    {
      key: "reliability",
      label: match.is_demo ? "Synthetic Carrier Reliability (Demo)" : "Historical Carrier Reliability",
      weight: "10%",
      score: match.factor_breakdown.reliability,
      icon: <Award className="w-4 h-4 text-[#3F7D58]" />,
      desc: match.is_demo
        ? `${match.driver_reliability_score}% synthetic demo metric (unverified)`
        : `${match.driver_reliability_score}% verified on-time delivery metric`,
    },
    {
      key: "return_load_potential",
      label: "Empty Return Load Potential",
      weight: "10%",
      score: match.factor_breakdown.return_load_potential,
      icon: <ArrowLeftRight className="w-4 h-4 text-[#B7791F]" />,
      desc: "Elimination of deadhead miles back to home depot",
    },
  ];

  return (
    <div
      onWheel={(e) => e.stopPropagation()}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-xs p-4 overflow-y-auto"
    >
      <div className="bg-[#FFFFFF] border border-[#E6DED5] rounded-2xl max-w-2xl w-full p-6 shadow-2xl relative my-8 isolate">
        {/* Header */}
        <div className="flex items-start justify-between pb-4 border-b border-[#E6DED5]">
          <div>
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-xs font-mono font-bold px-2 py-0.5 rounded bg-[#F0EAE1] text-[#5A3E2B] border border-[#E6DED5]">
                {match.truck_registration_no}
              </span>
              <span className="text-xs text-[#6E6259]">
                Driver: <strong className="text-[#29231F]">{match.driver_name}</strong>
              </span>
              {match.is_demo && (
                <span className="px-2 py-0.5 rounded bg-[#EFF6FF] border border-[#BFDBFE] text-[10px] text-[#1E40AF] font-bold inline-flex items-center gap-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-[#3B82F6]" />
                  DEMO DATA · Unverified
                </span>
              )}
            </div>
            <h2 className="text-base font-bold text-[#29231F] mt-1">
              Deterministic 7-Factor Score Breakdown
            </h2>
          </div>

          <div className="flex items-center gap-4">
            <div className="text-right">
              <span className="text-2xl font-black font-mono text-[#3F7D58]">
                {match.total_score}
              </span>
              <span className="text-xs text-[#8A796B] font-mono">/100</span>
              <p className="text-[10px] text-[#6E6259]">Composite Fit</p>
            </div>

            <button
              onClick={onClose}
              className="text-[#8A796B] hover:text-[#29231F] p-1.5 rounded-lg hover:bg-[#F7F5F0] transition"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Human-Readable Explanation Summary */}
        <div className="mt-4 p-3.5 bg-[#F7F5F0] border border-[#E6DED5] rounded-xl text-xs text-[#29231F] leading-relaxed">
          <p className="font-semibold text-[#5A3E2B] mb-1 flex items-center gap-1.5">
            <span>Algorithm Match Rationale</span>
          </p>
          <p className="text-[#6E6259]">{match.explanation_summary}</p>
        </div>

        {/* 7 Factors Grid */}
        <div className="mt-4 space-y-2.5 max-h-72 overflow-y-auto pr-1">
          {factors.map((f) => (
            <div
              key={f.key}
              className="p-3 bg-[#FFFFFF] border border-[#E6DED5] rounded-xl flex items-center justify-between gap-3 hover:border-[#C8BDB0] transition shadow-xs"
            >
              <div className="flex items-center gap-2.5 flex-1 min-w-0">
                <div className="w-7 h-7 rounded-lg bg-[#F7F5F0] border border-[#E6DED5] flex items-center justify-center flex-shrink-0">
                  {f.icon}
                </div>
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-semibold text-[#29231F] truncate">
                      {f.label}
                    </span>
                    <span className="text-[10px] font-mono font-medium text-[#8A796B]">
                      (wt {f.weight})
                    </span>
                  </div>
                  <p className="text-[11px] text-[#6E6259] truncate">{f.desc}</p>
                </div>
              </div>

              {/* Progress Bar & Numeric Score */}
              <div className="flex items-center gap-3 w-32 flex-shrink-0">
                <div className="w-full bg-[#F0EAE1] h-2 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-[#5A3E2B] rounded-full transition-all duration-500"
                    style={{ width: `${Math.min(100, Math.max(0, f.score))}%` }}
                  />
                </div>
                <span className="text-xs font-mono font-bold text-[#29231F] w-9 text-right">
                  {Math.round(f.score)}
                </span>
              </div>
            </div>
          ))}
        </div>

        {/* Booking Offer Action Section */}
        <div className="mt-5 pt-4 border-t border-[#E6DED5] flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2.5 w-full sm:w-auto">
            <span className="text-xs font-semibold text-[#29231F]">Offered Freight:</span>
            <div className="relative">
              <IndianRupee className="w-3.5 h-3.5 text-[#8A796B] absolute left-2.5 top-2.5" />
              <input
                type="number"
                step="500"
                value={offeredPrice}
                onChange={(e) => setOfferedPrice(Number(e.target.value))}
                className="w-36 bg-[#F7F5F0] border border-[#E6DED5] rounded-lg pl-7 pr-3 py-1.5 text-xs font-bold font-mono text-[#29231F] focus:outline-none focus:border-[#5A3E2B]"
              />
            </div>
          </div>

          <div className="flex items-center gap-3 w-full sm:w-auto justify-end">
            <button
              onClick={onClose}
              className="px-4 py-2 text-xs font-semibold text-[#6E6259] hover:text-[#29231F] transition"
            >
              Cancel
            </button>

            <button
              onClick={handleSendBooking}
              disabled={isSubmitting || successState}
              className={`flex items-center gap-2 px-5 py-2.5 rounded-lg text-white font-semibold text-xs transition shadow-xs cursor-pointer ${
                successState
                  ? "bg-[#3F7D58]"
                  : "bg-[#5A3E2B] hover:bg-[#432E20]"
              }`}
            >
              {successState ? (
                <>
                  <CheckCircle2 className="w-4 h-4" />
                  <span>Booking Request Sent!</span>
                </>
              ) : isSubmitting ? (
                <>
                  <div className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                  <span>Dispatching...</span>
                </>
              ) : (
                <>
                  <span>Send Booking Request</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
