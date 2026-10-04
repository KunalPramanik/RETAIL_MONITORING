"use client";

import { safeFetch } from "@/lib/api-client";
﻿import React, { useState, useEffect } from "react";
import { useParams } from "next/navigation";
import {
  Layers,
  ArrowLeft,
  CheckCircle,
  AlertTriangle,
  Clock,
  Box,
  Scale,
  Radio,
} from "lucide-react";
import Link from "next/link";

export default function EventDetailPage() {
  const params = useParams();
  const eventId = params.eventId as string;
  const [event, setEvent] = useState<any>(null);

  useEffect(() => {
    if (!eventId) return;
    const fetchEvent = async () => {
      try {
        const res = await safeFetch(`/api/events/${eventId}`);
        if (res.ok) setEvent(await res.json());
      } catch (e) {
        console.warn("Fetch event failed:", e);
      }
    };
    fetchEvent();
  }, [eventId]);

  return (
    <div className="space-y-6">
      <Link
        href="/events"
        className="text-xs font-mono text-[#38BDF8] hover:underline flex items-center gap-1.5"
      >
        <ArrowLeft size={14} /> Back to Traversal Stream
      </Link>

      <div className="bg-[var(--bg-panel)] p-6 rounded-xl border border-[var(--border-hairline)] flex justify-between items-center">
        <div>
          <span className="text-xs font-mono text-[var(--text-secondary)]">EVENT AUDIT RECORD //</span>
          <h1 className="text-2xl font-bold font-mono text-[var(--text-primary)] mt-1">{eventId}</h1>
          <span className="text-xs font-mono text-[var(--text-secondary)] mt-1 block">
            Exit Lane: <b className="text-[#38BDF8]">{event?.laneId || "LANE-01"}</b>
          </span>
        </div>

        <div className="text-right">
          <span
            className={`px-3 py-1 rounded text-xs font-mono font-bold ${
              event?.verdict === "PASS"
                ? "bg-[#4FD1B3]/20 text-[#4FD1B3] border border-[#4FD1B3]/30"
                : "bg-[#E5484D]/20 text-[#E5484D] border border-[#E5484D]/30"
            }`}
          >
            {event?.verdict || "PASS"}
          </span>
        </div>
      </div>

      {/* Multi-Channel Comparison (Part E.2) */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 font-mono text-xs">
        <div className="bg-[var(--bg-panel)] p-4 rounded-xl border border-[var(--border-hairline)]">
          <span className="text-[var(--text-secondary)]">1. VISION COUNT (YOLOX):</span>
          <div className="text-lg font-bold text-[#E8A33D] mt-1">
            {event?.casesDetected || 0} Cases / {event?.unitsDetected || 0} Units
          </div>
        </div>
        <div className="bg-[var(--bg-panel)] p-4 rounded-xl border border-[var(--border-hairline)]">
          <span className="text-[var(--text-secondary)]">2. RFID TAG READS:</span>
          <div className="text-lg font-bold text-[#38BDF8] mt-1">{event?.rfidCount || 0} Tags</div>
        </div>
        <div className="bg-[var(--bg-panel)] p-4 rounded-xl border border-[var(--border-hairline)]">
          <span className="text-[var(--text-secondary)]">3. WEIGHT SENSOR (LOAD CELL):</span>
          <div className="text-lg font-bold text-[#A78BFA] mt-1">{event?.weightKg || "0.000"} kg</div>
        </div>
      </div>
    </div>
  );
}
