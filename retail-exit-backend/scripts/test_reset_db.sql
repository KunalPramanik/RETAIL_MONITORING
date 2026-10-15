-- ==============================================================================
-- SEC-OPS V8 — TEST-ONLY DATABASE RESET PROCEDURE
-- WARNING: FOR EXPLICIT LOCAL TEST ENVIRONMENTS ONLY — NEVER RUN IN PRODUCTION!
-- ==============================================================================

DROP TABLE IF EXISTS public.platform_billing_invoice CASCADE;
DROP TABLE IF EXISTS public.platform_store_subscription CASCADE;
DROP TABLE IF EXISTS public.platform_subscription_tier CASCADE;
DROP TABLE IF EXISTS public.platform_audit_log CASCADE;
DROP TABLE IF EXISTS public.platform_super_admin CASCADE;
DROP TABLE IF EXISTS public.platform_tenant CASCADE;
DROP TABLE IF EXISTS public.alembic_version CASCADE;
DROP TABLE IF EXISTS public.audit_log CASCADE;
DROP TABLE IF EXISTS public.evidence_artifact CASCADE;
DROP TABLE IF EXISTS public.smart_wall_layout CASCADE;
DROP TABLE IF EXISTS public.static_image_detection CASCADE;
DROP TABLE IF EXISTS public.vehicle_detection CASCADE;
DROP TABLE IF EXISTS public.access_control_event CASCADE;
DROP TABLE IF EXISTS public.tripwire_crossing_event CASCADE;
DROP TABLE IF EXISTS public.dispatch_session CASCADE;
DROP TABLE IF EXISTS public.material_defect_event CASCADE;
DROP TABLE IF EXISTS public.material_movement_ledger CASCADE;
DROP TABLE IF EXISTS public.material_inventory_balance CASCADE;
DROP TABLE IF EXISTS public.alarm_dispatch CASCADE;
DROP TABLE IF EXISTS public.alert CASCADE;
DROP TABLE IF EXISTS public.person_appearance_summary CASCADE;
DROP TABLE IF EXISTS public.face_match_attempt CASCADE;
DROP TABLE IF EXISTS public.weight_reading CASCADE;
DROP TABLE IF EXISTS public.rfid_read CASCADE;
DROP TABLE IF EXISTS public.vision_detection CASCADE;
DROP TABLE IF EXISTS public.exit_event_line_item CASCADE;
DROP TABLE IF EXISTS public.exit_event CASCADE;
DROP TABLE IF EXISTS public.invoice CASCADE;
DROP TABLE IF EXISTS public.employee CASCADE;
DROP TABLE IF EXISTS public.shift CASCADE;
DROP TABLE IF EXISTS public.package_definition CASCADE;
DROP TABLE IF EXISTS public.material CASCADE;
DROP TABLE IF EXISTS public.pending_product_identification CASCADE;
DROP TABLE IF EXISTS public.initial_stock_verification CASCADE;
DROP TABLE IF EXISTS public.product CASCADE;
DROP TABLE IF EXISTS public.virtual_tripwire_config CASCADE;
DROP TABLE IF EXISTS public.camera_heartbeat CASCADE;
DROP TABLE IF EXISTS public.camera_pairing_token CASCADE;
DROP TABLE IF EXISTS public.camera CASCADE;
DROP TABLE IF EXISTS public.lane CASCADE;
DROP TABLE IF EXISTS public.app_user CASCADE;
DROP TABLE IF EXISTS public.threshold_config CASCADE;
DROP TABLE IF EXISTS public.store CASCADE;
DROP VIEW IF EXISTS public.user CASCADE;

