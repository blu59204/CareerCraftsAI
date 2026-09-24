// Hands a job's description off to the Resume workspace across a full page
// navigation. Descriptions can be several KB — too long for a URL query
// param — so this uses sessionStorage instead: one page writes it right
// before navigating, the other reads-and-clears it on mount.
const KEY = "careercraft:pending_jd";

export interface PendingJd {
  jdText: string;
  role: string;
  company: string;
}

export function setPendingJd(jd: PendingJd) {
  sessionStorage.setItem(KEY, JSON.stringify(jd));
}

export function takePendingJd(): PendingJd | null {
  const raw = sessionStorage.getItem(KEY);
  if (!raw) return null;
  sessionStorage.removeItem(KEY);
  try {
    return JSON.parse(raw) as PendingJd;
  } catch {
    return null;
  }
}
