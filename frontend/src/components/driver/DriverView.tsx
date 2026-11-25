"use client";

import React, { useState, useEffect } from "react";
import { Truck, Radio, CheckCircle, XCircle, Navigation, MapPin, UploadCloud, IndianRupee, ShieldCheck, Sparkles, ArrowRight, ArrowLeftRight, Phone, Send, ShieldAlert, Wrench, RefreshCw, WifiOff } from "lucide-react";
import { Shipment, Booking, ReturnLoadOpportunity, TruckStatus } from "@/types";
import { api } from "@/lib/api";
import { OfflineStorageManager } from "@/lib/offlineStorage";
import DriverSOSModal from "@/components/driver/DriverSOSModal";
import DriverBreakdownModal from "@/components/driver/DriverBreakdownModal";
import PreTripInspectionModal from "@/components/driver/PreTripInspectionModal";

interface DriverViewProps {
  currentTruck: any;
  bookings: Booking[];
  activeShipment: Shipment | null;
  onRefresh: () => void;
  currentUser?: any;
}

export default function DriverView({
  currentTruck,
  bookings,
  activeShipment,
  onRefresh,
  currentUser,
}: DriverViewProps) {
  const [isOnline, setIsOnline] = useState(
    currentTruck ? currentTruck.status === "ONLINE_AVAILABLE" : true
  );
  const [returnLoads, setReturnLoads] = useState<ReturnLoadOpportunity[]>([]);
  const [isSubmittingState, setIsSubmittingState] = useState(false);
  const [isPingingGPS, setIsPingingGPS] = useState(false);

  // POD Form State
  const [podReceiverName, setPodReceiverName] = useState("Debabrata Ghosh (Site In-Charge)");
  const [podReceiverPhone, setPodReceiverPhone] = useState("+919876543210");
  const [podNotes, setPodNotes] = useState("Received 16T TMT steel billets in sound undamaged condition.");
  const [isUploadingPOD, setIsUploadingPOD] = useState(false);

  // Master Prompt 3 Modals & Offline States
  const [isSOSOpen, setIsSOSOpen] = useState(false);
  const [isBreakdownOpen, setIsBreakdownOpen] = useState(false);
  const [isInspectionOpen, setIsInspectionOpen] = useState(false);
  const [pendingOfflineCount, setPendingOfflineCount] = useState(0);
  const [isSyncingOffline, setIsSyncingOffline] = useState(false);

  useEffect(() => {
    setPendingOfflineCount(OfflineStorageManager.getPendingCount());
  }, []);

  const handleSyncOffline = async () => {
    setIsSyncingOffline(true);
    try {
      const { synced, failed } = await OfflineStorageManager.syncPendingQueue(api);
      alert(`Offline Sync Complete: ${synced} event(s) synced, ${failed} failed.`);
      setPendingOfflineCount(OfflineStorageManager.getPendingCount());
      onRefresh();
    } catch {
      alert("Offline sync failed. Check connectivity.");
    } finally {
      setIsSyncingOffline(false);
    }
  };

  // Toggle Driver Online / Offline Status
  const handleToggleOnline = async () => {
    if (!currentTruck) return;
    const nextStatus: TruckStatus = isOnline ? "OFFLINE" : "ONLINE_AVAILABLE";
    try {
      await api.updateTruckAvailability(currentTruck.id, nextStatus);
      setIsOnline(!isOnline);
      onRefresh();
    } catch (err: any) {
      alert(err.message || "Failed to update truck status");
    }
  };

  // Respond to Booking Request (ACCEPT / REJECT)
  const handleBookingResponse = async (bookingId: string, action: "ACCEPT" | "REJECT") => {
    try {
      await api.respondBooking(bookingId, action);
      alert(`Trip booking ${action === "ACCEPT" ? "Accepted! Shipment is now active." : "Declined."}`);
      onRefresh();
    } catch (err: any) {
      alert(err.message || "Failed to process booking");
    }
  };

  // State Machine Step Progression
  const handleAdvanceShipmentState = async () => {
    if (!activeShipment) return;
    setIsSubmittingState(true);

    const transitionMap: Record<string, string> = {
      CONFIRMED: "DRIVER_EN_ROUTE",
      DRIVER_EN_ROUTE: "ARRIVED_PICKUP",
      ARRIVED_PICKUP: "LOADING",
      LOADING: "LOADED",
      LOADED: "IN_TRANSIT",
      IN_TRANSIT: "NEAR_DESTINATION",
      NEAR_DESTINATION: "DELIVERED",
    };

    const nextState = transitionMap[activeShipment.state];
    if (!nextState) {
      setIsSubmittingState(false);
      return;
    }

    try {
      await api.transitionShipment(activeShipment.id, nextState);
      onRefresh();
    } catch (err: any) {
      alert(err.message || "Failed state transition");
    } finally {
      setIsSubmittingState(false);
    }
  };

  // Live GPS Step Simulator (moves truck coordinate along the corridor)
  const handleSimulateGPSMove = async () => {
    if (!activeShipment || !currentTruck) return;
    setIsPingingGPS(true);
    const curLat = activeShipment.current_lat || activeShipment.origin_lat || 22.5448;
    const curLon = activeShipment.current_lon || activeShipment.origin_lon || 88.3186;
    const destLat = activeShipment.destination_lat || 23.5204;
    const destLon = activeShipment.destination_lon || 87.3119;

    // Step 25% closer to destination
    const nextLat = curLat + (destLat - curLat) * 0.25;
    const nextLon = curLon + (destLon - curLon) * 0.25;

    try {
      await api.updateTruckLocation(currentTruck.id, {
        latitude: Number(nextLat.toFixed(4)),
        longitude: Number(nextLon.toFixed(4)),
        speed_kmh: 52.0,
        location_name: "NH19 Freight Corridor (Durgapur Expressway)",
      });
      onRefresh();
    } catch (err: any) {
      alert(err.message || "Failed to transmit GPS ping");
    } finally {
      setIsPingingGPS(false);
    }
  };

  // Fetch return loads when in transit or near destination
  useEffect(() => {
    if (activeShipment) {
      api.getReturnLoads(activeShipment.id)
        .then((data) => setReturnLoads(data))
        .catch(() => setReturnLoads([]));
    }
  }, [activeShipment]);

  // Submit Digital POD
  const handlePODUploadSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeShipment) return;
    setIsUploadingPOD(true);

    try {
      const formData = new FormData();
      formData.append("receiver_name", podReceiverName);
      formData.append("receiver_phone", podReceiverPhone);
      formData.append("receiver_signature_notes", podNotes);

      // Create a dummy image blob for browser demo
      const blob = new Blob(["SAMPLE_SIGNED_EPOD_RECEIPT_STAMPED_DURGAPUR_GATE_2"], {
        type: "text/plain",
      });
      formData.append("file", blob, "signed_epod_receipt.png");

      await api.submitPOD(activeShipment.id, formData);
      alert("Electronic Proof of Delivery (ePOD) uploaded! Consignment sent for dealer approval.");
      onRefresh();
    } catch (err: any) {
      alert(err.message || "Failed to upload POD");
    } finally {
      setIsUploadingPOD(false);
    }
  };

  const pendingBookings = bookings.filter((b) => b.status === "PENDING");

  const getNextActionLabel = (state: string) => {
    switch (state) {
      case "CONFIRMED":
        return "Start Trip (Depart to Pickup Facility)";
      case "DRIVER_EN_ROUTE":
        return "Mark Arrived at Pickup Gate";
      case "ARRIVED_PICKUP":
        return "Begin Consignment Loading";
      case "LOADING":
        return "Confirm Loading & Verify e-Way Bill";
      case "LOADED":
        return "Depart Pickup & Enter Highway (In Transit)";
      case "IN_TRANSIT":
        return "Approaching Delivery Hub (Near Destination)";
      case "NEAR_DESTINATION":
        return "Mark Delivered at Consignee Gate";
      default:
        return "Advance Consignment Stage";
    }
  };

  return (
    <div className="max-w-xl mx-auto space-y-5 pb-12">
      {/* Mobile Carrier Header Card */}
      <div className="bg-[#FFFFFF] border border-[#E6DED5] rounded-2xl p-5 shadow-xs relative overflow-hidden">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 rounded-xl bg-[#F0EAE1] border border-[#E6DED5] flex items-center justify-center text-[#5A3E2B]">
              <Truck className="w-6 h-6" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-base font-bold text-[#29231F]">
                  {currentTruck ? currentTruck.registration_no : "WB-19-AF-0184"}
                </h2>
                <span className="text-[10px] font-bold uppercase px-2 py-0.5 rounded-full bg-[#EBF5EE] text-[#3F7D58] border border-[#C6E6D0]">
                  {currentTruck?.driver_reliability_score || 96}% Trust Index
                </span>
              </div>
              <p className="text-xs text-[#6E6259] mt-0.5">
                Driver: {currentTruck?.driver_name || currentUser?.name || "Rajesh Yadav"} • {currentTruck ? `${currentTruck.capacity_tons}T ${(currentTruck.truck_type || "OPEN_BODY").replace(/_/g, " ")}` : "16T Multi-Axle Open Truck"}
              </p>
            </div>
          </div>

          {/* Online / Offline Switch */}
          <button
            onClick={handleToggleOnline}
            className={`flex items-center gap-1.5 px-3.5 py-1.5 rounded-full text-xs font-bold transition shadow-xs cursor-pointer ${
              isOnline
                ? "bg-[#3F7D58] text-white"
                : "bg-[#F7F5F0] text-[#6E6259] border border-[#E6DED5]"
            }`}
          >
            <Radio className={`w-3.5 h-3.5 ${isOnline ? "live-pulse text-white" : "text-[#8A796B]"}`} />
            <span>{isOnline ? "ONLINE" : "OFFLINE"}</span>
          </button>
        </div>
      </div>

      {/* Driver Safety & Emergency Command Row (Master Prompt 3) */}
      <div className="grid grid-cols-3 gap-2.5">
        <button
          type="button"
          onClick={() => setIsSOSOpen(true)}
          className="p-3 rounded-2xl bg-[#D9381E] hover:bg-[#B91C1C] text-white flex flex-col items-center justify-center gap-1 shadow-xs transition cursor-pointer"
        >
          <ShieldAlert className="w-5 h-5 text-white animate-pulse" />
          <span className="text-[11px] font-black uppercase tracking-wider">EMERGENCY SOS</span>
        </button>

        <button
          type="button"
          onClick={() => setIsBreakdownOpen(true)}
          className="p-3 rounded-2xl bg-[#FEF6E7] border border-[#FCDCA0] text-[#B7791F] hover:bg-[#FDEED3] flex flex-col items-center justify-center gap-1 shadow-xs transition cursor-pointer"
        >
          <Wrench className="w-5 h-5" />
          <span className="text-[11px] font-bold uppercase tracking-wider">BREAKDOWN</span>
        </button>

        <button
          type="button"
          onClick={() => setIsInspectionOpen(true)}
          className="p-3 rounded-2xl bg-[#EBF5EE] border border-[#C6E6D0] text-[#2E5A3F] hover:bg-[#DDF0E2] flex flex-col items-center justify-center gap-1 shadow-xs transition cursor-pointer"
        >
          <ShieldCheck className="w-5 h-5" />
          <span className="text-[11px] font-bold uppercase tracking-wider">PRE-TRIP CHECK</span>
        </button>
      </div>

      {/* Offline Sync Banner if pending offline events exist */}
      {pendingOfflineCount > 0 && (
        <div className="p-3 bg-[#FEF6E7] border border-[#FCDCA0] rounded-2xl flex items-center justify-between text-xs text-[#B7791F]">
          <div className="flex items-center gap-2">
            <WifiOff className="w-4 h-4 text-[#D97706]" />
            <span className="font-semibold">{pendingOfflineCount} offline event(s) queued locally.</span>
          </div>
          <button
            type="button"
            onClick={handleSyncOffline}
            disabled={isSyncingOffline}
            className="px-3 py-1 rounded-lg bg-[#D97706] text-white text-[10px] font-bold flex items-center gap-1 cursor-pointer disabled:opacity-50"
          >
            <RefreshCw className={`w-3 h-3 ${isSyncingOffline ? "animate-spin" : ""}`} />
            <span>Sync Now</span>
          </button>
        </div>
      )}

      {/* Incoming Trip Bookings (Requires Driver 1-Tap Acceptance) */}
      <div className="bg-[#FFFFFF] border border-[#E6DED5] rounded-2xl p-5 shadow-xs space-y-4">
        <div className="flex items-center justify-between border-b border-[#E6DED5] pb-3">
          <div className="flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-[#B7791F]" />
            <h3 className="text-xs font-bold uppercase tracking-wider text-[#29231F]">
              Direct Consignment Offers ({pendingBookings.length})
            </h3>
          </div>
          <span className="text-[10px] font-mono text-[#6E6259]">Instant Settlement</span>
        </div>

        {pendingBookings.length === 0 ? (
          <div className="py-6 text-center text-xs text-[#6E6259] bg-[#F7F5F0] rounded-xl border border-dashed border-[#E6DED5]">
            No pending trip dispatches. Keep GPS online to receive high-fit corridor consignments.
          </div>
        ) : (
          <div className="space-y-3">
            {pendingBookings.map((b) => (
              <div
                key={b.id}
                className="bg-[#F7F5F0] border border-[#E6DED5] rounded-xl p-4 space-y-3"
              >
                <div className="flex items-start justify-between">
                  <div>
                    <span className="text-xs font-bold text-[#29231F]">
                      Consignment #{b.load_id.slice(0, 8)}
                    </span>
                    <p className="text-[11px] text-[#6E6259]">
                      Shipper: Bengal Steel & Industrial Traders
                    </p>
                  </div>
                  <div className="text-right">
                    <span className="text-base font-bold font-mono text-[#3F7D58]">
                      ₹{b.offered_price.toLocaleString("en-IN")}
                    </span>
                    <p className="text-[10px] text-[#6E6259]">All-Inclusive Rate</p>
                  </div>
                </div>

                <div className="flex items-center gap-2 pt-2 border-t border-[#E6DED5]">
                  <button
                    onClick={() => handleBookingResponse(b.id, "REJECT")}
                    className="flex-1 py-2 rounded-lg border border-[#E6DED5] bg-white text-xs font-semibold text-[#6E6259] hover:bg-[#F0EAE1] transition cursor-pointer"
                  >
                    Decline
                  </button>
                  <button
                    onClick={() => handleBookingResponse(b.id, "ACCEPT")}
                    className="flex-1 py-2 rounded-lg bg-[#5A3E2B] hover:bg-[#432E20] text-xs font-bold text-white transition shadow-xs cursor-pointer flex items-center justify-center gap-1"
                  >
                    <CheckCircle className="w-3.5 h-3.5" />
                    <span>Accept Consignment</span>
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Active Trip Workflow Stepper */}
      {activeShipment && activeShipment.state !== "COMPLETED" && (
        <div className="bg-[#FFFFFF] border border-[#E6DED5] rounded-2xl p-5 shadow-xs space-y-4">
          <div className="flex items-center justify-between border-b border-[#E6DED5] pb-3">
            <div>
              <span className="text-[10px] uppercase font-bold text-[#8A796B]">Active Trip</span>
              <h3 className="text-sm font-bold text-[#29231F]">
                Shipment #{activeShipment.id.slice(0, 8)}
              </h3>
            </div>
            <span className="text-xs font-mono font-bold px-2.5 py-0.5 rounded-full bg-[#F0EAE1] text-[#5A3E2B] border border-[#E6DED5]">
              {activeShipment.state}
            </span>
          </div>

          <div className="space-y-1.5 text-xs text-[#6E6259]">
            <div className="flex items-center gap-2">
              <MapPin className="w-4 h-4 text-[#5A3E2B] flex-shrink-0" />
              <span className="font-semibold text-[#29231F]">{activeShipment.origin_name}</span>
            </div>
            <div className="pl-6 text-[11px] text-[#8A796B]">↓ via NH19 Corridor</div>
            <div className="flex items-center gap-2">
              <MapPin className="w-4 h-4 text-[#3F7D58] flex-shrink-0" />
              <span className="font-semibold text-[#29231F]">{activeShipment.destination_name}</span>
            </div>
          </div>

          {/* Stepper Advancement Action */}
          {activeShipment.state !== "DELIVERED" ? (
            <div className="space-y-2 pt-2">
              <button
                onClick={handleAdvanceShipmentState}
                disabled={isSubmittingState}
                className="w-full py-3 rounded-xl bg-[#5A3E2B] hover:bg-[#432E20] text-white font-bold text-xs shadow-xs transition flex items-center justify-center gap-2 cursor-pointer disabled:opacity-50"
              >
                {isSubmittingState ? (
                  <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                ) : (
                  <>
                    <span>{getNextActionLabel(activeShipment.state)}</span>
                    <ArrowRight className="w-4 h-4" />
                  </>
                )}
              </button>

              {/* Live GPS Telemetry Ping Trigger */}
              <button
                onClick={handleSimulateGPSMove}
                disabled={isPingingGPS}
                className="w-full py-2 rounded-xl bg-[#F7F5F0] hover:bg-[#EFECE6] border border-[#E6DED5] text-xs font-semibold text-[#29231F] transition flex items-center justify-center gap-2 cursor-pointer"
              >
                <Send className="w-3.5 h-3.5 text-[#5A3E2B]" />
                <span>{isPingingGPS ? "Broadcasting Telemetry..." : "Emit Real-Time GPS Signal (25% Forward)"}</span>
              </button>
            </div>
          ) : (
            <div className="p-3 bg-[#EBF5EE] border border-[#C6E6D0] rounded-xl text-xs text-[#3F7D58] font-semibold text-center">
              Consignment Delivered! Submit signed ePOD below to initiate instant payout.
            </div>
          )}
        </div>
      )}

      {/* Return-Load Opportunities (PRD Section 9: 0% Deadhead Matching) */}
      {activeShipment && returnLoads.length > 0 && (
        <div className="bg-[#FFFFFF] border border-[#E6DED5] rounded-2xl p-5 shadow-xs space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <ArrowLeftRight className="w-4 h-4 text-[#B7791F]" />
              <h3 className="text-xs font-bold uppercase tracking-wider text-[#29231F]">
                Backhaul Opportunities ({returnLoads.length})
              </h3>
            </div>
            <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-[#FEF6E7] text-[#B7791F] border border-[#FCDCA0]">
              Zero Deadhead
            </span>
          </div>

          <p className="text-xs text-[#6E6259]">
            Pre-matched return freight loading at your destination hub heading back to your home depot.
          </p>

          <div className="space-y-2.5">
            {returnLoads.map((rl) => (
              <div
                key={rl.load_id}
                className="p-3.5 bg-[#F7F5F0] border border-[#E6DED5] rounded-xl flex items-center justify-between"
              >
                <div>
                  <span className="text-xs font-bold text-[#29231F]">
                    {rl.cargo_type} ({rl.cargo_weight_tons}T)
                  </span>
                  <div className="text-[11px] text-[#6E6259]">
                    {rl.origin_name} → {rl.destination_name}
                  </div>
                </div>
                <div className="text-right">
                  <span className="text-xs font-bold font-mono text-[#3F7D58]">
                    ₹{(rl.target_budget || 17000).toLocaleString("en-IN")}
                  </span>
                  <p className="text-[10px] text-[#8A796B]">Ready for loading</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ePOD Upload Section */}
      {activeShipment && (activeShipment.state === "DELIVERED" || activeShipment.state === "NEAR_DESTINATION") && (
        <div className="bg-[#FFFFFF] border border-[#E6DED5] rounded-2xl p-5 shadow-xs space-y-4">
          <div className="flex items-center gap-2 border-b border-[#E6DED5] pb-3">
            <UploadCloud className="w-4 h-4 text-[#5A3E2B]" />
            <h3 className="text-xs font-bold uppercase tracking-wider text-[#29231F]">
              Submit Digital Proof of Delivery (ePOD)
            </h3>
          </div>

          <form onSubmit={handlePODUploadSubmit} className="space-y-3 text-xs">
            <div>
              <label className="block font-semibold text-[#29231F] mb-1">
                Receiving Authority / Site In-Charge Name
              </label>
              <input
                type="text"
                value={podReceiverName}
                onChange={(e) => setPodReceiverName(e.target.value)}
                className="w-full bg-[#F7F5F0] border border-[#E6DED5] rounded-lg px-3 py-2 font-medium text-[#29231F] focus:outline-none focus:border-[#5A3E2B]"
                required
              />
            </div>

            <div>
              <label className="block font-semibold text-[#29231F] mb-1">
                Consignee Mobile Number
              </label>
              <input
                type="text"
                value={podReceiverPhone}
                onChange={(e) => setPodReceiverPhone(e.target.value)}
                className="w-full bg-[#F7F5F0] border border-[#E6DED5] rounded-lg px-3 py-2 font-medium text-[#29231F] focus:outline-none focus:border-[#5A3E2B]"
                required
              />
            </div>

            <div>
              <label className="block font-semibold text-[#29231F] mb-1">
                Lorry Receipt Stamped Notes
              </label>
              <textarea
                rows={2}
                value={podNotes}
                onChange={(e) => setPodNotes(e.target.value)}
                className="w-full bg-[#F7F5F0] border border-[#E6DED5] rounded-lg px-3 py-2 font-medium text-[#29231F] focus:outline-none focus:border-[#5A3E2B]"
              />
            </div>

            <button
              type="submit"
              disabled={isUploadingPOD}
              className="w-full py-2.5 rounded-lg bg-[#3F7D58] hover:bg-[#346648] text-white font-bold text-xs shadow-xs transition flex items-center justify-center gap-1.5 cursor-pointer disabled:opacity-50"
            >
              {isUploadingPOD ? (
                <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
              ) : (
                <>
                  <UploadCloud className="w-4 h-4" />
                  <span>Upload Signed Consignment Receipt</span>
                </>
              )}
            </button>
          </form>
        </div>
      )}

      {/* Master Prompt 3 Modals */}
      <DriverSOSModal
        isOpen={isSOSOpen}
        onClose={() => setIsSOSOpen(false)}
        truckId={currentTruck?.id || "wb19af0184"}
        shipmentId={activeShipment?.id}
        bookingId={activeShipment?.booking_id}
        driverPhone={currentTruck?.driver_phone || currentUser?.phone}
        currentLat={activeShipment?.current_lat || activeShipment?.origin_lat || 22.5448}
        currentLon={activeShipment?.current_lon || activeShipment?.origin_lon || 88.3186}
      />

      <DriverBreakdownModal
        isOpen={isBreakdownOpen}
        onClose={() => setIsBreakdownOpen(false)}
        truckId={currentTruck?.id || "wb19af0184"}
        shipmentId={activeShipment?.id}
        currentLat={activeShipment?.current_lat || activeShipment?.origin_lat || 22.5448}
        currentLon={activeShipment?.current_lon || activeShipment?.origin_lon || 88.3186}
        onSuccess={() => {
          onRefresh();
          setPendingOfflineCount(OfflineStorageManager.getPendingCount());
        }}
      />

      <PreTripInspectionModal
        isOpen={isInspectionOpen}
        onClose={() => setIsInspectionOpen(false)}
        truckId={currentTruck?.id || "wb19af0184"}
        onSuccess={() => {
          onRefresh();
          setPendingOfflineCount(OfflineStorageManager.getPendingCount());
        }}
      />
    </div>
  );
}
