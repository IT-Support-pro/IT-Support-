/**
 * Time and date formatting utilities for HBK IT Monitoring Dashboard.
 * All dashboard times, alert times, and last seen are displayed in Asia/Karachi (PKT).
 * UTC is kept in tooltips.
 */

export function formatPktTime(dateInput: string | number | Date | null | undefined): string {
  if (!dateInput) return 'N/A';
  const d = typeof dateInput === 'string' || typeof dateInput === 'number' ? new Date(dateInput) : dateInput;
  if (isNaN(d.getTime())) return 'N/A';

  try {
    const formatted = d.toLocaleTimeString('en-GB', {
      timeZone: 'Asia/Karachi',
      hour12: false,
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    });
    return `${formatted} PKT`;
  } catch {
    return `${d.toLocaleTimeString()} PKT`;
  }
}

export function formatPktDateTime(dateInput: string | number | Date | null | undefined): string {
  if (!dateInput) return 'N/A';
  const d = typeof dateInput === 'string' || typeof dateInput === 'number' ? new Date(dateInput) : dateInput;
  if (isNaN(d.getTime())) return 'N/A';

  try {
    const datePart = d.toLocaleDateString('en-GB', {
      timeZone: 'Asia/Karachi',
      year: 'numeric',
      month: 'short',
      day: '2-digit'
    });
    const timePart = d.toLocaleTimeString('en-GB', {
      timeZone: 'Asia/Karachi',
      hour12: false,
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    });
    return `${datePart} ${timePart} PKT`;
  } catch {
    return `${d.toLocaleString()} PKT`;
  }
}

export function formatUtcTooltip(dateInput: string | number | Date | null | undefined): string {
  if (!dateInput) return '';
  const d = typeof dateInput === 'string' || typeof dateInput === 'number' ? new Date(dateInput) : dateInput;
  if (isNaN(d.getTime())) return '';
  return `UTC: ${d.toISOString()}`;
}

export function formatRelativeMinutesAgo(dateInput: string | number | Date | null | undefined): string {
  if (!dateInput) return 'Never';
  const d = typeof dateInput === 'string' || typeof dateInput === 'number' ? new Date(dateInput) : dateInput;
  if (isNaN(d.getTime())) return 'Never';

  const diffMs = Date.now() - d.getTime();
  if (diffMs < 0) return 'Just now';
  const diffSec = Math.floor(diffMs / 1000);
  const diffMin = Math.floor(diffSec / 60);

  if (diffSec < 45) return 'Just now';
  if (diffMin === 1) return '1 min ago';
  if (diffMin < 60) return `${diffMin} min ago`;
  const diffHrs = Math.floor(diffMin / 60);
  if (diffHrs === 1) return '1 hr ago';
  if (diffHrs < 24) return `${diffHrs} hrs ago`;
  const diffDays = Math.floor(diffHrs / 24);
  return `${diffDays} day${diffDays > 1 ? 's' : ''} ago`;
}

/**
 * Calculates next expected reading time (15 minutes after last reading or now)
 */
export function getNextExpectedReadingPkt(lastReadingInput?: string | Date | null): string {
  const base = lastReadingInput ? new Date(lastReadingInput).getTime() : Date.now();
  const next = new Date(base + 15 * 60 * 1000);
  return formatPktTime(next);
}

export const timeAgoPkt = formatRelativeMinutesAgo;

