# 📖 SEC-OPS 2.0: Smart Retail Exit Monitoring — Operator & User Manual

Welcome to the **SEC-OPS 2.0 User Manual**. This guide is written in plain, simple language to help store supervisors, security officers, and warehouse operators use the Exit Monitoring & Inventory Intelligence System effectively.

---

## 📌 Table of Contents
1. [What is this System?](#1-what-is-this-system)
2. [How Does it Work? (The 5-Step Process)](#2-how-does-it-work-the-5-step-process)
3. [How to Start the Software](#3-how-to-start-the-software)
4. [Tour of the Control Console (Screens & Tabs)](#4-tour-of-the-control-console-screens--tabs)
   - [4.1 Dashboard](#41-dashboard)
   - [4.2 Exit Events View](#42-exit-events-view)
   - [4.3 Incident Alerts View](#43-incident-alerts-view)
   - [4.4 Products & Case Packs](#44-products--case-packs)
   - [4.5 Employees & Badges](#45-employees--badges)
   - [4.6 Invoices & Manifests](#46-invoices--manifests)
   - [4.7 Daily Reports & PDF Export](#47-daily-reports--pdf-export)
   - [4.8 Settings & Camera Fleet Management](#48-settings--camera-fleet-management)
5. [Common Day-to-Day Workflows](#5-common-day-to-day-workflows)
   - [Workflow A: Responding to a HIGH-Severity Alarm](#workflow-a-responding-to-a-high-severity-alarm)
   - [Workflow B: Adding a New Camera to an Exit Lane](#workflow-b-adding-a-new-camera-to-an-exit-lane)
   - [Workflow C: Adding a New Product with Pack Size](#workflow-c-adding-a-new-product-with-pack-size)
   - [Workflow D: Testing the Siren Sound](#workflow-d-testing-the-siren-sound)
6. [Understanding the Colors & Status Lights](#6-understanding-the-colors--status-lights)
7. [Frequently Asked Questions (FAQ) & Troubleshooting](#7-frequently-asked-questions-faq--troubleshooting)

---

## 1. What is this System?

The **Smart Retail Exit Monitoring System (SEC-OPS 2.0)** is an automated physical security and loss prevention platform. 

When employees or delivery porters push carts of merchandise through store exit doors, the system **instantly counts the items**, **verifies them against the invoice bill**, and **detects theft, extra items, or scanning mistakes** in less than 2 seconds.

### Why is it used?
- **Stops Exit Theft & Over-Carrying**: Catches cases where 8 boxes are taken when only 4 were paid for or declared.
- **Solves the "Box vs Single" Problem**: Automatically calculates that 1 sealed case of water contains 24 single bottles (`cases × pack_size = units`).
- **No Manual Counting Needed**: Uses AI cameras, RFID radio antennas, and floor scales working together.
- **Automated Physical Turnstile Lock**: Can automatically lock the exit barrier and sound an alarm if a major theft attempt is detected.

---

## 2. How Does it Work? (The 5-Step Process)

Every time someone walks through an exit lane:

```
  [1. SENSORS READ]           [2. AI FUSION]           [3. INVOICE MATCH]        [4. VERDICT RULE]        [5. ACTION]
 ┌─────────────────┐        ┌─────────────────┐        ┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
 │ • Camera frames │        │ Combines:       │        │ Compares:       │     │ Rules Engine:   │     │ • PASS (Teal)   │
 │ • RFID tags     │───────▶│ • Camera Count  │───────▶│ Fused Count     │────▶│ Checks Allowed  │────▶│ OR              │
 │ • Floor scale kg│        │ • RFID Tag Count│        │     VS          │     │ Tolerance &     │     │ • ALARM + LOCK  │
 │ • Face scanner  │        │ • Weight count  │        │ Declared Bill   │     │ Repeat History  │     │   (Red/Amber)   │
 └─────────────────┘        └─────────────────┘        └─────────────────┘     └─────────────────┘     └─────────────────┘
```

1. **Step 1: Sensors Read the Cart**:
   - **Camera (YOLOX Apache 2.0 + ByteTrack)**: Identifies boxes, full sealed cases, loose items, and tracks them across video frames without double-counting. *(Note: Permissive YOLOX is used to avoid AGPL commercial restrictions).*
   - **RFID Gate**: Reads wireless tags on products and the employee's ID badge.
   - **Floor Scale**: Measures total kilograms on the floor plate.
   - **Face Scanner (InsightFace / ArcFace)**: Matches the carrier's face against the authorized employee roster in 512-dimensional vector space.
2. **Step 2: AI Multi-Sensor Consensus (`weighted_vote_v2`)**:
   - Merges camera count + RFID tag count + weight estimate into one **final verified count**.
   - If metal shielding blocks the RFID reader, the camera and scale automatically override it so no items are missed.
3. **Step 3: Compares to Scanned Invoice (PaddleOCR / TrOCR)**:
   - The verified count is compared against the warehouse delivery bill or invoice.
4. **Step 4: Decides the Verdict (Rules Engine)**:
   - **PASS**: The count matches the bill (or is within allowable tolerance).
   - **MISMATCH**: More or fewer items than declared. Categorized into **LOW**, **MEDIUM**, or **HIGH** severity.
   - **Repeat Offender Rule**: If an employee has had 3 or more discrepancies in the last 30 days, their alert automatically escalates to **HIGH severity**.
5. **Step 5: Immediate Action**:
   - If **PASS**: Turnstile opens smoothly with a green/teal indicator.
   - If **HIGH Severity**: Siren sounds, red strobe flashes, turnstile electromagnetically locks, and supervisors receive an urgent notification.

---

## 3. How to Start the Software

To start both the Backend engine and the Frontend console on your computer:

### Step 1: Open the Terminal / Command Prompt
Open PowerShell or Command Prompt.

### Step 2: Start the Backend Server
```powershell
cd C:\Users\DELL\.gemini\antigravity\scratch\retail-exit-backend
uv run uvicorn src.main:app --port 8000 --host 127.0.0.1
```
*(You will see: `Uvicorn running on http://127.0.0.1:8000`)*

### Step 3: Start the Control Console (Frontend)
Open a second terminal window:
```powershell
cd C:\Users\DELL\.gemini\antigravity\scratch\retail-exit-console
npm run preview -- --port 4173 --host
```

### Step 4: Open in Your Web Browser
Open Google Chrome or Microsoft Edge and navigate to:
👉 **`http://localhost:4173/`**

---

## 4. Tour of the Control Console (Screens & Tabs)

On the left side of the screen, you will see the **Navigation Rail** with icons for all main screens:

```
[📊 Dashboard]   [🚪 Exit Events]   [🚨 Alerts]   [📦 Products]   [👤 Employees]   [🧾 Invoices]   [📑 Reports]   [⚙️ Settings]
```

---

### 4.1 Dashboard
The **Dashboard** is the main control room screen.

- **Top KPI Readout Strip**:
  - **Today's Outflow Units**: Total units that have exited the store today.
  - **Open Active Alerts**: Number of unresolved alerts grouped by High, Medium, and Low.
  - **Consensus Match Rate**: Percentage of clean exits that perfectly matched invoice manifests (Target: > 95%).
  - **Exit Lanes Online**: Number of active physical exit portals (e.g. `4/4`).
  - **Cameras Online**: Number of operational CCTV streams (e.g. `4/5`).
  - **Simulate Button**: Click **"Sim"** to test-inject simulated events (Clean Pass, Over-Carry, RFID Blindspot, etc.).
- **Exit Event Stream (Left Panel)**: Shows every cart crossing in real time. Clicking any row opens the full math breakdown and camera photos.
- **Active Alerts (Right Panel)**: Shows unresolved issues with **HIGH-severity alerts pinned at the very top**.

---

### 4.2 Exit Events View
Click **"Events"** in the left rail to view historical exits.

- **Search & Filter**: Filter by date range, specific exit lane (Lane 1–4), SKU product, or verdict (`PASS` vs `MISMATCH`).
- **Inspection Detail Panel** (Clicking any row):
  - **Camera Snapshot**: View the photo captured at the moment of exit with bounding boxes over boxes.
  - **Math Breakdown**: Shows the case-to-unit math:
    $$\text{3 Cases of Water (Pack 24)} = 72\text{ units} + 2\text{ Loose Single Bottles} = 74\text{ Total Units}$$
  - **Sensor Comparison Matrix**: Shows individual counts from Camera, RFID Antenna, and Scale side-by-side to highlight where a difference occurred.
  - **Person Identified**: Shows employee photo match and similarity confidence score.

---

### 4.3 Incident Alerts View
Click **"Alerts"** to view and resolve security incidents.

Alerts are color-coded by urgency:
- 🔴 **HIGH (Crimson)**: Major theft, large over-carry ($> 6$ units), repeat offenders, or offline camera.
- 🟠 **MEDIUM (Orange)**: Noticeable discrepancy (3–5 units) or under-declared invoice.
- 🟡 **LOW (Yellow)**: Minor difference (1–2 units) or loose single item.

#### Resolving an Alert:
1. Click **"Ack"** (Acknowledge) to let the team know you are investigating.
2. After inspecting the cart or speaking with the carrier, click **"Resolve"**.
3. **Type a brief explanation** in the box (e.g., *"Inspected cart at Lane 2. 12 extra laundry detergent units were returned to warehouse shelf."*).
4. Click **"Confirm & Resolve"**. The action is permanently saved to the immutable audit log.

---

### 4.4 Products & Case Packs
Click **"Products"** to manage product catalog data.

- **Pack Size (Units per Case)**: This is the critical number. If a case of soda has 24 cans, enter `24`. When the camera detects 3 boxes, the system knows that equals 72 cans.
- **Add Product**: Click **"+ Add Product"** to register new SKUs, pack sizes, unit prices, case prices, and average weights in grams.
- **Edit / Delete**: Update prices or pack sizes anytime.

---

### 4.5 Employees & Badges
Click **"Employees"** to manage warehouse staff and carriers.

- **30-Day Discrepancy Counter**: Displays how many exit discrepancies each employee has had in the last 30 days.
- **Repeat Offender Warning**: Staff with 3 or more discrepancies display a warning badge and automatically trigger HIGH severity on future mismatches.
- **Carrier Exit History**: Click on any employee to see a complete list of every exit traversal they have made.

---

### 4.6 Invoices & Manifests
Click **"Invoices"** to view scanned delivery bills and supplier manifests.

- **OCR Extraction**: Shows how the system read the paper or electronic waybill.
- **OCR Confidence Score**: Measures text-recognition quality (e.g., `98.5%`).
- **Linked Exit Event**: Click to jump directly to the physical cart traversal that used this invoice.

---

### 4.7 Daily Reports & PDF Export
Click **"Reports"** to view operations summaries.

- **Daily Loss-Prevention Digest**:
  - Total items exited
  - Value of inventory protected (\$ amount)
  - Discrepancy rate
  - Repeat offender incidents
- **Download Official PDF Report**: Click **"Download Daily Audit PDF"** to generate a clean, formatted report ready for store management or corporate security meetings.

---

### 4.8 Settings & Camera Fleet Management
Click **"Settings"** to calibrate the system and manage camera hardware.

1. **Appearance Mode**: Switch between **Dark Mode** (for dim control rooms) and **Light Mode** (for bright retail floor tablets).
2. **Severity Tolerance Thresholds**:
   - *Low Severity Threshold*: Delta units (default: 1)
   - *Medium Severity Threshold*: Delta units (default: 3)
   - *High Severity Threshold*: Delta units (default: 6)
3. **Repeat Offender Setting**: Number of mismatches before automatic high-severity escalation (default: 3).
4. **Alarm Sound & Volume**: Toggle synthetic alarm siren ON/OFF, adjust volume slider (0–100%), and test tone.
5. **Turnstile Auto-Lock**: Toggle whether the physical turnstile should automatically lock on HIGH-severity alarms.
6. **Camera Fleet Management**:
   - View all cameras, IP addresses, RTSP stream URLs, and live status dots.
   - Click **"Test Feed"** (🔄) to test any camera stream.
   - Click **"Rebind"** to move a camera from one lane to another.
   - Click **"Add Camera to Fleet"** to onboard a new camera (see workflow below).
   - Click **"Delete"** (🗑️) to decommission a camera safely (soft-delete).

---

## 5. Common Day-to-Day Workflows

### Workflow A: Responding to a HIGH-Severity Alarm
1. **Audio Tone Sounds & Red Border Flashes** on the console.
2. **Look at the Dashboard**: The top alert card will show the lane number (e.g. `LANE-02`), the employee name, and the extra units detected (e.g. `Δ +12 Units`).
3. **Check the Turnstile**: The turnstile gate at Lane 2 is automatically locked.
4. **Inspect the Physical Cart**: Check the items in the cart against the invoice displayed on your screen.
5. **Resolve in the Console**: Click **"Resolve"** on the alert card, enter what occurred (e.g. *"Extra box returned to shelf"*), and click Confirm.
6. **Unlock Gate**: If needed, click the turnstile toggle button to re-open the gate.

---

### Workflow B: Adding a New Camera to an Exit Lane
When a technician installs a new WiFi or IP camera at a doorway:

1. Go to **Settings** ➔ Scroll to **"Surveillance Camera Fleet"**.
2. Click **"+ Add Camera to Fleet"**.
3. **Step 1 (Details)**: Enter a label (e.g., *"Exit Lane 3 — High Angle"*), the camera IP address (`192.168.10.45`), and RTSP path (`/live/ch0`). Click Next.
4. **Step 2 (Connection Test)**: Click **"Execute Stream Pull Test"**.
   - The system connects to the camera and displays a live test image with latency in milliseconds.
   - If there is an error (e.g. wrong password or wrong IP), a clear troubleshooting message appears.
5. **Step 3 (Lane Linkage)**: Select which exit lane to assign the camera to (e.g., `LANE-03`), or create a new lane inline.
6. **Step 4 (Deploy)**: Review and click **"Deploy Camera to Fleet"**.
   - The camera immediately appears in the fleet table and begins monitoring.

---

### Workflow C: Adding a New Product with Pack Size
1. Go to **Products** ➔ Click **"+ Add Product"**.
2. Enter:
   - **SKU Code**: e.g., `SKU-JUICE-1L-12`
   - **Product Name**: e.g., `Orange Juice 1L`
   - **Category**: `Beverages`
   - **Pack Size (Units per Case)**: `12` *(Essential! 1 box = 12 bottles)*
   - **Unit Price**: `\$2.50` | **Case Price**: `\$28.00`
3. Click **"Save Product"**. The AI vision and pack-math engine will now recognize this product immediately.

---

### Workflow D: Testing the Siren Sound
1. Go to **Settings** ➔ **Alarm Sound Synthesizer**.
2. Make sure **"Web Audio API Synthetic Alarm Siren"** is checked.
3. Adjust the **Volume Slider**.
4. Click **"Test Siren Tone"**. A 0.8-second dual-frequency security tone will play through your speakers.

---

## 6. Understanding the Colors & Status Lights

| Color | Status Meaning | Used For |
|---|---|---|
| 🟢 **Cool Teal (`#4FD1B3`)** | **OK / PASS / ONLINE** | Verified exits, matching invoice, camera streaming normally |
| 🟡 **Warm Amber (`#E8A33D`)** | **ATTENTION / LOW** | Minor unit differences (1–2 items), degraded connection |
| 🟠 **Orange (`#F0924A`)** | **MEDIUM SEVERITY** | Unacknowledged discrepancies (3–5 items), under-declared bills |
| 🔴 **Crimson Red (`#E5484D`)** | **HIGH SEVERITY / ALARM** | Major mismatch ($>6$ items), repeat offender, offline camera |
| ⚪ **Phosphor Green (`#B8E3D6`)** | **LIVE SENSOR READOUT** | Unit counts, weights (kg), timestamps, SKU codes in mono font |

---

## 7. Frequently Asked Questions (FAQ) & Troubleshooting

### Q1: Why did an alert become HIGH severity even though the difference was only 2 units?
**Answer**: The carrier who pushed the cart is likely a **Repeat Offender** (3 or more previous discrepancies in the last 30 days). The system automatically bumps severity up by one band for repeat offenders.

### Q2: What happens if an RFID tag on a box is shielded by metal foil?
**Answer**: The **Consensus Fusion Engine** compares all 3 sensors (Camera, RFID, and Scale). If the Camera and Scale agree that 3 boxes are present, the system uses majority consensus and flags the RFID antenna as "Attenuated", ensuring no items are missed.

### Q3: How do I unlock a turnstile that locked automatically?
**Answer**: On the Dashboard or Lanes screen, click the **"Unlock / Lock"** toggle button next to the lane ID, or resolve the active High alert.

### Q4: What should I do if a camera shows "OFFLINE"?
**Answer**: 
1. Check that the camera power cable and network cable/WiFi are plugged in.
2. In **Settings ➔ Camera Fleet**, click the **Refresh/Test** button (🔄) to re-test the connection.
3. If the IP address changed, click **Rebind** or update the IP in the camera settings.

### Q5: Can I run this system without internet access?
**Answer**: **Yes**. The entire SEC-OPS 2.0 system runs completely locally on your in-store edge computer. All AI inference, database storage, audio sirens, and WebSocket feeds function 100% on the local store network.

---

*SEC-OPS 2.0 — Smart Retail Exit Monitoring & Inventory Intelligence Platform*  
*Document Version: 2.0.0 | Operational Release*

