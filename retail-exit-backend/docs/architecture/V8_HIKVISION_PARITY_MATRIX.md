# V8 HIKVISION PARITY MATRIX

*Status: ACTIVE - Phase 1 (Audit)*

This matrix maps enterprise VMS (Video Management System) capabilities against current V7 architecture and targeted V8 architecture.

| Category | Capability | V7 Status | V8 Target | V8 Enhancement |
| :--- | :--- | :--- | :--- | :--- |
| **Video Management** | Device Onboarding | Manual/Basic | ONVIF / Auto-Discovery | Automated codec inspection & duplicate prevention. |
| | Live View & Playback | Yes (WebRTC) | Yes | Adaptive bitrate, synchronized multi-cam playback. |
| | Stream Health | Binary (Online/Offline) | Granular | FPS drop, packet loss, codec mismatch tracking. |
| **Intelligent Monitoring**| Object Events (Tripwire) | Yes | Yes | Cross-camera spatial trajectories. |
| | PPE / Behavior | Yes | Yes | Expanded to OSHA posture / load limits. |
| | Queue / Occupancy | Basic | Advanced | Multi-zone occupancy with anomaly detection. |
| **Alarm Center** | Centralized Alerts | Yes | Yes | Full assignment/escalation resolution workflow. |
| | Linked Evidence | Image Snapshots | Clips + Metadata | Immutable chain-of-custody for audit logs. |
| **Smart Wall** | Configurable Layouts | No | Yes | Dynamic 1/4/9/16 grid with GPU capacity limits. |
| | Priority Override | No | Yes | Automatic pop-up for HIGH severity alerts. |
| **Map / E-Map** | GIS / Floor Plans | No | Yes | Interactive alarm pins and live-view on click. |
| **Access Control** | Face/Badge Auth | Basic Face Re-ID | Full Identity Graph | First-person-in, Anti-passback logic integration. |
| **Vehicle / ANPR** | License Plate Recog. | No | Modular Pipeline | Plate forensic search and watchlist correlation. |
| **Evidence Mgmt** | Tamper Protection | No | Yes | Hashes, retention policies, signed expiring URLs. |
| **Forensic Search** | Semantic/Visual Search| Basic | Advanced | Search by appearance embedding, time, and class. |
| **System Maintenance**| Health Monitoring | Basic | Advanced | CPU/GPU load, network health, recording integrity. |

## Next Steps for V8 Implementation
1. **Gap Analysis:** Current V7 lacks Smart Wall, E-Map, ANPR, and true Access Control interlocking.
2. **Execution:** These will be built according to the `V8_IMPLEMENTATION_PLAN.md` specifically in Phases 8, 9, and 10, strictly without hallucinating mock data.
