"use client";

import React, { useEffect, useMemo, useState } from "react";
import {
  Activity,
  ArrowDownUp,
  Bell,
  CheckCircle2,
  ChevronRight,
  CircleDollarSign,
  Clock3,
  LayoutDashboard,
  MapPin,
  Menu,
  Package,
  Plus,
  Search,
  Settings,
  ShieldCheck,
  Truck,
  Users,
  X,
  BrainCircuit,
  RefreshCw,
  Phone,
  Compass,
  AlertCircle,
  ExternalLink,
  Info,
  FileText,
  ShieldAlert,
  History,
  Radio,
} from "lucide-react";
import Link from "next/link";
import FreightMap from "@/components/map/FreightMap";
import AIStudio from "@/components/ai/AIStudio";
import DirectFreightAgreementModal from "@/components/agreements/DirectFreightAgreementModal";
import VehicleAssignmentModal from "@/components/fleet/VehicleAssignmentModal";
import BookingHistoryModal from "@/components/bookings/BookingHistoryModal";
import CustodyModal from "@/components/operations/CustodyModal";
import InsuranceModal from "@/components/operations/InsuranceModal";
import PaymentsModal from "@/components/operations/PaymentsModal";
import DisputesModal from "@/components/operations/DisputesModal";
import ControlRoomView from "@/components/controlroom/ControlRoomView";
import { UserRole } from "@/types";
import { api, setToken, getToken } from "@/lib/api";

type TruckData = {
  id: string;
  driver_id?: string;
  driver_name: string;
  driver_phone?: string;
  vehicle_type: string;
  capacity_tonnes: number;
  legal_payload_tonnes: number;
  latitude: number;
  longitude: number;
  destination_lat: number | null;
  destination_lon: number | null;
  available: boolean;
  verified: boolean;
  documents_valid: boolean;
  reliability_score: number;
  quoted_freight_inr: number | null;
  registration_no?: string;
  status?: string;
  ownership_type?: string;
  organization_name?: string;
};

type LoadData = {
  id: string;
  dealer_name: string;
  origin: string;
  destination: string;
  pickup_lat: number;
  pickup_lon: number;
  drop_lat: number;
  drop_lon: number;
  required_tonnes: number;
  vehicle_type: string;
  budget_inr: number;
  pickup_at: string;
  status: string;
  origin_name?: string;
  destination_name?: string;
  cargo_weight_tons?: number;
};

type Match = {
  truck_id: string;
  eligible: boolean;
  score: number;
  distance_km: number;
  reasons: string[];
  components: Record<string, number>;
  ml_probability?: number;
  ai_score?: number;
  neural_network_score?: number;
  rules_score?: number;
  ranking_method?: string;
};

type Booking = {
  id: string;
  load_id: string;
  truck_id: string;
  status: string;
  agreed_freight_inr: number;
  truck_registration_no?: string;
  driver_name?: string;
  origin_name?: string;
  destination_name?: string;
  origin?: string;
  destination?: string;
  required_tonnes?: number;
  budget_inr?: number;
};

const fmt = (n: number) =>
  new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  }).format(n || 0);

export default function UnifiedWorkspace() {
  const [page, setPage] = useState<string>("Overview");
  const [trucks, setTrucks] = useState<TruckData[]>([]);
  const [loads, setLoads] = useState<LoadData[]>([]);
  const [bookings, setBookings] = useState<Booking[]>([]);
  const [summary, setSummary] = useState<any>({});
  const [apiOnline, setApiOnline] = useState(false);
  const [activeLoad, setActiveLoad] = useState<string>("");
  const [matches, setMatches] = useState<Match[]>([]);
  const [selectedTruck, setSelectedTruck] = useState<string>("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string>("");
  const [mobileNav, setMobileNav] = useState(false);
  const [currentUser, setCurrentUser] = useState<any>(null);

  // Modal states for Master Architecture
  const [agreementBookingId, setAgreementBookingId] = useState<string | null>(null);
  const [showAgreementModal, setShowAgreementModal] = useState(false);
  const [assignmentTruck, setAssignmentTruck] = useState<any | null>(null);
  const [showAssignmentModal, setShowAssignmentModal] = useState(false);
  const [historyBookingId, setHistoryBookingId] = useState<string | null>(null);
  const [showHistoryModal, setShowHistoryModal] = useState(false);

  // Master Prompt 2 Modal States
  const [custodyShipmentId, setCustodyShipmentId] = useState<string | null>(null);
  const [showCustodyModal, setShowCustodyModal] = useState(false);
  const [insuranceTargetId, setInsuranceTargetId] = useState<string | null>(null);
  const [showInsuranceModal, setShowInsuranceModal] = useState(false);
  const [paymentsBookingId, setPaymentsBookingId] = useState<string | null>(null);
  const [showPaymentsModal, setShowPaymentsModal] = useState(false);
  const [disputesBookingId, setDisputesBookingId] = useState<string | null>(null);
  const [showDisputesModal, setShowDisputesModal] = useState(false);

  // Form states
  const [form, setForm] = useState({
    dealer_name: "Demo Shipper (Bengal Steel)",
    origin: "Kolkata Port / Docks",
    destination: "Durgapur Steel Complex",
    pickup_lat: "22.5448",
    pickup_lon: "88.3186",
    drop_lat: "23.5204",
    drop_lon: "87.3119",
    required_tonnes: "15",
    vehicle_type: "Open",
    budget_inr: "19000",
    pickup_at: new Date(Date.now() + 86400000).toISOString().slice(0, 16),
  });

  const [truckForm, setTruckForm] = useState({
    id: "",
    driver_name: "",
    phone: "",
    vehicle_type: "Open",
    capacity_tonnes: "16",
    legal_payload_tonnes: "16",
    latitude: "22.6842",
    longitude: "88.2934",
    available: true,
    verified: true,
    documents_valid: true,
    reliability_score: "92",
    quoted_freight_inr: "19000",
  });

  async function refresh() {
    try {
      const [t, l, b, s] = await Promise.all([
        api.listTrucks(),
        api.listLoads(),
        api.listBookings(),
        api.getDashboardSummary(),
      ]);

      const formattedTrucks: TruckData[] = (t || []).map((x: any) => ({
        id: x.id,
        driver_id: x.driver_id,
        registration_no: x.registration_no || x.id,
        driver_name: x.driver_name || "Commercial Carrier",
        driver_phone: x.driver_phone,
        vehicle_type: x.vehicle_type || (x.truck_type === "CLOSED_CONTAINER" ? "Container" : "Open"),
        capacity_tonnes: x.capacity_tonnes || x.capacity_tons || 16,
        legal_payload_tonnes: x.legal_payload_tonnes || x.capacity_tons || 16,
        latitude: x.latitude || x.current_lat || 22.5448,
        longitude: x.longitude || x.current_lon || 88.3186,
        destination_lat: x.destination_lat || null,
        destination_lon: x.destination_lon || null,
        available: x.available !== undefined ? x.available : x.status === "ONLINE_AVAILABLE",
        verified: x.verified !== undefined ? x.verified : x.verification_status === "VERIFIED",
        documents_valid: x.documents_valid !== undefined ? x.documents_valid : x.verification_status === "VERIFIED",
        reliability_score: x.reliability_score || x.driver_reliability_score || 88,
        quoted_freight_inr: x.quoted_freight_inr || 19000,
        status: x.status,
        ownership_type: x.ownership_type || "EXTERNAL_TRANSPORTER",
        organization_name: x.organization_name || (x.ownership_type === "LOADLINK_OWNED" ? "LoadLink Owned Fleet" : "Sharma Roadways"),
      }));

      const formattedLoads: LoadData[] = (l || []).map((x: any) => ({
        id: x.id,
        dealer_name: x.dealer_name || "Shipper",
        origin: x.origin || x.origin_name || "Kolkata Port",
        destination: x.destination || x.destination_name || "Durgapur",
        pickup_lat: x.pickup_lat || x.origin_lat || 22.5448,
        pickup_lon: x.pickup_lon || x.origin_lon || 88.3186,
        drop_lat: x.drop_lat || x.destination_lat || 23.5204,
        drop_lon: x.drop_lon || x.destination_lon || 87.3119,
        required_tonnes: x.required_tonnes || x.cargo_weight_tons || 15,
        vehicle_type: x.vehicle_type || (x.required_truck_type === "CLOSED_CONTAINER" ? "Container" : "Open"),
        budget_inr: x.budget_inr || x.target_budget || x.estimated_benchmark_price || 18000,
        pickup_at: x.pickup_at || (x.pickup_window_start ? new Date(x.pickup_window_start).toISOString() : new Date().toISOString()),
        status: x.status || "POSTED",
      }));

      const formattedBookings: Booking[] = (b || []).map((x: any) => ({
        id: x.id,
        load_id: x.load_id,
        truck_id: x.truck_id,
        status: x.status || "PENDING",
        agreed_freight_inr: x.agreed_freight_inr || x.offered_price || 18000,
        truck_registration_no: x.truck_registration_no || x.truck_id,
        driver_name: x.driver_name || "Assigned Driver",
        origin_name: x.origin_name || "Kolkata",
        destination_name: x.destination_name || "Durgapur",
        origin: x.origin_name || x.origin || "Kolkata Port",
        destination: x.destination_name || x.destination || "Durgapur Steel Complex",
        required_tonnes: x.required_tonnes || x.cargo_weight_tons || 15,
        budget_inr: x.agreed_freight_inr || x.offered_price || 18000,
      }));

      setTrucks(formattedTrucks);
      setLoads(formattedLoads);
      setBookings(formattedBookings);
      setSummary(s || {});
      setApiOnline(true);

      if (!activeLoad && formattedLoads.length > 0) {
        setActiveLoad(formattedLoads[0].id);
      }
    } catch (e: any) {
      setApiOnline(false);
      setMessage("Backend connection notice: " + (e.message || "Failed to fetch live data"));
    }
  }

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 15000);
    return () => clearInterval(id);
  }, []);

  // Quick Demo Login Handler - Full 8 Roles Supported
  const handleQuickDemoRole = async (role: UserRole) => {
    setBusy(true);
    setMessage("");
    try {
      const creds: Record<UserRole, { email: string; pass: string }> = {
        DEALER: { email: "dealer.kolkata@bengalsteel.in", pass: "dealer123" },
        DRIVER: { email: "driver.rajesh@loadlink.ai", pass: "driver123" },
        TRANSPORTER: { email: "transporter.sharma@bengalroadways.com", pass: "transporter123" },
        FLEET_MANAGER: { email: "fleet.manager@loadlink.ai", pass: "fleet123" },
        ADMIN: { email: "admin@loadlink.ai", pass: "admin123" },
        CONTROL_ROOM: { email: "control.room@loadlink.ai", pass: "control123" },
        COMPLIANCE_OFFICER: { email: "compliance@loadlink.ai", pass: "compliance123" },
        DISPUTE_OFFICER: { email: "disputes@loadlink.ai", pass: "disputes123" },
      };

      const c = creds[role] || creds.ADMIN;
      const res = await api.login(c.email, c.pass);
      setToken(res.access_token);
      setCurrentUser({ role, name: res.name || role });
      setMessage(`Switched active demo session to ${role} (${res.name || c.email})`);
      await refresh();
    } catch (err: any) {
      setMessage("Failed to switch demo role: " + (err.message || "Error"));
    } finally {
      setBusy(false);
    }
  };

  const currentLoad = loads.find((l) => l.id === activeLoad) || loads[0];

  const mapCenter: [number, number] = currentLoad
    ? [currentLoad.pickup_lat, currentLoad.pickup_lon]
    : [22.85, 87.8];

  const eligibleMatches = matches.filter((m) => m.eligible);

  async function createLoad(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      const l = await api.createLoad({
        ...form,
        pickup_lat: +form.pickup_lat,
        pickup_lon: +form.pickup_lon,
        drop_lat: +form.drop_lat,
        drop_lon: +form.drop_lon,
        required_tonnes: +form.required_tonnes,
        budget_inr: +form.budget_inr,
        pickup_at: new Date(form.pickup_at).toISOString(),
      });
      await refresh();
      setActiveLoad(l.id);
      setPage("Find Trucks");
      setMessage("Consignment load created successfully in database.");
      findMatches(l.id);
    } catch (e: any) {
      setMessage("Error creating load: " + (e.message || "Validation failed"));
    } finally {
      setBusy(false);
    }
  }

  async function findMatches(id = activeLoad) {
    if (!id) return;
    setBusy(true);
    try {
      const m = await api.getAIMatches(id);
      setMatches(m.results || []);
      setActiveLoad(id);
      setPage("Find Trucks");
      setMessage(
        `Smart Matching evaluated ${m.results?.length || 0} fleet candidates using 7-Factor Corridor Optimization.`
      );
    } catch (e: any) {
      setMessage("Matching failed: " + (e.message || "Error"));
    } finally {
      setBusy(false);
    }
  }

  async function createBooking() {
    if (!currentLoad || !selectedTruck) return;
    const t = trucks.find((x) => x.id === selectedTruck || x.registration_no === selectedTruck);
    try {
      await api.createBooking({
        load_id: currentLoad.id,
        truck_id: t?.id || selectedTruck,
        offered_price: t?.quoted_freight_inr || currentLoad.budget_inr || 18000,
        agreed_freight_inr: t?.quoted_freight_inr || currentLoad.budget_inr || 18000,
      });
      setMessage("Booking request dispatched to driver. Shipment created upon acceptance.");
      await refresh();
      setPage("Bookings");
    } catch (e: any) {
      setMessage("Booking failed: " + (e.message || "Error"));
    }
  }

  async function updateBooking(b: Booking, status: string) {
    try {
      await api.updateBookingStatus(b.id, status);
      setMessage(`Booking milestone updated to ${status}.`);
      await refresh();
    } catch (e: any) {
      setMessage("Booking transition notice: " + (e.message || "Action failed"));
      if (
        e.message?.toLowerCase().includes("agreement") ||
        e.message?.toLowerCase().includes("accept") ||
        e.message?.toLowerCase().includes("sign")
      ) {
        setAgreementBookingId(b.id);
        setShowAgreementModal(true);
      }
    }
  }

  async function addTruck(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      await api.createTruck({
        ...truckForm,
        capacity_tons: +truckForm.capacity_tonnes,
        capacity_tonnes: +truckForm.capacity_tonnes,
        legal_payload_tonnes: +truckForm.legal_payload_tonnes,
        latitude: +truckForm.latitude,
        longitude: +truckForm.longitude,
        current_lat: +truckForm.latitude,
        current_lon: +truckForm.longitude,
        reliability_score: +truckForm.reliability_score,
        quoted_freight_inr: +truckForm.quoted_freight_inr,
      });
      setMessage("Commercial truck onboarded and saved to active fleet.");
      await refresh();
      setTruckForm({
        id: "",
        driver_name: "",
        phone: "",
        vehicle_type: "Open",
        capacity_tonnes: "16",
        legal_payload_tonnes: "16",
        latitude: "22.6842",
        longitude: "88.2934",
        available: true,
        verified: true,
        documents_valid: true,
        reliability_score: "92",
        quoted_freight_inr: "19000",
      });
    } catch (e: any) {
      setMessage("Failed to register truck: " + (e.message || "Error"));
    } finally {
      setBusy(false);
    }
  }

  const nav = [
    ["Overview", LayoutDashboard],
    ["Post a Load", Plus],
    ["Find Trucks", Search],
    ["AI Studio", BrainCircuit],
    ["Live Map", MapPin],
    ["Fleet & Drivers", Users],
    ["Driver Portal", Truck],
    ["Bookings", Package],
    ["Agreements", FileText],
    ["Cargo Custody", Package],
    ["Risk Insurance", ShieldCheck],
    ["Direct Payments", CircleDollarSign],
    ["Disputes & Grievances", ShieldAlert],
    ["Control Room", Radio],
    ["Admin", Settings],
  ] as const;

  // Additional fleet trucks mapped for FreightMap
  const additionalTrucksForMap = useMemo(() => {
    return trucks.map((t) => ({
      lat: t.latitude,
      lon: t.longitude,
      regNo: t.registration_no || t.id,
      status: t.available ? "ONLINE" : "OFFLINE",
      reliability: t.reliability_score || 85,
    }));
  }, [trucks]);

  return (
    <div className="flex h-screen bg-[#F7F5F0] text-[#29231F] font-sans overflow-hidden">
      {/* Sidebar Navigation */}
      <aside
        className={`fixed inset-y-0 left-0 z-40 w-64 bg-[#FFFFFF] border-r border-[#E6DED5] flex flex-col justify-between transition-transform duration-200 md:static md:translate-x-0 ${
          mobileNav ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <div>
          {/* Brand Header */}
          <div className="h-16 px-5 border-b border-[#E6DED5] flex items-center justify-between">
            <Link href="/" className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-lg bg-[#5A3E2B] flex items-center justify-center text-white font-bold text-base shadow-xs">
                <Truck size={18} />
              </div>
              <div>
                <b className="tracking-tight text-sm text-[#29231F]">
                  LOADLINK <span className="text-[#8A796B]">AI</span>
                </b>
                <div className="text-[10px] text-[#8A796B] font-semibold tracking-wider uppercase">
                  FREIGHT INTELLIGENCE
                </div>
              </div>
            </Link>
            <button
              className="md:hidden text-[#6E6259] p-1.5 rounded-lg hover:bg-[#F7F5F0]"
              onClick={() => setMobileNav(false)}
            >
              <X size={18} />
            </button>
          </div>

          {/* Active Workspace / Demo Role Switcher */}
          <div className="p-4 border-b border-[#E6DED5] bg-[#FDFCFB]">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <div className="w-7 h-7 rounded-full bg-[#EFECE6] border border-[#E6DED5] flex items-center justify-center text-xs font-bold text-[#5A3E2B]">
                  {currentUser ? currentUser.name[0] : "D"}
                </div>
                <div>
                  <div className="text-xs font-bold text-[#29231F] truncate max-w-[120px]">
                    {currentUser ? currentUser.name : "Demo Workspace"}
                  </div>
                  <div className="text-[10px] text-[#6E6259]">
                    {currentUser ? `${currentUser.role} Session` : "Multi-Role Pilot"}
                  </div>
                </div>
              </div>
              <span className={`w-2 h-2 rounded-full ${apiOnline ? "bg-[#3F7D58] animate-pulse" : "bg-[#D9534F]"}`} />
            </div>

            {/* Quick 8-Role Simulator Switcher */}
            <div className="pt-2 space-y-1.5">
              <div className="flex items-center justify-between text-[10px] font-bold text-[#8A796B] uppercase">
                <span>Active Portal Role</span>
                <span className="bg-[#F0EAE1] text-[#5A3E2B] px-1.5 py-0.2 rounded font-mono text-[9px] border border-[#E6DED5]">
                  8 Portals
                </span>
              </div>
              <select
                value={currentUser?.role || "ADMIN"}
                onChange={(e) => handleQuickDemoRole(e.target.value as UserRole)}
                className="w-full text-xs p-1.5 bg-[#F7F5F0] border border-[#E6DED5] rounded-lg font-bold text-[#29231F]"
              >
                <option value="DEALER">Dealer / Shipper (Bengal Steel)</option>
                <option value="DRIVER">Driver (Rajesh Kumar)</option>
                <option value="TRANSPORTER">Transporter (Sharma Roadways)</option>
                <option value="FLEET_MANAGER">LoadLink Fleet Manager</option>
                <option value="ADMIN">Marketplace Admin</option>
                <option value="CONTROL_ROOM">Control Room Operator</option>
                <option value="COMPLIANCE_OFFICER">Compliance Officer</option>
                <option value="DISPUTE_OFFICER">Dispute Officer</option>
              </select>

              <div className="grid grid-cols-4 gap-1 text-[9px] font-bold">
                <button
                  onClick={() => handleQuickDemoRole("DEALER")}
                  className={`py-1 px-1 rounded text-center transition border ${
                    currentUser?.role === "DEALER"
                      ? "bg-[#5A3E2B] text-white border-[#5A3E2B]"
                      : "bg-[#F0EAE1] hover:bg-[#E6DED5] text-[#5A3E2B] border-[#E6DED5]"
                  }`}
                >
                  Dealer
                </button>
                <button
                  onClick={() => handleQuickDemoRole("DRIVER")}
                  className={`py-1 px-1 rounded text-center transition border ${
                    currentUser?.role === "DRIVER"
                      ? "bg-[#5A3E2B] text-white border-[#5A3E2B]"
                      : "bg-[#F0EAE1] hover:bg-[#E6DED5] text-[#5A3E2B] border-[#E6DED5]"
                  }`}
                >
                  Driver
                </button>
                <button
                  onClick={() => handleQuickDemoRole("TRANSPORTER")}
                  className={`py-1 px-1 rounded text-center transition border ${
                    currentUser?.role === "TRANSPORTER"
                      ? "bg-[#5A3E2B] text-white border-[#5A3E2B]"
                      : "bg-[#F0EAE1] hover:bg-[#E6DED5] text-[#5A3E2B] border-[#E6DED5]"
                  }`}
                >
                  Carrier
                </button>
                <button
                  onClick={() => handleQuickDemoRole("ADMIN")}
                  className={`py-1 px-1 rounded text-center transition border ${
                    currentUser?.role === "ADMIN"
                      ? "bg-[#5A3E2B] text-white border-[#5A3E2B]"
                      : "bg-[#F0EAE1] hover:bg-[#E6DED5] text-[#5A3E2B] border-[#E6DED5]"
                  }`}
                >
                  Admin
                </button>
              </div>
            </div>
          </div>

          {/* Navigation Links */}
          <div className="px-3 py-4">
            <div className="px-3 pb-2 text-[10px] font-bold uppercase tracking-wider text-[#8A796B]">
              WORKSPACE MODULES
            </div>
            <nav className="space-y-1">
              {nav.map(([label, Icon]) => {
                const isActive = page === label;
                return (
                  <button
                    key={label}
                    onClick={() => {
                      setPage(label);
                      setMobileNav(false);
                    }}
                    className={`w-full flex items-center justify-between px-3 py-2 rounded-lg text-xs font-semibold transition ${
                      isActive
                        ? "bg-[#5A3E2B] text-white shadow-xs"
                        : "text-[#6E6259] hover:bg-[#F7F5F0] hover:text-[#29231F]"
                    }`}
                  >
                    <span className="flex items-center gap-2.5">
                      <Icon size={16} />
                      <span>{label}</span>
                    </span>
                    {label === "Bookings" && bookings.length > 0 && (
                      <span
                        className={`text-[10px] font-bold px-1.5 py-0.2 rounded-full ${
                          isActive ? "bg-white/20 text-white" : "bg-[#EFECE6] text-[#5A3E2B]"
                        }`}
                      >
                        {bookings.length}
                      </span>
                    )}
                  </button>
                );
              })}
            </nav>
          </div>
        </div>

        {/* Sidebar Footer */}
        <div className="p-4 border-t border-[#E6DED5] space-y-3 bg-[#FDFCFB]">
          <div className="flex items-center gap-2.5 p-2 rounded-lg bg-[#F7F5F0] border border-[#E6DED5]">
            <ShieldCheck size={16} className="text-[#3F7D58] shrink-0" />
            <div>
              <div className="text-[11px] font-bold text-[#29231F]">Verified Corridor</div>
              <div className="text-[10px] text-[#6E6259]">Kolkata ↔ Durgapur ↔ Asansol</div>
            </div>
          </div>
          <div className="flex items-center justify-between text-[10px] text-[#8A796B] font-mono">
            <span>MVP V1.0.0</span>
            <button
              onClick={refresh}
              className="flex items-center gap-1 hover:text-[#29231F] transition"
              title="Refresh Data"
            >
              <RefreshCw size={11} className={busy ? "animate-spin" : ""} /> Sync
            </button>
          </div>
        </div>
      </aside>

      {/* Main Content Area */}
      <main className="flex-1 flex flex-col min-w-0 overflow-y-auto">
        {/* Top Header */}
        <header className="sticky top-0 z-30 h-16 bg-white/95 backdrop-blur-md border-b border-[#E6DED5] px-4 lg:px-8 flex items-center justify-between shadow-xs">
          <div className="flex items-center gap-3">
            <button
              className="md:hidden text-[#29231F] p-1.5 rounded-lg hover:bg-[#F7F5F0]"
              onClick={() => setMobileNav(true)}
            >
              <Menu size={20} />
            </button>
            <div>
              <div className="text-[10px] font-bold uppercase tracking-wider text-[#8A796B]">
                WORKSPACE / <span className="text-[#29231F]">{page.toUpperCase()}</span>
              </div>
              <h1 className="text-base font-bold text-[#29231F] leading-tight">{page}</h1>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <span
              className={`inline-flex items-center gap-1.5 text-xs font-semibold px-2.5 py-1 rounded-full border ${
                apiOnline
                  ? "bg-[#EBF7EE] text-[#24613B] border-[#BDE5C8]"
                  : "bg-[#FAEDED] text-[#C53030] border-[#F1C4C4]"
              }`}
            >
              <span className={`w-2 h-2 rounded-full ${apiOnline ? "bg-[#3F7D58]" : "bg-[#D9534F]"}`} />
              <span className="hidden sm:inline">{apiOnline ? "API Connected" : "API Offline"}</span>
            </span>

            {/* Link to dedicated portals */}
            <div className="hidden lg:flex items-center gap-1.5 text-xs font-semibold">
              <Link
                href="/dealer"
                className="px-2.5 py-1 rounded bg-[#F7F5F0] hover:bg-[#EFECE6] border border-[#E6DED5] text-[#5A3E2B] transition"
              >
                Dealer Portal
              </Link>
              <Link
                href="/driver"
                className="px-2.5 py-1 rounded bg-[#F7F5F0] hover:bg-[#EFECE6] border border-[#E6DED5] text-[#8A796B] transition"
              >
                Driver PWA
              </Link>
              <Link
                href="/admin"
                className="px-2.5 py-1 rounded bg-[#F7F5F0] hover:bg-[#EFECE6] border border-[#E6DED5] text-[#29231F] transition"
              >
                Control Tower
              </Link>
            </div>
          </div>
        </header>

        {/* Global Alert / Toast */}
        {message && (
          <div
            onClick={() => setMessage("")}
            className="mx-4 lg:mx-8 mt-4 p-3 rounded-lg bg-[#5A3E2B] text-white text-xs font-semibold flex items-center justify-between shadow-sm cursor-pointer"
          >
            <div className="flex items-center gap-2">
              <Info size={15} />
              <span>{message}</span>
            </div>
            <X size={14} />
          </div>
        )}

        {/* View Content */}
        <div className="p-4 lg:p-8 max-w-7xl w-full mx-auto space-y-6">
          {/* ============================================================== */}
          {/* MODULE A: OVERVIEW DASHBOARD */}
          {/* ============================================================== */}
          {page === "Overview" && (
            <div className="space-y-6">
              {/* Welcome Banner */}
              <div className="bg-gradient-to-r from-[#5A3E2B] to-[#432E20] text-white rounded-2xl p-6 lg:p-8 shadow-sm flex flex-col md:flex-row md:items-center justify-between gap-6">
                <div>
                  <div className="text-[11px] font-bold tracking-wider uppercase text-[#D8CEC4] mb-1">
                    CORRIDOR OPERATIONS · PILOT LOGISTICS CONTROL
                  </div>
                  <h2 className="text-2xl lg:text-3xl font-black tracking-tight">
                    Move freight <i className="font-serif italic font-normal text-[#E6DED5]">smarter.</i>
                  </h2>
                  <p className="text-xs lg:text-sm text-[#D8CEC4] max-w-xl mt-1">
                    Integrated operations, verified fleet availability, and deterministic 7-factor freight matching on the Kolkata-Durgapur-Asansol artery.
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => setPage("Post a Load")}
                    className="px-4 py-2.5 bg-white text-[#5A3E2B] rounded-xl font-bold text-xs hover:bg-[#F7F5F0] transition flex items-center gap-1.5 shadow-sm"
                  >
                    <Plus size={16} /> Post Consignment
                  </button>
                  <button
                    onClick={() => setPage("Find Trucks")}
                    className="px-4 py-2.5 bg-[#8A796B] text-white rounded-xl font-bold text-xs hover:bg-[#726255] transition flex items-center gap-1.5"
                  >
                    <Search size={16} /> Find Trucks
                  </button>
                </div>
              </div>

              {/* Operational Stats Cards */}
              <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                {[
                  ["Available trucks", summary.available_trucks ?? trucks.filter((t) => t.available).length, Truck, "Verified active supply"],
                  ["Open loads", summary.open_loads ?? loads.length, Package, "Ready for dispatch"],
                  ["Total bookings", summary.bookings ?? bookings.length, ArrowDownUp, "Corridor volume"],
                  ["In transit", summary.in_transit ?? 1, Activity, "Live route execution"],
                ].map(([label, value, Icon, sub]: any) => (
                  <div key={label} className="bg-white rounded-xl border border-[#E6DED5] p-5 shadow-xs">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-xs font-bold text-[#6E6259]">{label}</span>
                      <div className="w-7 h-7 rounded-lg bg-[#F7F5F0] text-[#5A3E2B] flex items-center justify-center">
                        <Icon size={16} />
                      </div>
                    </div>
                    <div className="text-2xl font-black font-mono text-[#29231F]">{value}</div>
                    <div className="text-[10px] text-[#8A796B] mt-1">{sub}</div>
                  </div>
                ))}
              </div>

              {/* Freight Network Map & Recent Loads */}
              <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
                {/* Map Card */}
                <div className="lg:col-span-7 bg-white rounded-xl border border-[#E6DED5] p-5 shadow-xs space-y-3">
                  <div className="flex items-center justify-between">
                    <div>
                      <h3 className="font-bold text-[#29231F] text-sm flex items-center gap-1.5">
                        <Compass size={16} className="text-[#5A3E2B]" /> Freight Network Overview
                      </h3>
                      <p className="text-[11px] text-[#6E6259]">
                        Real-time fleet positions and active consignment route corridor
                      </p>
                    </div>
                    <button
                      onClick={() => setPage("Live Map")}
                      className="text-xs font-bold text-[#5A3E2B] hover:underline flex items-center gap-1"
                    >
                      Open Live Map <ChevronRight size={14} />
                    </button>
                  </div>

                  <FreightMap
                    origin={
                      currentLoad
                        ? { lat: currentLoad.pickup_lat, lon: currentLoad.pickup_lon, name: currentLoad.origin }
                        : undefined
                    }
                    destination={
                      currentLoad
                        ? { lat: currentLoad.drop_lat, lon: currentLoad.drop_lon, name: currentLoad.destination }
                        : undefined
                    }
                    additionalTrucks={additionalTrucksForMap}
                    height="320px"
                    interactive={true}
                  />
                </div>

                {/* Recent Loads Panel */}
                <div className="lg:col-span-5 bg-white rounded-xl border border-[#E6DED5] p-5 shadow-xs space-y-3">
                  <div className="flex items-center justify-between">
                    <div>
                      <h3 className="font-bold text-[#29231F] text-sm">Recent Consignments</h3>
                      <p className="text-[11px] text-[#6E6259]">Select to match candidate trucks</p>
                    </div>
                    <button
                      onClick={() => setPage("Post a Load")}
                      className="text-xs font-bold text-[#5A3E2B] hover:underline flex items-center gap-1"
                    >
                      + New
                    </button>
                  </div>

                  <div className="space-y-2 max-h-[320px] overflow-y-auto">
                    {loads.slice(0, 6).map((l) => (
                      <button
                        key={l.id}
                        onClick={() => {
                          setActiveLoad(l.id);
                          findMatches(l.id);
                        }}
                        className={`w-full text-left p-3 rounded-lg border transition flex items-center justify-between ${
                          activeLoad === l.id
                            ? "bg-[#F7F5F0] border-[#5A3E2B]"
                            : "bg-[#FFFFFF] border-[#E6DED5] hover:border-[#8A796B]"
                        }`}
                      >
                        <div className="space-y-1">
                          <div className="text-xs font-bold text-[#29231F] flex items-center gap-1">
                            <span>{l.origin}</span>
                            <span className="text-[#8A796B]">→</span>
                            <span>{l.destination}</span>
                          </div>
                          <div className="text-[10px] text-[#6E6259]">
                            {l.required_tonnes}T · {l.vehicle_type} · {l.dealer_name}
                          </div>
                        </div>
                        <div className="text-right">
                          <div className="text-xs font-bold font-mono text-[#5A3E2B]">{fmt(l.budget_inr)}</div>
                          <span className="text-[9px] uppercase font-bold tracking-wider px-1.5 py-0.5 rounded bg-[#F0EAE1] text-[#6E6259]">
                            {l.status}
                          </span>
                        </div>
                      </button>
                    ))}
                    {loads.length === 0 && (
                      <p className="text-xs text-[#6E6259] italic text-center py-6">
                        No loads posted yet. Create your first freight requirement.
                      </p>
                    )}
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* ============================================================== */}
          {/* MODULE B: POST A LOAD */}
          {/* ============================================================== */}
          {page === "Post a Load" && (
            <div className="max-w-3xl mx-auto space-y-6">
              <div className="border-b border-[#E6DED5] pb-3">
                <span className="text-[10px] font-bold uppercase tracking-wider text-[#5A3E2B] bg-[#F0EAE1] px-2 py-0.5 rounded border border-[#E6DED5]">
                  Shipper & Dealer Workspace
                </span>
                <h2 className="text-xl font-black text-[#29231F] mt-1">Post a Freight Requirement</h2>
                <p className="text-xs text-[#6E6259]">
                  Input consignment tonnage and coordinates. The 7-factor engine will rank best-fit carriers.
                </p>
              </div>

              <form onSubmit={createLoad} className="bg-white rounded-xl border border-[#E6DED5] p-6 shadow-xs space-y-5">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <label className="space-y-1">
                    <span className="text-xs font-bold text-[#29231F]">Dealer / Company Name</span>
                    <input
                      type="text"
                      value={form.dealer_name}
                      onChange={(e) => setForm({ ...form, dealer_name: e.target.value })}
                      required
                      className="w-full text-xs p-2.5 bg-[#F7F5F0] border border-[#E6DED5] rounded-lg"
                    />
                  </label>

                  <label className="space-y-1">
                    <span className="text-xs font-bold text-[#29231F]">Required Payload (Tonnes)</span>
                    <input
                      type="number"
                      value={form.required_tonnes}
                      onChange={(e) => setForm({ ...form, required_tonnes: e.target.value })}
                      min="1"
                      max="55"
                      required
                      className="w-full text-xs p-2.5 bg-[#F7F5F0] border border-[#E6DED5] rounded-lg font-mono"
                    />
                  </label>

                  <label className="space-y-1">
                    <span className="text-xs font-bold text-[#29231F]">Pickup Origin Hub</span>
                    <input
                      type="text"
                      value={form.origin}
                      onChange={(e) => setForm({ ...form, origin: e.target.value })}
                      required
                      className="w-full text-xs p-2.5 bg-[#F7F5F0] border border-[#E6DED5] rounded-lg"
                    />
                  </label>

                  <label className="space-y-1">
                    <span className="text-xs font-bold text-[#29231F]">Delivery Destination Hub</span>
                    <input
                      type="text"
                      value={form.destination}
                      onChange={(e) => setForm({ ...form, destination: e.target.value })}
                      required
                      className="w-full text-xs p-2.5 bg-[#F7F5F0] border border-[#E6DED5] rounded-lg"
                    />
                  </label>

                  <label className="space-y-1">
                    <span className="text-xs font-bold text-[#29231F]">Pickup Latitude</span>
                    <input
                      type="text"
                      value={form.pickup_lat}
                      onChange={(e) => setForm({ ...form, pickup_lat: e.target.value })}
                      required
                      className="w-full text-xs p-2.5 bg-[#F7F5F0] border border-[#E6DED5] rounded-lg font-mono"
                    />
                  </label>

                  <label className="space-y-1">
                    <span className="text-xs font-bold text-[#29231F]">Pickup Longitude</span>
                    <input
                      type="text"
                      value={form.pickup_lon}
                      onChange={(e) => setForm({ ...form, pickup_lon: e.target.value })}
                      required
                      className="w-full text-xs p-2.5 bg-[#F7F5F0] border border-[#E6DED5] rounded-lg font-mono"
                    />
                  </label>

                  <label className="space-y-1">
                    <span className="text-xs font-bold text-[#29231F]">Dropoff Latitude</span>
                    <input
                      type="text"
                      value={form.drop_lat}
                      onChange={(e) => setForm({ ...form, drop_lat: e.target.value })}
                      required
                      className="w-full text-xs p-2.5 bg-[#F7F5F0] border border-[#E6DED5] rounded-lg font-mono"
                    />
                  </label>

                  <label className="space-y-1">
                    <span className="text-xs font-bold text-[#29231F]">Dropoff Longitude</span>
                    <input
                      type="text"
                      value={form.drop_lon}
                      onChange={(e) => setForm({ ...form, drop_lon: e.target.value })}
                      required
                      className="w-full text-xs p-2.5 bg-[#F7F5F0] border border-[#E6DED5] rounded-lg font-mono"
                    />
                  </label>

                  <label className="space-y-1">
                    <span className="text-xs font-bold text-[#29231F]">Vehicle Category</span>
                    <select
                      value={form.vehicle_type}
                      onChange={(e) => setForm({ ...form, vehicle_type: e.target.value })}
                      className="w-full text-xs p-2.5 bg-[#F7F5F0] border border-[#E6DED5] rounded-lg font-medium"
                    >
                      <option value="Open">Open Body (Flatbed / Industrial)</option>
                      <option value="Container">Closed Container</option>
                      <option value="Trailer">Multi-Axle Trailer</option>
                      <option value="Tipper">Tipper</option>
                    </select>
                  </label>

                  <label className="space-y-1">
                    <span className="text-xs font-bold text-[#29231F]">Freight Budget (₹)</span>
                    <input
                      type="number"
                      value={form.budget_inr}
                      onChange={(e) => setForm({ ...form, budget_inr: e.target.value })}
                      required
                      className="w-full text-xs p-2.5 bg-[#F7F5F0] border border-[#E6DED5] rounded-lg font-mono"
                    />
                  </label>

                  <label className="space-y-1 md:col-span-2">
                    <span className="text-xs font-bold text-[#29231F]">Pickup Date & Time</span>
                    <input
                      type="datetime-local"
                      value={form.pickup_at}
                      onChange={(e) => setForm({ ...form, pickup_at: e.target.value })}
                      required
                      className="w-full text-xs p-2.5 bg-[#F7F5F0] border border-[#E6DED5] rounded-lg font-medium"
                    />
                  </label>
                </div>

                <div className="p-3 bg-[#F7F5F0] rounded-lg border border-[#E6DED5] flex items-center gap-2 text-xs text-[#6E6259]">
                  <MapPin size={16} className="text-[#5A3E2B] shrink-0" />
                  <span>
                    Coordinates are calibrated to the West Bengal highway corridor. Tonnage is bounded by RTO safety limits.
                  </span>
                </div>

                <button
                  type="submit"
                  disabled={busy}
                  className="w-full py-3 bg-[#5A3E2B] text-white font-bold text-xs rounded-xl hover:bg-[#432E20] transition disabled:opacity-50 flex items-center justify-center gap-2 shadow-xs"
                >
                  {busy ? "Posting Consignment..." : "Create Load and Find Best-Fit Trucks"} <ChevronRight size={16} />
                </button>
              </form>
            </div>
          )}

          {/* ============================================================== */}
          {/* MODULE C: FIND TRUCKS */}
          {/* ============================================================== */}
          {page === "Find Trucks" && (
            <div className="space-y-6">
              <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-[#E6DED5]">
                <div>
                  <span className="text-[10px] font-bold uppercase tracking-wider text-[#5A3E2B] bg-[#F0EAE1] px-2 py-0.5 rounded border border-[#E6DED5]">
                    7-Factor Smart Matching Engine
                  </span>
                  <h2 className="text-xl font-black text-[#29231F] mt-1">Recommended Carrier Trucks</h2>
                  <p className="text-xs text-[#6E6259]">
                    Multi-criteria linear ranking with hard filters for capacity, vehicle type, and driver verification.
                  </p>
                </div>

                <div className="flex items-center gap-2">
                  <select
                    value={activeLoad}
                    onChange={(e) => {
                      setActiveLoad(e.target.value);
                      findMatches(e.target.value);
                    }}
                    className="text-xs p-2 bg-white border border-[#E6DED5] rounded-lg font-bold text-[#29231F]"
                  >
                    <option value="">Select a consignment</option>
                    {loads.map((l) => (
                      <option key={l.id} value={l.id}>
                        {l.origin} → {l.destination} ({l.required_tonnes}T)
                      </option>
                    ))}
                  </select>
                  <button
                    onClick={() => findMatches(activeLoad)}
                    disabled={!activeLoad || busy}
                    className="px-3.5 py-2 bg-[#5A3E2B] text-white text-xs font-bold rounded-lg hover:bg-[#432E20] transition disabled:opacity-50 flex items-center gap-1.5"
                  >
                    <RefreshCw size={13} className={busy ? "animate-spin" : ""} /> Run Match
                  </button>
                </div>
              </div>

              <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
                {/* Candidate List */}
                <div className="lg:col-span-7 space-y-4">
                  <div className="flex items-center justify-between text-xs text-[#6E6259]">
                    <span>
                      <b>{eligibleMatches.length}</b> eligible trucks ·{" "}
                      <b>{matches.length - eligibleMatches.length}</b> filtered out
                    </span>
                    {selectedTruck && (
                      <span className="text-[#3F7D58] font-bold">Selected: {selectedTruck}</span>
                    )}
                  </div>

                  <div className="space-y-3">
                    {eligibleMatches.map((m) => {
                      const t = trucks.find((x) => x.id === m.truck_id || x.registration_no === m.truck_id);
                      const isSelected = selectedTruck === (t?.id || m.truck_id);
                      return (
                        <div
                          key={m.truck_id}
                          onClick={() => setSelectedTruck(t?.id || m.truck_id)}
                          className={`p-4 rounded-xl border transition cursor-pointer shadow-xs ${
                            isSelected
                              ? "bg-[#FDFCFB] border-[#5A3E2B] ring-2 ring-[#5A3E2B]/20"
                              : "bg-white border-[#E6DED5] hover:border-[#8A796B]"
                          }`}
                        >
                          <div className="flex items-start justify-between gap-4">
                            <div className="flex items-start gap-3">
                              <div className="w-10 h-10 rounded-xl bg-[#F7F5F0] border border-[#E6DED5] flex items-center justify-center text-[#5A3E2B] shrink-0">
                                <Truck size={20} />
                              </div>
                              <div>
                                <div className="flex items-center gap-2">
                                  <b className="text-sm text-[#29231F] font-mono">
                                    {t?.registration_no || m.truck_id}
                                  </b>
                                  <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-[#EBF7EE] text-[#24613B] border border-[#BDE5C8]">
                                    ✓ Verified
                                  </span>
                                </div>
                                <p className="text-xs text-[#6E6259] mt-0.5">
                                  {t?.driver_name || "Commercial Carrier"} · {t?.vehicle_type || "Open"} ·{" "}
                                  {t?.capacity_tonnes || 16}T Capacity
                                </p>
                                <p className="text-[11px] text-[#8A796B] mt-1 flex items-center gap-2">
                                  <span>{m.distance_km} km to pickup</span>
                                  <span>•</span>
                                  <span>Reliability: {t?.reliability_score || 90}/100</span>
                                </p>
                              </div>
                            </div>

                            <div className="text-right shrink-0">
                              <div className="text-xl font-black font-mono text-[#5A3E2B]">
                                {m.score}%
                              </div>
                              <div className="text-[10px] uppercase font-bold text-[#8A796B]">Match Score</div>
                              {t?.quoted_freight_inr && (
                                <div className="text-xs font-bold text-[#29231F] mt-1 font-mono">
                                  {fmt(t.quoted_freight_inr)}
                                </div>
                              )}
                            </div>
                          </div>

                          {/* Factor Breakdown Bars */}
                          {m.components && (
                            <div className="mt-3 pt-3 border-t border-[#E6DED5] grid grid-cols-2 md:grid-cols-4 gap-2 text-[10px]">
                              {Object.entries(m.components).map(([k, v]) => (
                                <div key={k} className="bg-[#F7F5F0] p-1.5 rounded border border-[#E6DED5]">
                                  <span className="text-[#6E6259] truncate block capitalize">
                                    {k.replace(/_/g, " ")}
                                  </span>
                                  <b className="text-[#29231F] font-mono">{v.toFixed(1)}</b>
                                </div>
                              ))}
                            </div>
                          )}
                        </div>
                      );
                    })}

                    {matches.length === 0 && (
                      <div className="bg-white rounded-xl border border-[#E6DED5] p-10 text-center space-y-3">
                        <Search size={32} className="mx-auto text-[#8A796B]" />
                        <h3 className="font-bold text-sm text-[#29231F]">Ready to Match Commercial Carriers?</h3>
                        <p className="text-xs text-[#6E6259] max-w-sm mx-auto">
                          Select an active consignment above and execute the 7-factor corridor matching algorithm.
                        </p>
                      </div>
                    )}
                  </div>

                  {eligibleMatches.length > 0 && (
                    <button
                      onClick={createBooking}
                      disabled={!selectedTruck}
                      className="w-full py-3 bg-[#5A3E2B] text-white font-bold text-xs rounded-xl hover:bg-[#432E20] transition disabled:opacity-50 flex items-center justify-center gap-2 shadow-xs"
                    >
                      Request Selected Truck for Dispatch <ChevronRight size={16} />
                    </button>
                  )}
                </div>

                {/* Map Panel */}
                <div className="lg:col-span-5 bg-white rounded-xl border border-[#E6DED5] p-5 shadow-xs space-y-3">
                  <div className="flex items-center justify-between">
                    <div>
                      <h3 className="font-bold text-sm text-[#29231F]">Fleet Positions</h3>
                      <p className="text-[11px] text-[#6E6259]">Pickup/delivery pins & candidate locations</p>
                    </div>
                    <MapPin size={16} className="text-[#5A3E2B]" />
                  </div>

                  <FreightMap
                    origin={
                      currentLoad
                        ? { lat: currentLoad.pickup_lat, lon: currentLoad.pickup_lon, name: currentLoad.origin }
                        : undefined
                    }
                    destination={
                      currentLoad
                        ? { lat: currentLoad.drop_lat, lon: currentLoad.drop_lon, name: currentLoad.destination }
                        : undefined
                    }
                    additionalTrucks={additionalTrucksForMap}
                    height="400px"
                    interactive={true}
                  />
                </div>
              </div>
            </div>
          )}

          {/* ============================================================== */}
          {/* MODULE D: AI STUDIO */}
          {/* ============================================================== */}
          {page === "AI Studio" && <AIStudio trucks={trucks} loads={loads} />}

          {/* ============================================================== */}
          {/* MODULE E: LIVE MAP */}
          {/* ============================================================== */}
          {page === "Live Map" && (
            <div className="space-y-4">
              <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-[#E6DED5]">
                <div>
                  <span className="text-[10px] font-bold uppercase tracking-wider text-[#5A3E2B] bg-[#F0EAE1] px-2 py-0.5 rounded border border-[#E6DED5]">
                    Fleet Visibility
                  </span>
                  <h2 className="text-xl font-black text-[#29231F] mt-1">Live Freight Corridor Map</h2>
                  <p className="text-xs text-[#6E6259]">
                    GPS positions of registered carrier trucks across Kolkata, Dankuni, Durgapur & Asansol.
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-[11px] font-bold px-3 py-1 bg-[#F0EAE1] text-[#5A3E2B] border border-[#E6DED5] rounded-full flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full bg-[#3F7D58] animate-pulse" />
                    LIVE TELEMETRY & LAST-KNOWN COORDINATES
                  </span>
                </div>
              </div>

              <div className="bg-white rounded-xl border border-[#E6DED5] p-3 shadow-xs">
                <FreightMap
                  origin={
                    currentLoad
                      ? { lat: currentLoad.pickup_lat, lon: currentLoad.pickup_lon, name: currentLoad.origin }
                      : undefined
                  }
                  destination={
                    currentLoad
                      ? { lat: currentLoad.drop_lat, lon: currentLoad.drop_lon, name: currentLoad.destination }
                      : undefined
                  }
                  additionalTrucks={additionalTrucksForMap}
                  height="520px"
                  interactive={true}
                />
              </div>

              <div className="p-3 bg-white rounded-xl border border-[#E6DED5] flex flex-wrap items-center justify-between gap-4 text-xs text-[#6E6259]">
                <div className="flex items-center gap-4">
                  <span>
                    <b>{trucks.length}</b> commercial trucks registered
                  </span>
                  <span>•</span>
                  <span>
                    <b>{trucks.filter((t) => t.available).length}</b> available on-duty
                  </span>
                  <span>•</span>
                  <span>
                    Primary Corridor: <b>NH19 Grand Trunk Highway</b>
                  </span>
                </div>
                <div className="text-[10px] text-[#8A796B]">
                  Coordinates update dynamically via driver GPS telemetry or manual reporting.
                </div>
              </div>
            </div>
          )}

          {/* ============================================================== */}
          {/* MODULE F: DRIVER PORTAL */}
          {/* ============================================================== */}
          {page === "Driver Portal" && (
            <div className="space-y-6">
              <div className="border-b border-[#E6DED5] pb-3">
                <span className="text-[10px] font-bold uppercase tracking-wider text-[#8A796B] bg-[#F0EAE1] px-2 py-0.5 rounded border border-[#E6DED5]">
                  Carrier & Driver Workspace
                </span>
                <h2 className="text-xl font-black text-[#29231F] mt-1">Driver & Truck Operations</h2>
                <p className="text-xs text-[#6E6259]">
                  Register a commercial vehicle, toggle real-time duty availability, and manage corridor runs.
                </p>
              </div>

              <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
                {/* Truck Onboarding Form */}
                <form
                  onSubmit={addTruck}
                  className="lg:col-span-6 bg-white rounded-xl border border-[#E6DED5] p-5 shadow-xs space-y-4"
                >
                  <div className="flex items-center gap-2 border-b border-[#E6DED5] pb-3">
                    <Truck size={18} className="text-[#5A3E2B]" />
                    <div>
                      <h3 className="font-bold text-sm text-[#29231F]">Register Commercial Truck</h3>
                      <p className="text-[11px] text-[#6E6259]">Onboard vehicle to the LoadLink network</p>
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-3">
                    <label className="space-y-1">
                      <span className="text-xs font-bold text-[#29231F]">Registration Number</span>
                      <input
                        type="text"
                        placeholder="e.g. WB-19-9021"
                        value={truckForm.id}
                        onChange={(e) => setTruckForm({ ...truckForm, id: e.target.value })}
                        required
                        className="w-full text-xs p-2.5 bg-[#F7F5F0] border border-[#E6DED5] rounded-lg font-mono uppercase"
                      />
                    </label>

                    <label className="space-y-1">
                      <span className="text-xs font-bold text-[#29231F]">Driver Full Name</span>
                      <input
                        type="text"
                        placeholder="Driver Name"
                        value={truckForm.driver_name}
                        onChange={(e) => setTruckForm({ ...truckForm, driver_name: e.target.value })}
                        required
                        className="w-full text-xs p-2.5 bg-[#F7F5F0] border border-[#E6DED5] rounded-lg"
                      />
                    </label>

                    <label className="space-y-1">
                      <span className="text-xs font-bold text-[#29231F]">Phone Number</span>
                      <input
                        type="tel"
                        placeholder="+91..."
                        value={truckForm.phone}
                        onChange={(e) => setTruckForm({ ...truckForm, phone: e.target.value })}
                        required
                        className="w-full text-xs p-2.5 bg-[#F7F5F0] border border-[#E6DED5] rounded-lg font-mono"
                      />
                    </label>

                    <label className="space-y-1">
                      <span className="text-xs font-bold text-[#29231F]">Vehicle Type</span>
                      <select
                        value={truckForm.vehicle_type}
                        onChange={(e) => setTruckForm({ ...truckForm, vehicle_type: e.target.value })}
                        className="w-full text-xs p-2.5 bg-[#F7F5F0] border border-[#E6DED5] rounded-lg font-medium"
                      >
                        <option value="Open">Open Body</option>
                        <option value="Container">Closed Container</option>
                        <option value="Trailer">Trailer</option>
                        <option value="Tipper">Tipper</option>
                      </select>
                    </label>

                    <label className="space-y-1">
                      <span className="text-xs font-bold text-[#29231F]">Capacity (Tonnes)</span>
                      <input
                        type="number"
                        value={truckForm.capacity_tonnes}
                        onChange={(e) => setTruckForm({ ...truckForm, capacity_tonnes: e.target.value })}
                        required
                        className="w-full text-xs p-2.5 bg-[#F7F5F0] border border-[#E6DED5] rounded-lg font-mono"
                      />
                    </label>

                    <label className="space-y-1">
                      <span className="text-xs font-bold text-[#29231F]">Baseline Quote (₹)</span>
                      <input
                        type="number"
                        value={truckForm.quoted_freight_inr}
                        onChange={(e) => setTruckForm({ ...truckForm, quoted_freight_inr: e.target.value })}
                        required
                        className="w-full text-xs p-2.5 bg-[#F7F5F0] border border-[#E6DED5] rounded-lg font-mono"
                      />
                    </label>

                    <label className="space-y-1">
                      <span className="text-xs font-bold text-[#29231F]">Initial Lat</span>
                      <input
                        type="text"
                        value={truckForm.latitude}
                        onChange={(e) => setTruckForm({ ...truckForm, latitude: e.target.value })}
                        required
                        className="w-full text-xs p-2.5 bg-[#F7F5F0] border border-[#E6DED5] rounded-lg font-mono"
                      />
                    </label>

                    <label className="space-y-1">
                      <span className="text-xs font-bold text-[#29231F]">Initial Lon</span>
                      <input
                        type="text"
                        value={truckForm.longitude}
                        onChange={(e) => setTruckForm({ ...truckForm, longitude: e.target.value })}
                        required
                        className="w-full text-xs p-2.5 bg-[#F7F5F0] border border-[#E6DED5] rounded-lg font-mono"
                      />
                    </label>
                  </div>

                  <button
                    type="submit"
                    disabled={busy}
                    className="w-full py-2.5 bg-[#5A3E2B] text-white font-bold text-xs rounded-lg hover:bg-[#432E20] transition disabled:opacity-50"
                  >
                    {busy ? "Registering..." : "Add Vehicle to Fleet"}
                  </button>
                </form>

                {/* Fleet Availability Toggles */}
                <div className="lg:col-span-6 bg-white rounded-xl border border-[#E6DED5] p-5 shadow-xs space-y-4">
                  <div className="flex items-center justify-between border-b border-[#E6DED5] pb-3">
                    <div>
                      <h3 className="font-bold text-sm text-[#29231F]">Fleet Duty Status</h3>
                      <p className="text-[11px] text-[#6E6259]">Toggle availability in real-time</p>
                    </div>
                    <span className="text-xs font-mono font-bold text-[#5A3E2B]">
                      {trucks.filter((t) => t.available).length}/{trucks.length} Online
                    </span>
                  </div>

                  <div className="space-y-2 max-h-[380px] overflow-y-auto">
                    {trucks.map((t) => (
                      <div
                        key={t.id}
                        className="p-3 bg-[#F7F5F0] rounded-lg border border-[#E6DED5] flex items-center justify-between gap-3"
                      >
                        <div className="flex items-center gap-2.5">
                          <div className="w-8 h-8 rounded-lg bg-white border border-[#E6DED5] flex items-center justify-center text-[#5A3E2B]">
                            <Truck size={16} />
                          </div>
                          <div>
                            <div className="text-xs font-bold text-[#29231F] font-mono">
                              {t.registration_no || t.id}
                            </div>
                            <div className="text-[10px] text-[#6E6259]">
                              {t.driver_name} · {t.vehicle_type} · {t.capacity_tonnes}T
                            </div>
                          </div>
                        </div>

                        <div className="flex items-center gap-1.5">
                          <button
                            onClick={() => {
                              setAssignmentTruck(t);
                              setShowAssignmentModal(true);
                            }}
                            className="text-[10px] font-bold px-2.5 py-1.5 rounded-lg bg-white hover:bg-[#EFECE6] border border-[#E6DED5] text-[#5A3E2B] transition cursor-pointer"
                            title="Assign Driver & Safety Holds"
                          >
                            Assign / Hold
                          </button>
                          <button
                            onClick={async () => {
                              await api.updateTruckAvailability(t.id, !t.available);
                              refresh();
                            }}
                            className={`text-[10px] font-bold px-3 py-1.5 rounded-lg border transition cursor-pointer ${
                              t.available
                                ? "bg-[#3F7D58] text-white border-[#3F7D58]"
                                : "bg-white text-[#6E6259] border-[#E6DED5] hover:bg-[#EFECE6]"
                            }`}
                          >
                            {t.available ? "ONLINE" : "OFFLINE"}
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* ============================================================== */}
          {/* MODULE G: BOOKINGS */}
          {/* ============================================================== */}
          {page === "Bookings" && (
            <div className="space-y-6">
              <div className="border-b border-[#E6DED5] pb-3">
                <span className="text-[10px] font-bold uppercase tracking-wider text-[#5A3E2B] bg-[#F0EAE1] px-2 py-0.5 rounded border border-[#E6DED5]">
                  Transaction & Milestone Management
                </span>
                <h2 className="text-xl font-black text-[#29231F] mt-1">Bookings & Active Shipments</h2>
                <p className="text-xs text-[#6E6259]">
                  Review contract requests and move freight through the 14-state shipment state machine.
                </p>
              </div>

              <div className="bg-white rounded-xl border border-[#E6DED5] overflow-hidden shadow-xs">
                <div className="overflow-x-auto">
                  <table className="w-full text-left border-collapse text-xs">
                    <thead>
                      <tr className="border-b border-[#E6DED5] bg-[#F7F5F0] text-[#6E6259] text-[11px] font-bold uppercase tracking-wider">
                        <th className="p-3.5">Booking ID</th>
                        <th className="p-3.5">Load Route</th>
                        <th className="p-3.5">Truck & Carrier</th>
                        <th className="p-3.5">Agreed Freight</th>
                        <th className="p-3.5">Status</th>
                        <th className="p-3.5 text-right">Lifecycle Actions</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-[#E6DED5]">
                      {bookings.map((b) => (
                        <tr key={b.id} className="hover:bg-[#FDFCFB] transition">
                          <td className="p-3.5 font-mono font-bold text-[#29231F]">
                            {b.id.slice(0, 8)}...
                          </td>
                          <td className="p-3.5">
                            <div className="font-bold text-[#29231F]">
                              {b.origin_name || "Kolkata"} → {b.destination_name || "Durgapur"}
                            </div>
                            <div className="text-[10px] text-[#6E6259]">Consignment: {b.load_id.slice(0, 8)}</div>
                          </td>
                          <td className="p-3.5">
                            <div className="font-mono font-bold text-[#29231F]">
                              {b.truck_registration_no || b.truck_id}
                            </div>
                            <div className="text-[10px] text-[#6E6259]">{b.driver_name || "Driver"}</div>
                          </td>
                          <td className="p-3.5 font-mono font-bold text-[#5A3E2B]">
                            {fmt(b.agreed_freight_inr)}
                          </td>
                          <td className="p-3.5">
                            <span
                              className={`text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded border ${
                                b.status === "CONFIRMED" || b.status === "ACCEPTED"
                                  ? "bg-[#EBF7EE] text-[#24613B] border-[#BDE5C8]"
                                  : b.status === "IN_TRANSIT"
                                  ? "bg-[#FEF3C7] text-[#92400E] border-[#FDE68A]"
                                  : b.status === "DELIVERED"
                                  ? "bg-[#E0E7FF] text-[#3730A3] border-[#C7D2FE]"
                                  : "bg-[#F7F5F0] text-[#6E6259] border-[#E6DED5]"
                              }`}
                            >
                              {b.status}
                            </span>
                          </td>
                          <td className="p-3.5 text-right space-x-1.5 whitespace-nowrap">
                            <button
                              onClick={() => {
                                setAgreementBookingId(b.id);
                                setShowAgreementModal(true);
                              }}
                              className="px-2.5 py-1 bg-[#F0EAE1] hover:bg-[#E6DED5] text-[#5A3E2B] border border-[#E6DED5] text-[11px] font-bold rounded inline-flex items-center gap-1 transition cursor-pointer"
                              title="Direct Freight Agreement & Signatures"
                            >
                              <FileText size={12} /> Agreement
                            </button>

                            <button
                              onClick={() => {
                                setCustodyShipmentId(b.id);
                                setShowCustodyModal(true);
                              }}
                              className="px-2 py-1 bg-[#F0EAE1] hover:bg-[#E6DED5] text-[#29231F] border border-[#E6DED5] text-[11px] font-bold rounded inline-flex items-center gap-1 transition cursor-pointer"
                              title="Digital Cargo Custody Handover & POD"
                            >
                              <Package size={12} /> Custody
                            </button>

                            <button
                              onClick={() => {
                                setInsuranceTargetId(b.id);
                                setShowInsuranceModal(true);
                              }}
                              className="px-2 py-1 bg-[#F0EAE1] hover:bg-[#E6DED5] text-indigo-700 border border-[#E6DED5] text-[11px] font-bold rounded inline-flex items-center gap-1 transition cursor-pointer"
                              title="Risk-Based Cargo Insurance Policy"
                            >
                              <ShieldCheck size={12} /> Insurance
                            </button>

                            <button
                              onClick={() => {
                                setPaymentsBookingId(b.id);
                                setShowPaymentsModal(true);
                              }}
                              className="px-2 py-1 bg-[#F0EAE1] hover:bg-[#E6DED5] text-emerald-700 border border-[#E6DED5] text-[11px] font-bold rounded inline-flex items-center gap-1 transition cursor-pointer"
                              title="Direct Freight Payment & Platform Invoices"
                            >
                              <CircleDollarSign size={12} /> Payment
                            </button>

                            <button
                              onClick={() => {
                                setDisputesBookingId(b.id);
                                setShowDisputesModal(true);
                              }}
                              className="px-2 py-1 bg-[#F0EAE1] hover:bg-[#E6DED5] text-amber-700 border border-[#E6DED5] text-[11px] font-bold rounded inline-flex items-center gap-1 transition cursor-pointer"
                              title="Open Dispute / File Claim"
                            >
                              <ShieldAlert size={12} /> Dispute
                            </button>

                            <button
                              onClick={() => {
                                setHistoryBookingId(b.id);
                                setShowHistoryModal(true);
                              }}
                              className="px-2 py-1 bg-[#F7F5F0] hover:bg-[#EFECE6] text-[#6E6259] border border-[#E6DED5] text-[11px] font-bold rounded inline-flex items-center gap-1 transition cursor-pointer"
                              title="Booking Lifecycle State Machine Transitions"
                            >
                              <History size={12} />
                            </button>

                            {(b.status === "PENDING" || b.status === "REQUESTED") && (
                              <button
                                onClick={() => updateBooking(b, "ACCEPTED")}
                                className="px-2.5 py-1 bg-[#3F7D58] text-white text-[11px] font-bold rounded hover:bg-[#346647] transition cursor-pointer"
                              >
                                Accept
                              </button>
                            )}
                            {(b.status === "ACCEPTED" || b.status === "CONFIRMED") && (
                              <button
                                onClick={() => updateBooking(b, "IN_TRANSIT")}
                                className="px-2.5 py-1 bg-[#B7791F] text-white text-[11px] font-bold rounded hover:bg-[#976319] transition cursor-pointer"
                              >
                                Start Trip
                              </button>
                            )}
                            {b.status === "IN_TRANSIT" && (
                              <button
                                onClick={() => updateBooking(b, "DELIVERED")}
                                className="px-2.5 py-1 bg-[#5A3E2B] text-white text-[11px] font-bold rounded hover:bg-[#432E20] transition cursor-pointer"
                              >
                                Mark Delivered
                              </button>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                {bookings.length === 0 && (
                  <div className="p-8 text-center text-xs text-[#6E6259] space-y-2">
                    <Package size={24} className="mx-auto text-[#8A796B]" />
                    <p>No bookings created yet. Find a suitable truck and dispatch a booking request.</p>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* ============================================================== */}
          {/* MODULE H: ADMIN CONTROL CENTRE */}
          {/* ============================================================== */}
          {page === "Admin" && (
            <div className="space-y-6">
              <div className="border-b border-[#E6DED5] pb-3 flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div>
                  <span className="text-[10px] font-bold uppercase tracking-wider text-[#29231F] bg-[#F0EAE1] px-2 py-0.5 rounded border border-[#E6DED5]">
                    Operations Control Tower
                  </span>
                  <h2 className="text-xl font-black text-[#29231F] mt-1">Platform Operational Snapshot</h2>
                  <p className="text-xs text-[#6E6259]">
                    Marketplace supply metrics, compliance verification queue, and system configuration.
                  </p>
                </div>
                <Link
                  href="/admin"
                  className="px-3.5 py-1.5 bg-[#29231F] text-white text-xs font-bold rounded-lg hover:bg-[#1A1715] transition flex items-center gap-1.5"
                >
                  <ExternalLink size={14} /> Full Control Tower View
                </Link>
              </div>

              {/* Admin Stats Grid */}
              <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                {[
                  ["Registered trucks", summary.trucks ?? trucks.length, Truck],
                  ["Registered loads", summary.loads ?? loads.length, Package],
                  ["Total bookings", summary.bookings ?? bookings.length, ArrowDownUp],
                  ["Available supply", summary.available_trucks ?? trucks.filter((t) => t.available).length, Activity],
                ].map(([l, v, Icon]: any) => (
                  <div key={l} className="bg-white rounded-xl border border-[#E6DED5] p-5 shadow-xs">
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-xs text-[#6E6259] font-bold">{l}</span>
                      <Icon size={16} className="text-[#5A3E2B]" />
                    </div>
                    <div className="text-2xl font-black font-mono text-[#29231F]">{v}</div>
                    <div className="text-[10px] text-[#8A796B]">Database count</div>
                  </div>
                ))}
              </div>

              {/* Truck Verification Queue Table */}
              <div className="bg-white rounded-xl border border-[#E6DED5] overflow-hidden shadow-xs space-y-2">
                <div className="p-4 border-b border-[#E6DED5]">
                  <h3 className="font-bold text-sm text-[#29231F]">Carrier Compliance & Verification Queue</h3>
                  <p className="text-[11px] text-[#6E6259]">Fleet records verified against RTO safety standards</p>
                </div>

                <div className="overflow-x-auto">
                  <table className="w-full text-left border-collapse text-xs">
                    <thead>
                      <tr className="border-b border-[#E6DED5] bg-[#F7F5F0] text-[#6E6259] text-[11px] font-bold uppercase tracking-wider">
                        <th className="p-3">Truck Reg</th>
                        <th className="p-3">Driver</th>
                        <th className="p-3">Vehicle Type</th>
                        <th className="p-3">Capacity</th>
                        <th className="p-3">Verification</th>
                        <th className="p-3">Documentation</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-[#E6DED5]">
                      {trucks.map((t) => (
                        <tr key={t.id} className="hover:bg-[#FDFCFB]">
                          <td className="p-3 font-mono font-bold text-[#29231F]">
                            {t.registration_no || t.id}
                          </td>
                          <td className="p-3 font-semibold text-[#29231F]">{t.driver_name}</td>
                          <td className="p-3 text-[#6E6259]">{t.vehicle_type}</td>
                          <td className="p-3 font-mono text-[#29231F]">{t.capacity_tonnes}T</td>
                          <td className="p-3">
                            <span
                              className={`text-[10px] font-bold px-2 py-0.5 rounded border ${
                                t.verified
                                  ? "bg-[#EBF7EE] text-[#24613B] border-[#BDE5C8]"
                                  : "bg-[#FEF3C7] text-[#92400E] border-[#FDE68A]"
                              }`}
                            >
                              {t.verified ? "Verified" : "Pending"}
                            </span>
                          </td>
                          <td className="p-3">
                            <span
                              className={`text-[10px] font-bold px-2 py-0.5 rounded border ${
                                t.documents_valid
                                  ? "bg-[#EBF7EE] text-[#24613B] border-[#BDE5C8]"
                                  : "bg-[#FAEDED] text-[#C53030] border-[#F1C4C4]"
                              }`}
                            >
                              {t.documents_valid ? "Valid" : "Review Required"}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}

          {/* ============================================================== */}
          {/* MODULE I: FLEET & DRIVERS (TRANSPORTER & FLEET MANAGER PORTAL) */}
          {/* ============================================================== */}
          {page === "Fleet & Drivers" && (
            <div className="space-y-6">
              <div className="border-b border-[#E6DED5] pb-3 flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div>
                  <span className="text-[10px] font-bold uppercase tracking-wider text-[#5A3E2B] bg-[#F0EAE1] px-2 py-0.5 rounded border border-[#E6DED5]">
                    Fleet Architecture & Driver Roster
                  </span>
                  <h2 className="text-xl font-black text-[#29231F] mt-1">Fleet Operations & Assignments</h2>
                  <p className="text-xs text-[#6E6259]">
                    Manage LoadLink-owned vehicles and external carrier fleets with automated driver assignment conflict prevention.
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-xs font-bold text-[#6E6259]">
                    <b>{trucks.filter((t) => t.ownership_type === "LOADLINK_OWNED").length}</b> Owned ·{" "}
                    <b>{trucks.filter((t) => t.ownership_type !== "LOADLINK_OWNED").length}</b> External Carriers
                  </span>
                </div>
              </div>

              {/* Fleet Cards Grid */}
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {trucks.map((t) => {
                  const isHeld = t.status === "SAFETY_HOLD";
                  const isMaint = t.status === "MAINTENANCE";
                  return (
                    <div key={t.id} className="bg-white rounded-xl border border-[#E6DED5] p-5 shadow-xs space-y-3">
                      <div className="flex items-start justify-between">
                        <div>
                          <span
                            className={`text-[9px] uppercase font-bold tracking-wider px-2 py-0.5 rounded-full border ${
                              t.ownership_type === "LOADLINK_OWNED"
                                ? "bg-[#E0E7FF] text-[#3730A3] border-[#C7D2FE]"
                                : "bg-[#F0EAE1] text-[#5A3E2B] border-[#E6DED5]"
                            }`}
                          >
                            {t.ownership_type === "LOADLINK_OWNED" ? "LoadLink Owned" : "External Carrier"}
                          </span>
                          <div className="text-base font-black font-mono text-[#29231F] mt-1">
                            {t.registration_no || t.id}
                          </div>
                          <div className="text-[11px] text-[#6E6259]">
                            {t.organization_name || "Commercial Carrier Organization"}
                          </div>
                        </div>

                        <span
                          className={`text-[10px] font-bold px-2 py-0.5 rounded-full border ${
                            isHeld
                              ? "bg-[#FAEDED] text-[#C53030] border-[#F1C4C4]"
                              : isMaint
                              ? "bg-[#FEF3C7] text-[#92400E] border-[#FDE68A]"
                              : t.available
                              ? "bg-[#EBF7EE] text-[#24613B] border-[#BDE5C8]"
                              : "bg-[#F7F5F0] text-[#6E6259] border-[#E6DED5]"
                          }`}
                        >
                          {t.status || (t.available ? "ONLINE" : "OFFLINE")}
                        </span>
                      </div>

                      <div className="p-3 bg-[#F7F5F0] rounded-lg border border-[#E6DED5] space-y-1.5 text-xs">
                        <div className="flex items-center justify-between">
                          <span className="text-[#6E6259]">Assigned Driver:</span>
                          <span className="font-bold text-[#29231F]">{t.driver_name || "Unassigned"}</span>
                        </div>
                        <div className="flex items-center justify-between">
                          <span className="text-[#6E6259]">Vehicle Specs:</span>
                          <span className="font-semibold text-[#29231F]">
                            {t.vehicle_type} · {t.capacity_tonnes}T
                          </span>
                        </div>
                        <div className="flex items-center justify-between">
                          <span className="text-[#6E6259]">Driver Phone:</span>
                          <span className="font-mono text-[#29231F]">{t.driver_phone || "—"}</span>
                        </div>
                        <div className="flex items-center justify-between">
                          <span className="text-[#6E6259]">Trust Score:</span>
                          <span className="font-bold text-[#3F7D58]">{t.reliability_score || 88}/100</span>
                        </div>
                      </div>

                      {isHeld && (
                        <div className="p-2 bg-[#FAEDED] rounded border border-[#F1C4C4] text-[10px] text-[#C53030] font-medium flex items-center gap-1.5">
                          <AlertCircle size={12} />
                          <span>SAFETY HOLD: Hard-filtered from matching engine.</span>
                        </div>
                      )}
                      {isMaint && (
                        <div className="p-2 bg-[#FEF3C7] rounded border border-[#FDE68A] text-[10px] text-[#92400E] font-medium flex items-center gap-1.5">
                          <AlertCircle size={12} />
                          <span>MAINTENANCE: Excluded from candidate ranking.</span>
                        </div>
                      )}

                      <div className="pt-1">
                        <button
                          onClick={() => {
                            setAssignmentTruck(t);
                            setShowAssignmentModal(true);
                          }}
                          className="w-full py-2 bg-[#5A3E2B] hover:bg-[#432E20] text-white text-xs font-bold rounded-lg transition flex items-center justify-center gap-1.5 cursor-pointer shadow-xs"
                        >
                          <Users size={13} /> Driver Assignment & Compliance
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* ============================================================== */}
          {/* MODULE J: DIRECT FREIGHT AGREEMENTS (MARKETPLACE CONTRACTS)     */}
          {/* ============================================================== */}
          {page === "Agreements" && (
            <div className="space-y-6">
              <div className="border-b border-[#E6DED5] pb-3 flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div>
                  <span className="text-[10px] font-bold uppercase tracking-wider text-[#5A3E2B] bg-[#F0EAE1] px-2 py-0.5 rounded border border-[#E6DED5]">
                    Marketplace Legal Architecture
                  </span>
                  <h2 className="text-xl font-black text-[#29231F] mt-1">Direct Freight Agreements</h2>
                  <p className="text-xs text-[#6E6259]">
                    Verifiable contracts directly between Shippers and Carriers with SHA-256 canonical hashing and mutual assent.
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-xs font-bold text-[#6E6259]">
                    <b>{bookings.length}</b> Active Contract Records
                  </span>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {bookings.map((b) => (
                  <div key={b.id} className="bg-white rounded-xl border border-[#E6DED5] p-5 shadow-xs space-y-4">
                    <div className="flex items-start justify-between">
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="font-mono font-bold text-xs text-[#29231F]">
                            Booking: {b.id.slice(0, 8)}...
                          </span>
                          <span className="text-[9px] font-bold px-2 py-0.5 rounded-full bg-[#F0EAE1] text-[#5A3E2B] border border-[#E6DED5]">
                            Agreement v1.0
                          </span>
                        </div>
                        <div className="font-bold text-sm text-[#29231F] mt-1">
                          {b.origin_name || "Kolkata"} → {b.destination_name || "Durgapur"}
                        </div>
                      </div>
                      <div className="text-right">
                        <div className="text-base font-black font-mono text-[#5A3E2B]">
                          {fmt(b.agreed_freight_inr)}
                        </div>
                        <span className="text-[9px] font-bold uppercase tracking-wider px-2 py-0.5 rounded bg-[#EBF7EE] text-[#24613B] border border-[#BDE5C8]">
                          {b.status}
                        </span>
                      </div>
                    </div>

                    <div className="p-3 bg-[#F7F5F0] rounded-lg border border-[#E6DED5] space-y-1.5 text-xs">
                      <div className="flex items-center justify-between">
                        <span className="text-[#6E6259]">Assigned Carrier:</span>
                        <span className="font-mono font-bold text-[#29231F]">
                          {b.truck_registration_no || b.truck_id}
                        </span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-[#6E6259]">Driver:</span>
                        <span className="font-semibold text-[#29231F]">{b.driver_name || "Assigned Driver"}</span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-[#6E6259]">Consignment:</span>
                        <span className="font-mono text-[#6E6259]">{b.load_id.slice(0, 10)}...</span>
                      </div>
                    </div>

                    <div className="flex items-center gap-2 pt-1">
                      <button
                        onClick={() => {
                          setAgreementBookingId(b.id);
                          setShowAgreementModal(true);
                        }}
                        className="flex-1 py-2 bg-[#5A3E2B] hover:bg-[#432E20] text-white text-xs font-bold rounded-lg transition flex items-center justify-center gap-1.5 cursor-pointer shadow-xs"
                      >
                        <FileText size={14} /> Review & Sign Agreement
                      </button>
                      <button
                        onClick={() => {
                          setHistoryBookingId(b.id);
                          setShowHistoryModal(true);
                        }}
                        className="py-2 px-3 bg-[#F7F5F0] hover:bg-[#EFECE6] border border-[#E6DED5] text-[#29231F] text-xs font-bold rounded-lg transition flex items-center gap-1 cursor-pointer"
                        title="Lifecycle Transition Audit Log"
                      >
                        <History size={14} />
                      </button>
                    </div>
                  </div>
                ))}

                {bookings.length === 0 && (
                  <div className="col-span-2 p-12 bg-white rounded-xl border border-[#E6DED5] text-center space-y-2">
                    <FileText size={32} className="mx-auto text-[#8A796B]" />
                    <h3 className="font-bold text-sm text-[#29231F]">No Freight Agreements Yet</h3>
                    <p className="text-xs text-[#6E6259]">
                      Agreements are automatically established when booking requests are initiated between Shippers and Carriers.
                    </p>
                  </div>
                )}
              </div>
            </div>
          )}
          {/* ============================================================== */}
          {/* 10. CARGO CUSTODY & HANDOVER PAGE */}
          {/* ============================================================== */}
          {page === "Cargo Custody" && (
            <div className="space-y-6">
              <div className="p-4 bg-white rounded-xl border border-[#E6DED5] flex flex-col sm:flex-row sm:items-center justify-between gap-4 shadow-2xs">
                <div>
                  <h2 className="text-sm font-bold text-[#29231F]">Digital Cargo Custody Handover</h2>
                  <p className="text-xs text-[#6E6259]">
                    Inspect loading seals, transit condition reports, receiver OTP validations, and tamper-evident digital PODs.
                  </p>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {bookings.map((b) => (
                  <div
                    key={b.id}
                    className="p-5 bg-white rounded-xl border border-[#E6DED5] shadow-2xs space-y-4 hover:border-[#8A796B] transition"
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-mono font-bold text-[#5A3E2B]">
                        BOOKING #{b.id.slice(0, 8)}
                      </span>
                      <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-[#EFECE6] text-[#29231F] border border-[#E6DED5]">
                        {b.status}
                      </span>
                    </div>

                    <div className="space-y-1">
                      <div className="text-sm font-bold text-[#29231F]">
                        {b.origin} → {b.destination}
                      </div>
                      <div className="text-xs text-[#6E6259]">
                        Consignment Weight: <b>{b.required_tonnes || 0} MT</b> · Truck: <b>{b.truck_id ? b.truck_id.slice(0, 10) : "Assigned"}</b>
                      </div>
                    </div>

                    <button
                      onClick={() => {
                        setCustodyShipmentId(b.id);
                        setShowCustodyModal(true);
                      }}
                      className="w-full py-2 bg-[#5A3E2B] hover:bg-[#432E20] text-white text-xs font-bold rounded-lg transition flex items-center justify-center gap-1.5 cursor-pointer"
                    >
                      <Package size={14} /> Open Digital Custody Handover Log & POD
                    </button>
                  </div>
                ))}

                {bookings.length === 0 && (
                  <div className="col-span-2 p-12 bg-white rounded-xl border border-[#E6DED5] text-center space-y-2">
                    <Package size={32} className="mx-auto text-[#8A796B]" />
                    <h3 className="font-bold text-sm text-[#29231F]">No Active Custody Consignments</h3>
                    <p className="text-xs text-[#6E6259]">
                      Dispatch bookings to inspect loading seals, highway incidents, and consignee delivery handovers.
                    </p>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* ============================================================== */}
          {/* 11. RISK-BASED INSURANCE PAGE */}
          {/* ============================================================== */}
          {page === "Risk Insurance" && (
            <div className="space-y-6">
              <div className="p-4 bg-white rounded-xl border border-[#E6DED5] flex flex-col sm:flex-row sm:items-center justify-between gap-4 shadow-2xs">
                <div>
                  <h2 className="text-sm font-bold text-[#29231F]">Risk-Based Cargo Insurance Underwriting</h2>
                  <p className="text-xs text-[#6E6259]">
                    Configurable transit insurance policies, compliance dispatch gates, and certificate authentication.
                  </p>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {bookings.map((b) => (
                  <div
                    key={b.id}
                    className="p-5 bg-white rounded-xl border border-[#E6DED5] shadow-2xs space-y-4 hover:border-indigo-400 transition"
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-mono font-bold text-indigo-900">
                        CONSIGNMENT #{b.id.slice(0, 8)}
                      </span>
                      <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-indigo-50 text-indigo-700 border border-indigo-200">
                        CORRIDOR UNDERWRITING
                      </span>
                    </div>

                    <div className="space-y-1">
                      <div className="text-sm font-bold text-[#29231F]">
                        {b.origin} → {b.destination}
                      </div>
                      <div className="text-xs text-[#6E6259]">
                        Consignment Freight: <b>{fmt(b.budget_inr || 0)}</b> · Weight: <b>{b.required_tonnes || 0} MT</b>
                      </div>
                    </div>

                    <button
                      onClick={() => {
                        setInsuranceTargetId(b.id);
                        setShowInsuranceModal(true);
                      }}
                      className="w-full py-2 bg-indigo-700 hover:bg-indigo-600 text-white text-xs font-bold rounded-lg transition flex items-center justify-center gap-1.5 cursor-pointer"
                    >
                      <ShieldCheck size={14} /> Assess Underwriting Risk & Verify Policy
                    </button>
                  </div>
                ))}

                {bookings.length === 0 && (
                  <div className="col-span-2 p-12 bg-white rounded-xl border border-[#E6DED5] text-center space-y-2">
                    <ShieldCheck size={32} className="mx-auto text-[#8A796B]" />
                    <h3 className="font-bold text-sm text-[#29231F]">No Consignments for Insurance Review</h3>
                    <p className="text-xs text-[#6E6259]">
                      Loads and shipments requiring insurance verification will appear here for compliance clearance.
                    </p>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* ============================================================== */}
          {/* 12. DIRECT FREIGHT PAYMENTS & FEES PAGE */}
          {/* ============================================================== */}
          {page === "Direct Payments" && (
            <div className="space-y-6">
              <div className="p-4 bg-white rounded-xl border border-[#E6DED5] flex flex-col sm:flex-row sm:items-center justify-between gap-4 shadow-2xs">
                <div>
                  <h2 className="text-sm font-bold text-[#29231F]">Direct Freight Payments & Platform Invoices</h2>
                  <p className="text-xs text-[#6E6259]">
                    Dealer-to-Transporter direct settlement tracking and separate LoadLink service fee tax invoices.
                  </p>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {bookings.map((b) => (
                  <div
                    key={b.id}
                    className="p-5 bg-white rounded-xl border border-[#E6DED5] shadow-2xs space-y-4 hover:border-emerald-400 transition"
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-mono font-bold text-emerald-900">
                        SETTLEMENT #{b.id.slice(0, 8)}
                      </span>
                      <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200">
                        DIRECT SETTLEMENT
                      </span>
                    </div>

                    <div className="space-y-1">
                      <div className="text-sm font-bold text-[#29231F]">
                        Agreed Freight: <span className="text-emerald-700">{fmt(b.budget_inr || 0)}</span>
                      </div>
                      <div className="text-xs text-[#6E6259]">
                        Route: {b.origin} → {b.destination} · Transporter Direct Payee
                      </div>
                    </div>

                    <button
                      onClick={() => {
                        setPaymentsBookingId(b.id);
                        setShowPaymentsModal(true);
                      }}
                      className="w-full py-2 bg-emerald-700 hover:bg-emerald-600 text-white text-xs font-bold rounded-lg transition flex items-center justify-center gap-1.5 cursor-pointer"
                    >
                      <CircleDollarSign size={14} /> Manage Freight Transfer & View Platform Invoice
                    </button>
                  </div>
                ))}

                {bookings.length === 0 && (
                  <div className="col-span-2 p-12 bg-white rounded-xl border border-[#E6DED5] text-center space-y-2">
                    <CircleDollarSign size={32} className="mx-auto text-[#8A796B]" />
                    <h3 className="font-bold text-sm text-[#29231F]">No Active Payment Records</h3>
                    <p className="text-xs text-[#6E6259]">
                      Direct freight payment settlements and platform fee invoices are generated upon booking creation.
                    </p>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* ============================================================== */}
          {/* 13. DISPUTES & GRIEVANCES PAGE */}
          {/* ============================================================== */}
          {page === "Disputes & Grievances" && (
            <div className="space-y-6">
              <div className="p-4 bg-white rounded-xl border border-[#E6DED5] flex flex-col sm:flex-row sm:items-center justify-between gap-4 shadow-2xs">
                <div>
                  <h2 className="text-sm font-bold text-[#29231F]">Dispute Adjudication & Grievance Desk</h2>
                  <p className="text-xs text-[#6E6259]">
                    11 claim categories, evidence logs, SLA timestamps, and AI-assisted dispute triage.
                  </p>
                </div>
                <button
                  onClick={() => {
                    setDisputesBookingId(null);
                    setShowDisputesModal(true);
                  }}
                  className="py-2 px-4 bg-amber-700 hover:bg-amber-600 text-white text-xs font-bold rounded-lg transition flex items-center gap-1.5 cursor-pointer"
                >
                  <ShieldAlert size={14} /> Open Case / File Claim
                </button>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {bookings.map((b) => (
                  <div
                    key={b.id}
                    className="p-5 bg-white rounded-xl border border-[#E6DED5] shadow-2xs space-y-4 hover:border-amber-400 transition"
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-mono font-bold text-amber-900">
                        CONSIGNMENT #{b.id.slice(0, 8)}
                      </span>
                      <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-amber-50 text-amber-700 border border-amber-200">
                        CLAIMS DESK
                      </span>
                    </div>

                    <div className="space-y-1">
                      <div className="text-sm font-bold text-[#29231F]">
                        {b.origin} → {b.destination}
                      </div>
                      <div className="text-xs text-[#6E6259]">
                        Consignment Value at Risk: <b>{fmt(b.budget_inr || 0)}</b>
                      </div>
                    </div>

                    <button
                      onClick={() => {
                        setDisputesBookingId(b.id);
                        setShowDisputesModal(true);
                      }}
                      className="w-full py-2 bg-amber-700 hover:bg-amber-600 text-white text-xs font-bold rounded-lg transition flex items-center justify-center gap-1.5 cursor-pointer"
                    >
                      <ShieldAlert size={14} /> Inspect Claims, Evidence & Grievances
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* ============================================================== */}
          {/* 14. CONTROL ROOM (SOS & HIGHWAY EMERGENCIES) */}
          {/* ============================================================== */}
          {page === "Control Room" && (
            <div className="space-y-6">
              <ControlRoomView />
            </div>
          )}
        </div>

        {/* Global Footer */}
        <footer className="mt-auto border-t border-[#E6DED5] px-6 py-4 bg-white text-[11px] text-[#6E6259] flex flex-col sm:flex-row items-center justify-between gap-2">
          <span>© 2026 LOADLINK AI · WEST BENGAL FREIGHT CORRIDOR MVP 1.0</span>
          <div className="flex items-center gap-4 text-[10px] text-[#8A796B]">
            <span>SMARTER FREIGHT. BETTER UTILIZATION.</span>
            <span>•</span>
            <span>MAP DATA © OPENSTREETMAP CONTRIBUTORS</span>
          </div>
        </footer>
      </main>

      {/* Modals for Master Prompt 1 Architecture */}
      {showAgreementModal && agreementBookingId && (
        <DirectFreightAgreementModal
          isOpen={showAgreementModal}
          onClose={() => {
            setShowAgreementModal(false);
            setAgreementBookingId(null);
          }}
          bookingId={agreementBookingId}
          currentUser={currentUser}
          onAgreementUpdated={refresh}
        />
      )}

      {showAssignmentModal && assignmentTruck && (
        <VehicleAssignmentModal
          isOpen={showAssignmentModal}
          onClose={() => {
            setShowAssignmentModal(false);
            setAssignmentTruck(null);
          }}
          truck={assignmentTruck}
          currentUser={currentUser}
          onTruckUpdated={refresh}
        />
      )}

      {showHistoryModal && historyBookingId && (
        <BookingHistoryModal
          isOpen={showHistoryModal}
          onClose={() => {
            setShowHistoryModal(false);
            setHistoryBookingId(null);
          }}
          bookingId={historyBookingId}
        />
      )}

      {/* Master Prompt 2 Modals */}
      {showCustodyModal && custodyShipmentId && (
        <CustodyModal
          isOpen={showCustodyModal}
          onClose={() => {
            setShowCustodyModal(false);
            setCustodyShipmentId(null);
          }}
          shipmentId={custodyShipmentId}
          currentUser={currentUser}
          onStatusUpdated={refresh}
        />
      )}

      {showInsuranceModal && insuranceTargetId && (
        <InsuranceModal
          isOpen={showInsuranceModal}
          onClose={() => {
            setShowInsuranceModal(false);
            setInsuranceTargetId(null);
          }}
          targetId={insuranceTargetId}
          currentUser={currentUser}
          onStatusUpdated={refresh}
        />
      )}

      {showPaymentsModal && paymentsBookingId && (
        <PaymentsModal
          isOpen={showPaymentsModal}
          onClose={() => {
            setShowPaymentsModal(false);
            setPaymentsBookingId(null);
          }}
          bookingId={paymentsBookingId}
          currentUser={currentUser}
          onStatusUpdated={refresh}
        />
      )}

      {showDisputesModal && (
        <DisputesModal
          isOpen={showDisputesModal}
          onClose={() => {
            setShowDisputesModal(false);
            setDisputesBookingId(null);
          }}
          bookingId={disputesBookingId || undefined}
          currentUser={currentUser}
          onStatusUpdated={refresh}
        />
      )}
    </div>
  );
}
