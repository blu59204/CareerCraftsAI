import { currentUser } from "@clerk/nextjs/server";

export default async function DashboardPage() {
  const user = await currentUser();
  return (
    <main className="p-8">
      <h1 className="text-2xl font-bold">Welcome, {user?.firstName ?? "there"}</h1>
      <p className="text-slate-500 mt-2">Your job search dashboard. Agents ready.</p>
    </main>
  );
}
