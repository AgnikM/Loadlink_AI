"use client";

import React, { useEffect, useRef, useState } from "react";

interface FreightMapProps {
  origin?: { lat: number; lon: number; name: string };
  destination?: { lat: number; lon: number; name: string };
  truckLocation?: { lat: number; lon: number; regNo?: string; isStale?: boolean };
  corridorWaypoints?: Array<[number, number]>;
  additionalTrucks?: Array<{ lat: number; lon: number; regNo: string; status: string; reliability: number }>;
  height?: string;
  zoom?: number;
  center?: [number, number];
  interactive?: boolean;
}

export default function FreightMap({
  origin,
  destination,
  truckLocation,
  corridorWaypoints,
  additionalTrucks,
  height = "420px",
  zoom = 8,
  center = [23.1, 87.8],
  interactive = true,
}: FreightMapProps) {
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<any>(null);
  const layerGroupRef = useRef<any>(null);
  const [isClient, setIsClient] = useState(false);

  // Keep stable reference for initial center and zoom
  const initialCenterRef = useRef<[number, number]>(origin ? [origin.lat, origin.lon] : center);
  const initialZoomRef = useRef<number>(zoom);

  useEffect(() => {
    setIsClient(true);
  }, []);

  // 1. Initialize Leaflet Map instance EXACTLY ONCE on client mount
  useEffect(() => {
    if (!isClient || !mapContainerRef.current) return;

    let isCancelled = false;

    import("leaflet").then((L) => {
      if (isCancelled || !mapContainerRef.current) return;

      // Defensive lifecycle patches on Leaflet prototypes to prevent _leaflet_pos runtime errors
      if (L.DomUtil && L.DomUtil.getPosition) {
        const origGetPosition = L.DomUtil.getPosition;
        L.DomUtil.getPosition = function (el: HTMLElement) {
          if (!el || typeof el !== "object") {
            return new L.Point(0, 0);
          }
          return origGetPosition.call(this, el);
        };
      }

      if (L.Map && (L.Map.prototype as any) && (L.Map.prototype as any)._getMapPanePos) {
        const origGetMapPanePos = (L.Map.prototype as any)._getMapPanePos;
        (L.Map.prototype as any)._getMapPanePos = function () {
          if (!(this as any)._mapPane) {
            return new L.Point(0, 0);
          }
          return origGetMapPanePos.call(this);
        };
      }

      // Fix Leaflet ScrollWheelZoom timer cleanup bug in removeHooks and guard _performZoom
      if (L.Map && (L.Map as any).ScrollWheelZoom) {
        const SWZ = (L.Map as any).ScrollWheelZoom;
        const origRemoveHooks = SWZ.prototype.removeHooks;
        SWZ.prototype.removeHooks = function () {
          if (this._timer) {
            clearTimeout(this._timer);
            this._timer = null;
          }
          this._delta = 0;
          this._startTime = null;
          if (origRemoveHooks) origRemoveHooks.call(this);
        };

        const origPerformZoom = SWZ.prototype._performZoom;
        SWZ.prototype._performZoom = function () {
          if (!this._map || !this._map._mapPane || !this._map._container) {
            this._delta = 0;
            this._startTime = null;
            return;
          }
          origPerformZoom.call(this);
        };
      }

      // If map is already initialized on this container, reuse it
      if (mapInstanceRef.current) return;

      // Clean up any stale container leaflet id before fresh init
      if ((mapContainerRef.current as any)._leaflet_id) {
        delete (mapContainerRef.current as any)._leaflet_id;
      }

      const map = L.map(mapContainerRef.current, {
        preferCanvas: true,
        zoomAnimation: false,
        fadeAnimation: false,
        markerZoomAnimation: false,
        scrollWheelZoom: interactive,
        dragging: interactive,
        wheelDebounceTime: 40,
      }).setView(initialCenterRef.current, initialZoomRef.current);

      mapInstanceRef.current = map;

      // Standard OpenStreetMap tiles (watermark-free)
      L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
        maxZoom: 19,
      }).addTo(map);

      // Dedicated layer group for dynamic markers and route polylines
      layerGroupRef.current = L.layerGroup().addTo(map);

      // Trigger initial resize invalidate
      setTimeout(() => {
        if (!isCancelled && mapInstanceRef.current) {
          try {
            mapInstanceRef.current.invalidateSize({ debounceMoveend: true });
          } catch {}
        }
      }, 60);
    });

    return () => {
      isCancelled = true;
      const map = mapInstanceRef.current;
      if (map) {
        // Cancel any pending scroll wheel zoom timer
        if (map.scrollWheelZoom && (map.scrollWheelZoom as any)._timer) {
          clearTimeout((map.scrollWheelZoom as any)._timer);
          (map.scrollWheelZoom as any)._timer = null;
        }
        try { map.scrollWheelZoom?.disable(); } catch {}
        try { map.dragging?.disable(); } catch {}
        try { map.touchZoom?.disable(); } catch {}
        try { map.doubleClickZoom?.disable(); } catch {}
        try { map.boxZoom?.disable(); } catch {}
        try { map.keyboard?.disable(); } catch {}
        try { map.stop(); } catch {}
        try { layerGroupRef.current?.clearLayers(); } catch {}
        try { map.remove(); } catch {}
        mapInstanceRef.current = null;
        layerGroupRef.current = null;
      }
      if (mapContainerRef.current && (mapContainerRef.current as any)._leaflet_id) {
        delete (mapContainerRef.current as any)._leaflet_id;
      }
    };
  }, [isClient]);

  // 2. Toggle interaction when interactive prop changes
  useEffect(() => {
    const map = mapInstanceRef.current;
    if (!map) return;
    if (interactive) {
      map.scrollWheelZoom?.enable();
      map.dragging?.enable();
    } else {
      if (map.scrollWheelZoom && (map.scrollWheelZoom as any)._timer) {
        clearTimeout((map.scrollWheelZoom as any)._timer);
        (map.scrollWheelZoom as any)._timer = null;
      }
      map.scrollWheelZoom?.disable();
      map.dragging?.disable();
    }
  }, [interactive]);

  // 3. Update markers and route polylines whenever data props change (WITHOUT destroying map)
  useEffect(() => {
    if (!isClient || !mapInstanceRef.current || !layerGroupRef.current) return;

    import("leaflet").then((L) => {
      const map = mapInstanceRef.current;
      const layerGroup = layerGroupRef.current;
      if (!map || !layerGroup) return;

      // Clear existing markers cleanly inside the layer group
      layerGroup.clearLayers();

      // Custom DivIcons using warm enterprise palette
      const originIcon = L.divIcon({
        className: "custom-map-icon",
        html: `<div style="background: #5A3E2B; width: 28px; height: 28px; border-radius: 50%; display: flex; align-items: center; justify-content: center; border: 2px solid white; box-shadow: 0 2px 8px rgba(90,62,43,0.35); font-weight: 700; font-size: 12px; color: white;">A</div>`,
        iconSize: [28, 28],
        iconAnchor: [14, 14],
      });

      const destIcon = L.divIcon({
        className: "custom-map-icon",
        html: `<div style="background: #3F7D58; width: 28px; height: 28px; border-radius: 50%; display: flex; align-items: center; justify-content: center; border: 2px solid white; box-shadow: 0 2px 8px rgba(63,125,88,0.35); font-weight: 700; font-size: 12px; color: white;">B</div>`,
        iconSize: [28, 28],
        iconAnchor: [14, 14],
      });

      const truckIcon = L.divIcon({
        className: "custom-map-icon",
        html: `<div style="background: #B7791F; width: 34px; height: 34px; border-radius: 8px; display: flex; align-items: center; justify-content: center; border: 2px solid #fff; box-shadow: 0 3px 10px rgba(183,121,31,0.4); font-size: 17px;">🚚</div>`,
        iconSize: [34, 34],
        iconAnchor: [17, 17],
      });

      const genericTruckIcon = L.divIcon({
        className: "custom-map-icon",
        html: `<div style="background: #8A796B; width: 26px; height: 26px; border-radius: 6px; display: flex; align-items: center; justify-content: center; border: 1.5px solid #fff; box-shadow: 0 2px 6px rgba(0,0,0,0.25); font-size: 13px;">🚛</div>`,
        iconSize: [26, 26],
        iconAnchor: [13, 13],
      });

      const bounds: any[] = [];

      // Add Origin Marker
      if (origin) {
        L.marker([origin.lat, origin.lon], { icon: originIcon })
          .bindPopup(`<strong>Pickup Origin</strong><br/>${origin.name}`)
          .addTo(layerGroup);
        bounds.push([origin.lat, origin.lon]);
      }

      // Add Destination Marker
      if (destination) {
        L.marker([destination.lat, destination.lon], { icon: destIcon })
          .bindPopup(`<strong>Delivery Destination</strong><br/>${destination.name}`)
          .addTo(layerGroup);
        bounds.push([destination.lat, destination.lon]);
      }

      // Add Assigned Truck Marker
      if (truckLocation) {
        L.marker([truckLocation.lat, truckLocation.lon], { icon: truckIcon })
          .bindPopup(
            `<strong>Assigned Truck: ${truckLocation.regNo || "Live GPS"}</strong><br/>${
              truckLocation.isStale
                ? "<span style='color:#C53030; font-weight:600;'>Signal Stale (>15m)</span>"
                : "<span style='color:#3F7D58; font-weight:600;'>Live Tracking Active</span>"
            }`
          )
          .addTo(layerGroup);
        bounds.push([truckLocation.lat, truckLocation.lon]);
      }

      // Draw Polyline Route
      let polylinePoints: [number, number][] = [];
      if (corridorWaypoints && corridorWaypoints.length > 0) {
        polylinePoints = corridorWaypoints;
      } else if (origin && destination) {
        polylinePoints = [
          [origin.lat, origin.lon],
          [destination.lat, destination.lon],
        ];
      }

      if (polylinePoints.length > 0) {
        L.polyline(polylinePoints, {
          color: "#5A3E2B",
          weight: 4,
          opacity: 0.85,
          dashArray: "6, 6",
        }).addTo(layerGroup);
      }

      // Add Fleet Trucks
      if (additionalTrucks && additionalTrucks.length > 0) {
        additionalTrucks.forEach((t) => {
          L.marker([t.lat, t.lon], { icon: genericTruckIcon })
            .bindPopup(`<strong>${t.regNo}</strong><br/>Status: ${t.status}<br/>Reliability: ${t.reliability}%`)
            .addTo(layerGroup);
          bounds.push([t.lat, t.lon]);
        });
      }

      // Fit bounds without animation to prevent Leaflet _leaflet_pos race conditions
      if (bounds.length > 1) {
        try {
          map.fitBounds(bounds, { padding: [40, 40], maxZoom: 14, animate: false });
        } catch {}
      }
    });
  }, [isClient, origin, destination, truckLocation, corridorWaypoints, additionalTrucks]);

  return (
    <div
      style={{ height, minHeight: height, maxHeight: height }}
      className={`w-full rounded-xl overflow-hidden relative isolate z-0 border border-[#E6DED5] shadow-sm bg-[#F7F5F0] ${
        !interactive ? "pointer-events-none" : ""
      }`}
    >
      <div
        ref={mapContainerRef}
        className="w-full h-full relative overflow-hidden"
        style={{ minHeight: height }}
      />

      {/* Corridor Legend Overlay - Warm Enterprise */}
      <div className="absolute bottom-3 left-3 z-10 bg-white/95 backdrop-blur-md px-3.5 py-2 rounded-lg border border-[#E6DED5] text-[11px] font-medium flex items-center gap-3.5 text-[#29231F] shadow-sm pointer-events-none">
        <div className="flex items-center gap-1.5">
          <span className="w-2.5 h-2.5 rounded-full bg-[#5A3E2B] inline-block" />
          <span>Pickup Origin</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="w-2.5 h-2.5 rounded-full bg-[#3F7D58] inline-block" />
          <span>Destination</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="w-2.5 h-2.5 rounded bg-[#B7791F] inline-block" />
          <span>Assigned Truck</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="w-2 h-2 rounded bg-[#8A796B] inline-block" />
          <span>Corridor Fleet</span>
        </div>
      </div>
    </div>
  );
}
