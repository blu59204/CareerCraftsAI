"use client";

import { redirect } from "next/navigation";

export default function RegisterPage() {
  redirect("/login?mode=sign-up");
}
