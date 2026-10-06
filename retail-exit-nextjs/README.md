# SEC-OPS 2.0 â€” Retail Exit Monitoring & Inventory Intelligence Console

Modern, high-performance web dashboard for real-time retail exit monitoring, multi-sensor consensus fusion, and loss prevention auditing. Powered by **Next.js 16 (App Router)**, **TypeScript**, **Tailwind CSS**, and real-time WebSocket telemetry.

---

## Overview

The **SEC-OPS Frontend Console** connects operators, floor supervisors, and security executives with the edge-accelerated backend to provide:

- **Live Multi-Camera Surveillance & Edge Feeds:** Low-latency MJPEG and RTSP-transcoded streams with real-time bounding box annotations (merchandise, carrier identity, PPE compliance, flame/hazard).
- **Multi-Sensor Consensus Fusion Telemetry:** Real-time synchronization of Computer Vision (YOLO/ByteTrack), UHF RFID portals, and high-precision load-cell weight scales.
- **Instant Security Incident Cards & Alerts:** High-consequence discrepancy detection (over-carry, under-declare, unauthorized exits, tailgating) with automated turnstile locking and siren/strobe triggers.
- **Supervisor Signature & Turnstile Gate Override:** Cryptographically audited digital signature pad and badge verification for gate unlock authorizations.
- **Smart Video Wall:** Dynamic multi-tile layouts (1x1, 2x2, 3x3, 4x4, 1+5, 1+7) with drag-and-drop camera assignments and full-screen forensic views.
- **Daily Loss Prevention Audit Digest:** Automated multi-tab compliance reporting, shrinkage delta tracking, and Excel/PDF export pipelines.

---

## Technology Stack

- **Framework:** Next.js 16 (React 19 / App Router)
- **Styling:** Tailwind CSS with dark-mode security console palette
- **Icons:** Lucide React
- **Streaming:** Low-latency MJPEG stream player, WebSockets (`/ws/live`)
- **API Client:** Robust fetch wrapper (`safeFetch`) with error normalization and zero hardcoded URLs

---

## Environment Configuration

Configure environment variables in `.env.local` or `.env.production`:

```env
# Backend REST & WebSocket API Base URL (Leave empty if using Next.js reverse proxy)
NEXT_PUBLIC_API_BASE_URL="http://localhost:8000"
```

When deployed behind an enterprise reverse proxy (e.g., NGINX / Traefik / Kubernetes Ingress), `NEXT_PUBLIC_API_BASE_URL` can be left blank or set to `/api` to route directly via same-origin.

---

## Getting Started

### 1. Install Dependencies

```bash
npm install
```

### 2. Start Development Server

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) to view the console.

### 3. Production Build & Linting

```bash
npm run build
npm run start
```

---

## Project Structure

```
retail-exit-nextjs/
â”œâ”€â”€ src/
â”‚   â”œâ”€â”€ app/
â”‚   â”‚   â”œâ”€â”€ (dashboard)/
â”‚   â”‚   â”‚   â”œâ”€â”€ alerts/           # Alert management, triage & turnstile unlock
â”‚   â”‚   â”‚   â”œâ”€â”€ analytics/        # Shrinkage trends & sensor health KPIs
â”‚   â”‚   â”‚   â”œâ”€â”€ cameras/          # Live CCTV camera grid & single stream forensic
â”‚   â”‚   â”‚   â”œâ”€â”€ employees/        # Carrier identity roster & facial vectors
â”‚   â”‚   â”‚   â”œâ”€â”€ events/           # Exit event logs & forensic evidence artifacts
â”‚   â”‚   â”‚   â”œâ”€â”€ materials/        # SKU catalog & weight tolerance definitions
â”‚   â”‚   â”‚   â”œâ”€â”€ reports/          # Daily loss prevention audit digest & Excel export
â”‚   â”‚   â”‚   â”œâ”€â”€ settings/         # Camera registration, thresholds & USB fleet
â”‚   â”‚   â”‚   â”œâ”€â”€ wall/             # Smart Wall multi-monitor command center
â”‚   â”‚   â”‚   â””â”€â”€ layout.tsx        # Dashboard shell with nav & live status
â”‚   â”‚   â””â”€â”€ page.tsx              # Main overview command center
â”‚   â”œâ”€â”€ components/              # Modular UI components (modals, players, charts)
â”‚   â”œâ”€â”€ hooks/                   # React hooks (useWebSocket, useDebounce)
â”‚   â””â”€â”€ lib/                     # API client & utility functions
â””â”€â”€ package.json
```
