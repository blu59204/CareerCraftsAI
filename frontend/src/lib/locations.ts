// Suggestions for location fields. Free text is always allowed; this list only
// powers the dropdown. India first (most members), then global hubs.
export const LOCATIONS: string[] = [
  "Remote",
  "Bengaluru, India",
  "Hyderabad, India",
  "Mumbai, India",
  "Pune, India",
  "Chennai, India",
  "Delhi, India",
  "Gurugram, India",
  "Noida, India",
  "Kolkata, India",
  "Ahmedabad, India",
  "Kochi, India",
  "Coimbatore, India",
  "Jaipur, India",
  "Chandigarh, India",
  "Indore, India",
  "Thiruvananthapuram, India",
  "Mysuru, India",
  "Bhubaneswar, India",
  "Nagpur, India",
  "Visakhapatnam, India",
  "Lucknow, India",
  "Mangaluru, India",
  "Vadodara, India",
  "Surat, India",
  "Singapore",
  "Dubai, UAE",
  "Abu Dhabi, UAE",
  "London, UK",
  "Manchester, UK",
  "Dublin, Ireland",
  "Berlin, Germany",
  "Munich, Germany",
  "Amsterdam, Netherlands",
  "Paris, France",
  "Stockholm, Sweden",
  "Zurich, Switzerland",
  "Toronto, Canada",
  "Vancouver, Canada",
  "New York, USA",
  "San Francisco, USA",
  "Seattle, USA",
  "Austin, USA",
  "Boston, USA",
  "Chicago, USA",
  "Los Angeles, USA",
  "Sydney, Australia",
  "Melbourne, Australia",
  "Tokyo, Japan",
  "Kuala Lumpur, Malaysia",
];

const ALIASES: Record<string, string> = { bangalore: "bengaluru", gurgaon: "gurugram", bombay: "mumbai", madras: "chennai", calcutta: "kolkata" };

/** Up to `limit` suggestions for what the member has typed, best matches first. */
export function suggestLocations(typed: string, exclude: string[] = [], limit = 8): string[] {
  const q = typed.trim().toLowerCase();
  const skip = new Set(exclude.map((e) => e.trim().toLowerCase()));
  const pool = LOCATIONS.filter((l) => !skip.has(l.toLowerCase()));
  if (!q) return pool.slice(0, limit);
  // "bangal" -> also search "bengaluru": old names suggest the current one while typing.
  const queries = [q, ...Object.entries(ALIASES).filter(([old]) => old.startsWith(q)).map(([, now]) => now)];
  const starts = pool.filter((l) => queries.some((x) => l.toLowerCase().startsWith(x)));
  const contains = pool.filter((l) => !starts.includes(l) && queries.some((x) => l.toLowerCase().includes(x)));
  return [...starts, ...contains].slice(0, limit);
}
