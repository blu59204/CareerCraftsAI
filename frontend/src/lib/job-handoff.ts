// Hands a job's description off to the Resume workspace across a full page
// navigation. Descriptions can be several KB — too long for a URL query
// param — so this uses sessionStorage instead: one page writes it right
// before navigating, the other reads-and-clears it on mount.
const KEY = "careercraft:pending_jd";
// The Resume page mounts twice on arrival (~200ms apart); the second mount
// must get the same handoff, not an empty box after the first one cleared it.
const REMOUNT_WINDOW_MS = 5_000;

export interface PendingJd {
  jdText: string;
  role: string;
  company: string;
}

let taken: { jd: PendingJd; at: number } | null = null;

export function setPendingJd(jd: PendingJd) {
  taken = null;
  sessionStorage.setItem(KEY, JSON.stringify(jd));
}

export function takePendingJd(): PendingJd | null {
  if (taken && Date.now() - taken.at < REMOUNT_WINDOW_MS) return taken.jd;
  const raw = sessionStorage.getItem(KEY);
  if (!raw) return null;
  sessionStorage.removeItem(KEY);
  try {
    const jd = JSON.parse(raw) as PendingJd;
    taken = { jd, at: Date.now() };
    return jd;
  } catch {
    return null;
  }
}
