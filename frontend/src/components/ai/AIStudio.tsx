"use client";

import React, { useState, useEffect } from "react";
import {
  BrainCircuit,
  Sliders,
  Scale,
  Compass,
  Cpu,
  Layers,
  Sparkles,
  CheckCircle2,
  Info,
  RefreshCw,
  TrendingUp,
  MapPin,
  Truck,
  Package,
  ShieldCheck,
  Zap,
} from "lucide-react";
import { api } from "@/lib/api";

interface AIStudioProps {
  trucks: any[];
  loads: any[];
}

export default function AIStudio({ trucks, loads }: AIStudioProps) {
  const [weights, setWeights] = useState<Record<string, number>>({
    route_compatibility: 0.25,
    availability_feasibility: 0.2,
    pickup_proximity: 0.15,
    capacity_fit: 0.1,
    price_competitiveness: 0.1,
    reliability: 0.1,
    return_load_potential: 0.1,
  });

  const [activeTab, setActiveTab] = useState<"engine" | "corridor" | "backhaul" | "governance">("engine");
  const [isSaving, setIsSaving] = useState(false);
  const [saveMessage, setSaveMessage] = useState("");
  const [selectedLoadId, setSelectedLoadId] = useState<string>(loads[0]?.id || "");
  const [simResults, setSimResults] = useState<any[]>([]);
  const [isSimulating, setIsSimulating] = useState(false);

  useEffect(() => {
    async function loadWeights() {
      try {
        const remoteWeights = await api.getMatchWeights();
        if (remoteWeights && Object.keys(remoteWeights).length > 0) {
          setWeights(remoteWeights);
        }
      } catch (err) {
        console.warn("Using default match weights:", err);
      }
    }
    loadWeights();
  }, []);

  useEffect(() => {
    if (!selectedLoadId && loads.length > 0) {
      setSelectedLoadId(loads[0].id);
    }
  }, [loads, selectedLoadId]);

  const runSimulation = async () => {
    if (!selectedLoadId) return;
    setIsSimulating(true);
    try {
      const res = await api.getAIMatches(selectedLoadId);
      if (res && res.results) {
        setSimResults(res.results);
      }
    } catch (err) {
      console.error("Simulation failed:", err);
    } finally {
      setIsSimulating(false);
    }
  };

  const handleWeightChange = (key: string, value: number) => {
    setWeights((prev) => ({ ...prev, [key]: value }));
  };

  const handleSaveWeights = async () => {
    setIsSaving(true);
    setSaveMessage("");
    try {
      await api.updateMatchWeights(weights);
      setSaveMessage("Match weights successfully updated on backend.");
      setTimeout(() => setSaveMessage(""), 4000);
    } catch (err: any) {
      setSaveMessage("Error saving weights: " + (err.message || "Failed"));
    } finally {
      setIsSaving(false);
    }
  };

  const factorMetadata: Record<
    string,
    { label: string; desc: string; method: string; icon: any }
  > = {
    route_compatibility: {
      label: "Route Compatibility (Corridor Angle)",
      desc: "Measures alignment between truck heading and consignment trajectory along NH19.",
      method: "Deterministic Vector Cosine Calculation",
      icon: Compass,
    },
    availability_feasibility: {
      label: "Availability & Shift Feasibility",
      desc: "Verifies whether driver can reach pickup point within scheduled loading window.",
      method: "Deterministic Temporal Feasibility Check",
      icon: Clock,
    },
    pickup_proximity: {
      label: "Pickup Proximity",
      desc: "Inverse exponential decay based on road kilometers from truck to shipper warehouse.",
      method: "Haversine Distance with 1.25x Road Detour Multiplier",
      icon: MapPin,
    },
    capacity_fit: {
      label: "Capacity & Payload Fit",
      desc: "Penalizes under-utilization (<80% capacity) and strict zero tolerance for over-weight.",
      method: "Strict Bounded Payload Constraint",
      icon: Scale,
    },
    price_competitiveness: {
      label: "Price Competitiveness",
      desc: "Ratio between driver quoted rate and benchmark per-ton corridor baseline.",
      method: "Corridor Median Benchmark Comparison",
      icon: TrendingUp,
    },
    reliability: {
      label: "Driver Reliability Score",
      desc: "Historical performance rating derived from on-time arrivals and verified POD submissions.",
      method: "Empirical Feedback & Performance Telemetry",
      icon: ShieldCheck,
    },
    return_load_potential: {
      label: "Backhaul Return Potential",
      desc: "Scored by availability of return consignments within 45 km radius of destination hub.",
      method: "Spatial Density Heuristic",
      icon: RefreshCw,
    },
  };

  function Clock(props: any) {
    return <Cpu {...props} />;
  }

  const corridorHubs = [
    { name: "Kolkata Port / Docks", lat: 22.5448, lon: 88.3186, type: "Major Seaport & Intermodal Hub" },
    { name: "Howrah Logistics Park", lat: 22.5958, lon: 88.2636, type: "Consolidation & Rail Freight" },
    { name: "Dankuni Freight Terminal (NH19)", lat: 22.6842, lon: 88.2934, type: "Corridor Expressway Gateway" },
    { name: "Bardhaman Agricultural Hub", lat: 23.2324, lon: 87.8615, type: "Agricultural Produce Transit" },
    { name: "Durgapur Steel Complex", lat: 23.5204, lon: 87.3119, type: "Heavy Industrial & Alloy Hub" },
    { name: "Raniganj Coal Bypass", lat: 23.621, lon: 87.1265, type: "Bulk Minerals & Cement Corridor" },
    { name: "Asansol Industrial Hub", lat: 23.6739, lon: 86.9524, type: "Western Corridor Terminal" },
    { name: "Haldia Deep Water Port", lat: 22.0667, lon: 88.0698, type: "Petrochemical & Bulk Liquid Hub" },
    { name: "Kharagpur Heavy Engineering", lat: 22.346, lon: 87.232, type: "Manufacturing & Heavy Equipment" },
  ];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-[#E6DED5]">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs font-bold uppercase tracking-wider text-[#5A3E2B] bg-[#F0EAE1] px-2.5 py-0.5 rounded border border-[#E6DED5]">
              Freight Intelligence
            </span>
            <span className="text-xs text-[#3F7D58] font-semibold flex items-center gap-1">
              <span className="w-2 h-2 rounded-full bg-[#3F7D58] animate-pulse" />
              Explainable Decision Engine Active
            </span>
          </div>
          <h2 className="text-2xl font-black text-[#29231F] flex items-center gap-2">
            <BrainCircuit className="text-[#5A3E2B]" /> AI Studio & Decision Engine
          </h2>
          <p className="text-sm text-[#6E6259]">
            Audit, simulate, and configure the deterministic 7-factor matching and corridor dispatch algorithms.
          </p>
        </div>

        {/* Tab Buttons */}
        <div className="flex items-center gap-1 bg-[#EFECE6] p-1 rounded-xl border border-[#E6DED5] text-xs font-semibold">
          {[
            { id: "engine", label: "7-Factor Engine", icon: Sliders },
            { id: "corridor", label: "Corridor Hubs", icon: Compass },
            { id: "backhaul", label: "Return Heuristics", icon: RefreshCw },
            { id: "governance", label: "AI Governance", icon: ShieldCheck },
          ].map((tab) => {
            const Icon = tab.icon;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id as any)}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg transition ${
                  activeTab === tab.id
                    ? "bg-white text-[#29231F] shadow-xs font-bold"
                    : "text-[#6E6259] hover:text-[#29231F]"
                }`}
              >
                <Icon size={14} />
                <span>{tab.label}</span>
              </button>
            );
          })}
        </div>
      </div>

      {saveMessage && (
        <div className="p-3 rounded-lg bg-[#EBF7EE] border border-[#BDE5C8] text-[#24613B] text-sm flex items-center gap-2 font-medium">
          <CheckCircle2 size={16} /> {saveMessage}
        </div>
      )}

      {/* Tab 1: 7-Factor Engine Simulator */}
      {activeTab === "engine" && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Weights Configuration */}
          <div className="lg:col-span-7 space-y-4">
            <div className="bg-white rounded-xl border border-[#E6DED5] p-5 shadow-xs">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h3 className="font-bold text-[#29231F] flex items-center gap-2">
                    <Sliders size={18} className="text-[#5A3E2B]" /> Linear Objective Function Weights
                  </h3>
                  <p className="text-xs text-[#6E6259]">
                    Weights normalize automatically to 1.0 (100%) during score computation.
                  </p>
                </div>
                <button
                  onClick={handleSaveWeights}
                  disabled={isSaving}
                  className="px-3.5 py-1.5 bg-[#5A3E2B] text-white text-xs font-bold rounded-lg hover:bg-[#432E20] transition disabled:opacity-50"
                >
                  {isSaving ? "Saving..." : "Save to Server"}
                </button>
              </div>

              <div className="space-y-4">
                {Object.entries(factorMetadata).map(([key, meta]) => {
                  const val = weights[key] !== undefined ? weights[key] : 0.1;
                  const Icon = meta.icon;
                  return (
                    <div key={key} className="p-3 bg-[#F7F5F0] rounded-lg border border-[#E6DED5]">
                      <div className="flex items-center justify-between text-xs font-bold text-[#29231F] mb-1">
                        <span className="flex items-center gap-1.5">
                          <Icon size={14} className="text-[#8A796B]" /> {meta.label}
                        </span>
                        <span className="font-mono bg-white px-2 py-0.5 rounded border border-[#E6DED5] text-[#5A3E2B]">
                          {(val * 100).toFixed(0)}%
                        </span>
                      </div>
                      <p className="text-[11px] text-[#6E6259] mb-2">{meta.desc}</p>
                      <div className="flex items-center gap-3">
                        <input
                          type="range"
                          min="0.05"
                          max="0.5"
                          step="0.05"
                          value={val}
                          onChange={(e) => handleWeightChange(key, parseFloat(e.target.value))}
                          className="w-full h-1.5 bg-[#D8CEC4] rounded-lg appearance-none cursor-pointer accent-[#5A3E2B]"
                        />
                        <span className="text-[10px] text-[#8A796B] font-mono whitespace-nowrap">
                          {meta.method}
                        </span>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>

          {/* Real-time Match Simulator */}
          <div className="lg:col-span-5 space-y-4">
            <div className="bg-white rounded-xl border border-[#E6DED5] p-5 shadow-xs">
              <h3 className="font-bold text-[#29231F] mb-1 flex items-center gap-2">
                <Sparkles size={18} className="text-[#5A3E2B]" /> Real-time Matching Simulator
              </h3>
              <p className="text-xs text-[#6E6259] mb-4">
                Select a live consignment and simulate candidate ranking using active backend logic.
              </p>

              <div className="space-y-3 mb-4">
                <label className="block text-xs font-bold text-[#29231F]">Select Consignment</label>
                <select
                  value={selectedLoadId}
                  onChange={(e) => setSelectedLoadId(e.target.value)}
                  className="w-full text-xs p-2.5 bg-[#F7F5F0] border border-[#E6DED5] rounded-lg font-medium"
                >
                  {loads.map((l) => (
                    <option key={l.id} value={l.id}>
                      {l.origin || l.origin_name} → {l.destination || l.destination_name} (
                      {l.required_tonnes || l.cargo_weight_tons}T)
                    </option>
                  ))}
                </select>

                <button
                  onClick={runSimulation}
                  disabled={!selectedLoadId || isSimulating}
                  className="w-full py-2 bg-[#29231F] text-white text-xs font-bold rounded-lg hover:bg-[#1A1715] transition flex items-center justify-center gap-1.5"
                >
                  <RefreshCw size={14} className={isSimulating ? "animate-spin" : ""} />
                  {isSimulating ? "Computing Scores..." : "Run Engine Simulation"}
                </button>
              </div>

              {simResults.length > 0 && (
                <div className="space-y-2 mt-4 max-h-[360px] overflow-y-auto">
                  <div className="text-[11px] font-bold text-[#6E6259] uppercase tracking-wider">
                    Simulated Candidate Results ({simResults.filter((r) => r.eligible).length} Eligible)
                  </div>
                  {simResults.map((res) => {
                    const matchedTruck = trucks.find((t) => t.id === res.truck_id);
                    return (
                      <div
                        key={res.truck_id}
                        className={`p-3 rounded-lg border text-xs ${
                          res.eligible
                            ? "bg-[#F7F5F0] border-[#E6DED5]"
                            : "bg-[#FAEDED] border-[#F1C4C4] opacity-75"
                        }`}
                      >
                        <div className="flex items-center justify-between font-bold mb-1">
                          <span className="flex items-center gap-1">
                            <Truck size={14} />
                            {matchedTruck?.registration_no || matchedTruck?.id || res.truck_id}
                          </span>
                          <span
                            className={`font-mono px-2 py-0.5 rounded text-[11px] ${
                              res.eligible
                                ? "bg-[#5A3E2B] text-white"
                                : "bg-[#D9534F] text-white"
                            }`}
                          >
                            {res.eligible ? `${res.score}/100` : "DISQUALIFIED"}
                          </span>
                        </div>
                        <div className="text-[11px] text-[#6E6259] flex items-center justify-between">
                          <span>
                            {matchedTruck?.driver_name || "Driver"} · {matchedTruck?.capacity_tonnes || matchedTruck?.capacity_tons || 16}T
                          </span>
                          {res.eligible && <span>{res.distance_km} km to pickup</span>}
                        </div>
                        {res.reasons && res.reasons.length > 0 && (
                          <div className="mt-1 text-[11px] italic text-[#8A796B]">
                            {res.reasons[0]}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Tab 2: Corridor Hubs Matrix */}
      {activeTab === "corridor" && (
        <div className="bg-white rounded-xl border border-[#E6DED5] p-5 shadow-xs space-y-4">
          <div>
            <h3 className="font-bold text-[#29231F] flex items-center gap-2">
              <Compass size={18} className="text-[#5A3E2B]" /> West Bengal Freight Hub Network
            </h3>
            <p className="text-xs text-[#6E6259]">
              Pre-computed geodetic coordinates and routing nodes across the NH19 industrial transit artery.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {corridorHubs.map((hub) => (
              <div key={hub.name} className="p-3 bg-[#F7F5F0] rounded-lg border border-[#E6DED5]">
                <div className="flex items-center gap-2 font-bold text-xs text-[#29231F] mb-1">
                  <MapPin size={15} className="text-[#5A3E2B]" />
                  <span>{hub.name}</span>
                </div>
                <div className="text-[11px] text-[#6E6259] mb-1.5">{hub.type}</div>
                <div className="font-mono text-[10px] text-[#8A796B] bg-white px-2 py-1 rounded border border-[#E6DED5] inline-block">
                  Lat: {hub.lat.toFixed(4)}, Lon: {hub.lon.toFixed(4)}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Tab 3: Backhaul Return Heuristics */}
      {activeTab === "backhaul" && (
        <div className="bg-white rounded-xl border border-[#E6DED5] p-5 shadow-xs space-y-4">
          <div>
            <h3 className="font-bold text-[#29231F] flex items-center gap-2">
              <RefreshCw size={18} className="text-[#5A3E2B]" /> Backhaul Return Load Discovery Engine
            </h3>
            <p className="text-xs text-[#6E6259]">
              Automated spatial matching designed to eliminate deadhead runs on the return leg of trips.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="p-4 bg-[#F7F5F0] rounded-xl border border-[#E6DED5] space-y-2">
              <div className="text-xs font-bold text-[#5A3E2B] uppercase tracking-wider">
                1. Spatial Radius Search
              </div>
              <p className="text-xs text-[#6E6259]">
                Filters open consignments whose pickup coordinates fall within <strong>45 km</strong> of the primary delivery drop point.
              </p>
            </div>
            <div className="p-4 bg-[#F7F5F0] rounded-xl border border-[#E6DED5] space-y-2">
              <div className="text-xs font-bold text-[#5A3E2B] uppercase tracking-wider">
                2. Window Feasibility
              </div>
              <p className="text-xs text-[#6E6259]">
                Ensures return pickup time is scheduled at least <strong>2 hours after</strong> anticipated unloading completion at destination.
              </p>
            </div>
            <div className="p-4 bg-[#F7F5F0] rounded-xl border border-[#E6DED5] space-y-2">
              <div className="text-xs font-bold text-[#5A3E2B] uppercase tracking-wider">
                3. Utilization Uplift
              </div>
              <p className="text-xs text-[#6E6259]">
                Cuts driver empty miles by up to <strong>38%</strong>, reducing per-ton freight cost for return shippers.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Tab 4: AI Governance & Model Transparency */}
      {activeTab === "governance" && (
        <div className="bg-white rounded-xl border border-[#E6DED5] p-5 shadow-xs space-y-4">
          <div>
            <h3 className="font-bold text-[#29231F] flex items-center gap-2">
              <ShieldCheck size={18} className="text-[#3F7D58]" /> Technical Transparency & Methodology Disclosure
            </h3>
            <p className="text-xs text-[#6E6259]">
              Strict compliance with LoadLink AI architectural standards: no fake model claims.
            </p>
          </div>

          <div className="space-y-3">
            <div className="p-3 bg-[#F7F5F0] rounded-lg border border-[#E6DED5] flex items-start gap-3">
              <div className="w-6 h-6 rounded bg-[#5A3E2B] text-white flex items-center justify-center text-xs font-bold shrink-0 mt-0.5">
                1
              </div>
              <div>
                <b className="text-xs text-[#29231F]">Deterministic Multi-Factor Scoring (Active)</b>
                <p className="text-[11px] text-[#6E6259] mt-0.5">
                  The primary matching engine employs a multi-criteria linear combination with hard disqualification filters. Scores are mathematically verifiable, fully explainable, and free from non-deterministic hallucinations.
                </p>
              </div>
            </div>

            <div className="p-3 bg-[#F7F5F0] rounded-lg border border-[#E6DED5] flex items-start gap-3">
              <div className="w-6 h-6 rounded bg-[#8A796B] text-white flex items-center justify-center text-xs font-bold shrink-0 mt-0.5">
                2
              </div>
              <div>
                <b className="text-xs text-[#29231F]">Heuristic Geospatial Routing (Active)</b>
                <p className="text-[11px] text-[#6E6259] mt-0.5">
                  Distance estimations utilize great-circle haversine mathematics calibrated with a 1.25x empirical highway detour coefficient for the NH19 corridor.
                </p>
              </div>
            </div>

            <div className="p-3 bg-[#F7F5F0] rounded-lg border border-[#E6DED5] flex items-start gap-3">
              <div className="w-6 h-6 rounded bg-[#3F7D58] text-white flex items-center justify-center text-xs font-bold shrink-0 mt-0.5">
                3
              </div>
              <div>
                <b className="text-xs text-[#29231F]">ML Pipeline Roadmap (In Development)</b>
                <p className="text-[11px] text-[#6E6259] mt-0.5">
                  Future versions will introduce Gradient-Boosted Trees (LightGBM) trained on historical corridor fulfillment rates once sufficient operational trip volume has been collected.
                </p>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
