"use client";

import React, { useState } from "react";
import { X, Sparkles, MapPin, Weight, Truck, IndianRupee, AlertCircle } from "lucide-react";
import { api } from "@/lib/api";
import { TruckType } from "@/types";

interface PostLoadModalProps {
  isOpen: boolean;
  onClose: () => void;
  onLoadCreated: (load: any) => void;
}

const CORRIDOR_HUBS = [
  { name: "Kolkata Port Docks (Warehouse 4)", lat: 22.5448, lon: 88.3186 },
  { name: "Howrah Logistics Park (Dhulagarh)", lat: 22.5892, lon: 88.2163 },
  { name: "Dankuni Industrial Freight Hub (NH19)", lat: 22.6842, lon: 88.2934 },
  { name: "Durgapur Steel Complex (Gate 2)", lat: 23.5204, lon: 87.3119 },
  { name: "Asansol Industrial Estate (Gate 1)", lat: 23.6739, lon: 86.9524 },
  { name: "Raniganj Coal & Cement Bypass", lat: 23.6210, lon: 87.1265 },
  { name: "Bardhaman Grain & Agro Terminal", lat: 23.2324, lon: 87.8615 },
  { name: "Haldia Port Petrochemical Hub", lat: 22.0644, lon: 88.0872 },
  { name: "Kharagpur Heavy Engineering Hub", lat: 22.3460, lon: 87.2320 },
  { name: "Siliguri North Bengal Gateway", lat: 26.7271, lon: 88.3953 },
  { name: "Malda Distribution Depot", lat: 25.0108, lon: 88.1411 },
];

export default function PostLoadModal({ isOpen, onClose, onLoadCreated }: PostLoadModalProps) {
  const [originIndex, setOriginIndex] = useState(0);
  const [destIndex, setDestIndex] = useState(3); // Durgapur Steel Complex
  const [cargoType, setCargoType] = useState("TMT Steel Billets");
  const [cargoWeightTons, setCargoWeightTons] = useState(16.0);
  const [truckType, setTruckType] = useState<TruckType>("OPEN_BODY");
  const [targetBudget, setTargetBudget] = useState(19500);
  const [cargoNotes, setCargoNotes] = useState("Industrial consignment. Requires crane offloading and valid e-Way bill.");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState("");

  if (!isOpen) return null;

  // Approximate live corridor distance & benchmark preview
  const origin = CORRIDOR_HUBS[originIndex];
  const destination = CORRIDOR_HUBS[destIndex];
  const approxDistanceKm = Math.round(
    Math.sqrt(
      Math.pow((destination.lat - origin.lat) * 111, 2) +
      Math.pow((destination.lon - origin.lon) * 111, 2)
    ) * 1.22
  );
  const benchmarkMedian = Math.round(2800 + approxDistanceKm * cargoWeightTons * 3.75);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg("");

    if (originIndex === destIndex) {
      setErrorMsg("Origin and Destination cannot be the exact same location.");
      return;
    }

    setIsSubmitting(true);
    try {
      const now = new Date();
      const pickupStart = new Date(now.getTime() + 2 * 60 * 60 * 1000); // +2 hours
      const pickupEnd = new Date(now.getTime() + 8 * 60 * 60 * 1000); // +8 hours

      const payload = {
        origin_name: origin.name,
        origin_lat: origin.lat,
        origin_lon: origin.lon,
        destination_name: destination.name,
        destination_lat: destination.lat,
        destination_lon: destination.lon,
        cargo_type: cargoType,
        cargo_weight_tons: Number(cargoWeightTons),
        required_truck_type: truckType,
        min_capacity_tons: Math.max(5.0, Number(cargoWeightTons) - 2),
        max_capacity_tons: Number(cargoWeightTons) + 8,
        pickup_window_start: pickupStart.toISOString(),
        pickup_window_end: pickupEnd.toISOString(),
        target_budget: Number(targetBudget),
        cargo_notes: cargoNotes,
      };

      const created = await api.createLoad(payload);
      // Auto-trigger deterministic match engine for the newly posted load
      try {
        await api.generateMatches(created.id);
      } catch (err) {
        console.warn("Auto-match trigger warning:", err);
      }

      onLoadCreated(created);
      onClose();
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to post consignment");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div
      onWheel={(e) => e.stopPropagation()}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-xs p-4 overflow-y-auto"
    >
      <div className="bg-[#FFFFFF] border border-[#E6DED5] rounded-2xl max-w-xl w-full p-6 shadow-2xl relative my-8 isolate">
        {/* Header */}
        <div className="flex items-center justify-between pb-4 border-b border-[#E6DED5]">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-[#F0EAE1] flex items-center justify-center text-[#5A3E2B]">
              <Truck className="w-4 h-4" />
            </div>
            <div>
              <h2 className="text-base font-bold text-[#29231F]">Post New Freight Consignment</h2>
              <p className="text-xs text-[#6E6259]">
                West Bengal Multi-Hub Corridor • Instant Deterministic 7-Factor Ranking
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-[#8A796B] hover:text-[#29231F] p-1.5 rounded-lg hover:bg-[#F7F5F0] transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {errorMsg && (
          <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded-xl text-xs text-red-700 flex items-center gap-2">
            <AlertCircle className="w-4 h-4 flex-shrink-0" />
            <span>{errorMsg}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="mt-4 space-y-4">
          {/* Corridor Selection */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
            <div>
              <label className="block text-xs font-semibold text-[#29231F] mb-1">
                Pickup Origin Hub
              </label>
              <select
                value={originIndex}
                onChange={(e) => setOriginIndex(Number(e.target.value))}
                className="w-full bg-[#F7F5F0] border border-[#E6DED5] rounded-lg px-3 py-2 text-xs font-medium text-[#29231F] focus:outline-none focus:border-[#5A3E2B]"
              >
                {CORRIDOR_HUBS.map((hub, idx) => (
                  <option key={`orig-${hub.name}`} value={idx}>
                    {hub.name}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-xs font-semibold text-[#29231F] mb-1">
                Delivery Destination Hub
              </label>
              <select
                value={destIndex}
                onChange={(e) => setDestIndex(Number(e.target.value))}
                className="w-full bg-[#F7F5F0] border border-[#E6DED5] rounded-lg px-3 py-2 text-xs font-medium text-[#29231F] focus:outline-none focus:border-[#5A3E2B]"
              >
                {CORRIDOR_HUBS.map((hub, idx) => (
                  <option key={`dest-${hub.name}`} value={idx}>
                    {hub.name}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Cargo Details */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3.5">
            <div>
              <label className="block text-xs font-semibold text-[#29231F] mb-1">
                Commodity Type
              </label>
              <input
                type="text"
                value={cargoType}
                onChange={(e) => setCargoType(e.target.value)}
                placeholder="e.g. TMT Steel, Cement"
                className="w-full bg-[#F7F5F0] border border-[#E6DED5] rounded-lg px-3 py-2 text-xs font-medium text-[#29231F] focus:outline-none focus:border-[#5A3E2B]"
                required
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-[#29231F] mb-1">
                Payload Weight (Tons)
              </label>
              <input
                type="number"
                step="0.5"
                min="1"
                max="55"
                value={cargoWeightTons}
                onChange={(e) => setCargoWeightTons(Number(e.target.value))}
                className="w-full bg-[#F7F5F0] border border-[#E6DED5] rounded-lg px-3 py-2 text-xs font-medium text-[#29231F] focus:outline-none focus:border-[#5A3E2B]"
                required
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-[#29231F] mb-1">
                Vehicle Body Type
              </label>
              <select
                value={truckType}
                onChange={(e) => setTruckType(e.target.value as TruckType)}
                className="w-full bg-[#F7F5F0] border border-[#E6DED5] rounded-lg px-3 py-2 text-xs font-medium text-[#29231F] focus:outline-none focus:border-[#5A3E2B]"
              >
                <option value="OPEN_BODY">Open Body Truck</option>
                <option value="CONTAINER">Closed Container</option>
                <option value="FLATBED">Flatbed Trailer</option>
                <option value="TANKER">Bulk Liquid Tanker</option>
                <option value="TIPPER">Tipper / Dumper</option>
              </select>
            </div>
          </div>

          {/* Pricing & Estimation Widget */}
          <div className="bg-[#F7F5F0] border border-[#E6DED5] rounded-xl p-3.5 space-y-2">
            <div className="flex items-center justify-between text-xs">
              <span className="text-[#6E6259] font-medium flex items-center gap-1">
                <Sparkles className="w-3.5 h-3.5 text-[#B7791F]" />
                Estimated Corridor Benchmark:
              </span>
              <span className="font-mono font-bold text-[#3F7D58]">
                ₹{benchmarkMedian.toLocaleString("en-IN")} (~{approxDistanceKm} km)
              </span>
            </div>

            <div className="flex items-center gap-3">
              <label className="text-xs font-semibold text-[#29231F] whitespace-nowrap">
                Your Target Budget (₹):
              </label>
              <div className="relative flex-1">
                <IndianRupee className="w-3.5 h-3.5 text-[#8A796B] absolute left-3 top-2.5" />
                <input
                  type="number"
                  step="500"
                  min="1000"
                  value={targetBudget}
                  onChange={(e) => setTargetBudget(Number(e.target.value))}
                  className="w-full bg-[#FFFFFF] border border-[#E6DED5] rounded-lg pl-8 pr-3 py-1.5 text-xs font-bold font-mono text-[#29231F] focus:outline-none focus:border-[#5A3E2B]"
                  required
                />
              </div>
            </div>
          </div>

          {/* Handling & Special Instructions */}
          <div>
            <label className="block text-xs font-semibold text-[#29231F] mb-1">
              Handling & Consignment Notes
            </label>
            <textarea
              rows={2}
              value={cargoNotes}
              onChange={(e) => setCargoNotes(e.target.value)}
              className="w-full bg-[#F7F5F0] border border-[#E6DED5] rounded-lg px-3 py-2 text-xs font-medium text-[#29231F] focus:outline-none focus:border-[#5A3E2B]"
            />
          </div>

          {/* Actions */}
          <div className="flex items-center justify-end gap-3 pt-3 border-t border-[#E6DED5]">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-xs font-semibold text-[#6E6259] hover:text-[#29231F] transition"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting}
              className="flex items-center gap-2 px-5 py-2.5 rounded-lg bg-[#5A3E2B] hover:bg-[#432E20] text-white font-semibold text-xs transition shadow-xs disabled:opacity-50 cursor-pointer"
            >
              {isSubmitting ? (
                <>
                  <div className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                  <span>Matching Corridor Fleet...</span>
                </>
              ) : (
                <>
                  <Sparkles className="w-3.5 h-3.5" />
                  <span>Post & Find Matches</span>
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
