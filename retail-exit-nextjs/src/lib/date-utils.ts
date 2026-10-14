/**
 * Location-Aware Date and Time Utility for SEC-OPS Retail Platform.
 * 
 * Formats timestamps according to the client/store location and preserves
 * full original dates and timestamps instead of truncating or displaying raw UTC.
 */

export function formatLocalDateTime(isoOrTime?: any): string {
  if (isoOrTime === null || isoOrTime === undefined) return "--";
  try {
    let dateStr = typeof isoOrTime === "string" ? isoOrTime.trim() : String(isoOrTime).trim();
    if (!dateStr || dateStr === "--" || dateStr === "null" || dateStr === "undefined") return "--";

    // Handle bare time format "HH:MM:SS" by prepending today's date in UTC
    if (/^\d{2}:\d{2}(:\d{2})?$/.test(dateStr)) {
      const today = new Date().toISOString().split("T")[0];
      dateStr = `${today}T${dateStr}Z`;
    } else {
      if (dateStr.includes(" ") && /^\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}/.test(dateStr)) {
        dateStr = dateStr.replace(" ", "T");
      }
      if (dateStr.includes("T") && !dateStr.endsWith("Z") && !/[+-]\d{2}:?\d{2}$/.test(dateStr)) {
        dateStr = `${dateStr}Z`;
      }
    }
    const d = new Date(dateStr);
    if (!isNaN(d.getTime())) {
      return new Intl.DateTimeFormat(undefined, {
        year: "numeric",
        month: "short",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
        hour12: true,
      }).format(d);
    }
  } catch (_) {}
  return String(isoOrTime || "--");
}

export function formatLocalDateOnly(isoOrTime?: any): string {
  if (isoOrTime === null || isoOrTime === undefined) return "--";
  try {
    let dateStr = typeof isoOrTime === "string" ? isoOrTime.trim() : String(isoOrTime).trim();
    if (!dateStr || dateStr === "--" || dateStr === "null" || dateStr === "undefined") return "--";

    if (dateStr.includes(" ") && /^\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}/.test(dateStr)) {
      dateStr = dateStr.replace(" ", "T");
    }
    if (dateStr.includes("T") && !dateStr.endsWith("Z") && !/[+-]\d{2}:?\d{2}$/.test(dateStr)) {
      dateStr = `${dateStr}Z`;
    }
    const d = new Date(dateStr);
    if (!isNaN(d.getTime())) {
      return new Intl.DateTimeFormat(undefined, {
        year: "numeric",
        month: "short",
        day: "2-digit",
      }).format(d);
    }
  } catch (_) {}
  return String(isoOrTime || "--");
}

export function formatLocalTimeOnly(isoOrTime?: any): string {
  if (isoOrTime === null || isoOrTime === undefined) return "--:--:--";
  try {
    let dateStr = typeof isoOrTime === "string" ? isoOrTime.trim() : String(isoOrTime).trim();
    if (!dateStr || dateStr === "--:--:--" || dateStr === "null" || dateStr === "undefined") return "--:--:--";

    if (/^\d{2}:\d{2}(:\d{2})?$/.test(dateStr)) {
      const today = new Date().toISOString().split("T")[0];
      dateStr = `${today}T${dateStr}Z`;
    } else {
      if (dateStr.includes(" ") && /^\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}/.test(dateStr)) {
        dateStr = dateStr.replace(" ", "T");
      }
      if (dateStr.includes("T") && !dateStr.endsWith("Z") && !/[+-]\d{2}:?\d{2}$/.test(dateStr)) {
        dateStr = `${dateStr}Z`;
      }
    }
    const d = new Date(dateStr);
    if (!isNaN(d.getTime())) {
      return new Intl.DateTimeFormat(undefined, {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
        hour12: true,
      }).format(d);
    }
  } catch (_) {}
  return String(isoOrTime || "--:--:--");
}

