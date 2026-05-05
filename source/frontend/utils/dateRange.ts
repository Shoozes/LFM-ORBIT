export function formatDateInput(date: Date): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

export function getDefaultMissionDateRange(now = new Date()): { startDate: string; endDate: string } {
  const end = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const start = new Date(end);
  start.setFullYear(start.getFullYear() - 1);
  return {
    startDate: formatDateInput(start),
    endDate: formatDateInput(end),
  };
}

export function getRecentMissionDateRange(days = 30, now = new Date()): { startDate: string; endDate: string } {
  const end = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const start = new Date(end);
  start.setDate(start.getDate() - Math.max(1, days));
  return {
    startDate: formatDateInput(start),
    endDate: formatDateInput(end),
  };
}
