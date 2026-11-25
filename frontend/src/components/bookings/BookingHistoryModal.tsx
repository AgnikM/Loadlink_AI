"use client";

import React, { useState, useEffect, useCallback } from "react";
import { X, Clock, CheckCircle2, History, GitCommit, UserCheck, ShieldCheck } from "lucide-react";
import { BookingStateHistory } from "@/types";
import { api } from "@/lib/api";

interface BookingHistoryModalProps {
  isOpen: boolean;
  onClose: () => void;
  bookingId: string;
}

export default function BookingHistoryModal({
  isOpen,
  onClose,
  bookingId,
}: BookingHistoryModalProps) {
  const [history, setHistory] = useState<BookingStateHistory[]>([]);
  const [loading, setLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState("");

  const loadHistory = useCallback(async () => {
    if (!bookingId) return;
    setLoading(true);
    setErrorMsg("");
    try {
      const data = await api.getBookingHistory(bookingId);
      setHistory(data || []);
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to load state history");
    } finally {
      setLoading(false);
    }
  }, [bookingId]);

  useEffect(() => {
    if (isOpen) {
      loadHistory();
    }
  }, [isOpen, loadHistory]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4 overflow-y-auto">
      <div className="bg-white border border-[#E6DED5] rounded-2xl w-full max-w-xl max-h-[85vh] flex flex-col shadow-2xl overflow-hidden my-auto animate-in fade-in zoom-in-95 duration-150">
        {/* Header */}
        <div className="p-5 border-b border-[#E6DED5] flex items-center justify-between bg-[#FDFCFB]">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-[#5A3E2B] text-white flex items-center justify-center shadow-xs">
              <History size={20} />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="font-bold text-base text-[#29231F]">Booking Lifecycle History</h3>
                <span className="font-mono font-bold text-xs px-2 py-0.5 rounded-full bg-[#F0EAE1] text-[#5A3E2B] border border-[#E6DED5]">
                  {bookingId.slice(0, 8)}...
                </span>
              </div>
              <p className="text-xs text-[#6E6259]">
                State machine transitions, pre-dispatch verification & audit records
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 text-[#6E6259] hover:text-[#29231F] hover:bg-[#F7F5F0] rounded-lg transition cursor-pointer"
          >
            <X size={18} />
          </button>
        </div>

        {/* Body */}
        <div className="p-6 overflow-y-auto space-y-4 text-xs text-[#29231F]">
          {loading ? (
            <div className="py-10 text-center text-[#6E6259] space-y-2">
              <Clock size={24} className="mx-auto animate-spin text-[#5A3E2B]" />
              <p>Loading lifecycle audit log...</p>
            </div>
          ) : errorMsg ? (
            <div className="p-4 bg-[#FAEDED] border border-[#F1C4C4] rounded-xl text-[#C53030]">
              {errorMsg}
            </div>
          ) : history.length === 0 ? (
            <p className="text-center text-[#6E6259] py-8 italic">
              No historical state transitions recorded for this booking yet.
            </p>
          ) : (
            <div className="relative pl-6 space-y-6 before:absolute before:left-2.5 before:top-2 before:bottom-2 before:w-0.5 before:bg-[#E6DED5]">
              {history.map((h, i) => (
                <div key={h.id || i} className="relative group">
                  <div className="absolute -left-6 top-1 w-5 h-5 rounded-full bg-white border-2 border-[#5A3E2B] flex items-center justify-center text-[#5A3E2B]">
                    <GitCommit size={12} />
                  </div>
                  <div className="bg-[#F7F5F0] p-3.5 rounded-xl border border-[#E6DED5] space-y-1">
                    <div className="flex items-center justify-between gap-2">
                      <div className="flex items-center gap-2">
                        {h.previous_state && (
                          <>
                            <span className="font-mono text-[10px] uppercase font-bold text-[#6E6259] bg-[#EFECE6] px-1.5 py-0.5 rounded">
                              {h.previous_state}
                            </span>
                            <span className="text-[#8A796B]">→</span>
                          </>
                        )}
                        <span className="font-mono text-[11px] uppercase font-bold text-[#24613B] bg-[#EBF7EE] border border-[#BDE5C8] px-2 py-0.5 rounded">
                          {h.new_state}
                        </span>
                      </div>
                      <span className="text-[10px] text-[#8A796B] font-mono">
                        {new Date(h.created_at).toLocaleString("en-IN")}
                      </span>
                    </div>

                    <div className="text-[11px] text-[#29231F] font-semibold pt-1">
                      Action: <span className="font-mono text-[#5A3E2B]">{h.trigger_action}</span>
                      {h.changed_by_name && (
                        <span className="text-[#6E6259] font-normal"> · by {h.changed_by_name}</span>
                      )}
                    </div>

                    {h.notes && (
                      <p className="text-[11px] text-[#6E6259] pt-0.5 leading-relaxed bg-white/70 p-2 rounded border border-[#E6DED5]/60 mt-1">
                        {h.notes}
                      </p>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-[#E6DED5] bg-[#FDFCFB] flex items-center justify-end">
          <button
            onClick={onClose}
            className="px-4 py-2 bg-[#F7F5F0] hover:bg-[#EFECE6] border border-[#E6DED5] rounded-lg text-xs font-bold text-[#29231F] transition cursor-pointer"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
