/**
 * Shared Utility Functions for SEC-OPS Next.js Frontend
 * 
 * Provides safe formatting helpers that guard against undefined / null values
 * and eliminate runtime crashes caused by unchecked property access.
 */

/**
 * Safely formats raw uppercase / snake_case enum keys into human-readable strings.
 * Replaces underscores with spaces and handles null/undefined gracefully.
 * 
 * @param val - The raw enum string, e.g. "RESTOCK_IN_PROGRESS" or "INVENTORY_ANOMALY"
 * @param fallback - The fallback label if val is undefined, null, or empty
 * @returns Human-readable string, e.g. "RESTOCK IN PROGRESS"
 */
export function formatEnum(val?: string | null, fallback: string = "UNKNOWN"): string {
  if (!val || typeof val !== "string") {
    return fallback;
  }
  return val.replace(/_/g, " ");
}

/**
 * Ensures an input form field value is always controlled (never undefined or null).
 * 
 * @param val - The raw state value
 * @returns Non-null string for React input value binding
 */
export function controlledValue<T>(val: T | null | undefined): T | string {
  return val ?? "";
}

