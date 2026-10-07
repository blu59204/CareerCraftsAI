// New-password rules for sign-up and password reset. Checked live in the form
// so a weak password is caught on the same page, before Clerk is ever called.
export const PASSWORD_MIN_LENGTH = 12;

export const PASSWORD_RULES = [
  { id: "length", label: `At least ${PASSWORD_MIN_LENGTH} characters`, test: (p: string) => p.length >= PASSWORD_MIN_LENGTH },
  { id: "lower", label: "1 lowercase letter", test: (p: string) => /[a-z]/.test(p) },
  { id: "upper", label: "1 uppercase letter", test: (p: string) => /[A-Z]/.test(p) },
  { id: "number", label: "1 number", test: (p: string) => /[0-9]/.test(p) },
  { id: "special", label: "1 special character (e.g. !@#$%^&*)", test: (p: string) => /[^A-Za-z0-9\s]/.test(p) },
] as const;

export type PasswordCheck = { id: string; label: string; ok: boolean };

export function checkPassword(password: string): { checks: PasswordCheck[]; passed: number; strong: boolean } {
  const checks = PASSWORD_RULES.map((rule) => ({ id: rule.id, label: rule.label, ok: rule.test(password) }));
  const passed = checks.filter((check) => check.ok).length;
  return { checks, passed, strong: passed === checks.length };
}
