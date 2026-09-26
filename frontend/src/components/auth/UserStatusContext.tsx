"use client";

import { createContext, useContext } from "react";

export interface UserStatus {
  onboarding_completed: boolean;
  policy_accepted_at: string | null;
  deletion_requested_at: string | null;
  deletion_scheduled_for: string | null;
  deletion_cooldown_until: string | null;
}

interface UserStatusContextValue {
  status: UserStatus | null;
  refresh: () => void;
}

const UserStatusContext = createContext<UserStatusContextValue>({
  status: null,
  refresh: () => {},
});

export const UserStatusProvider = UserStatusContext.Provider;

// Read-only status from the same `/users/me` fetch OnboardingGuard already
// makes on every load — components below it (e.g. the pending-deletion
// banner) read from here instead of issuing their own duplicate request.
export function useUserStatus() {
  return useContext(UserStatusContext);
}
