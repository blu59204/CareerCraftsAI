"use client";

import { useAuth } from "@clerk/nextjs";
import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/lib/api";
import { githubProfileSchema } from "@/lib/profile-contracts";

export function GithubProjects() {
  const { userId } = useAuth();
  const { data } = useQuery({
    queryKey: ["github-resume-projects", userId], enabled: !!userId, retry: false,
    queryFn: async () => {
      try {
        const response = await apiClient.get("/integrations/github/profile");
        return githubProfileSchema.parse(response.data);
      } catch (error) {
        if ((error as { response?: { status: number } }).response?.status === 404) return null;
        throw error;
      }
    },
  });
  if (!data?.suggested_projects.length) return null;
  return (
    <aside aria-label="Optional GitHub projects" className="rounded-2xl bg-muted/40 p-4">
      <h3 className="font-medium">Projects you could add</h3>
      <p className="mt-1 text-sm text-muted-foreground">Review the repository evidence and add a project only if it reflects your work.</p>
      <ul className="mt-3 space-y-3 text-sm">
        {data.suggested_projects.map((project, index) => (
          <li key={index}>
            <strong>{typeof project === "string" ? project : project.name ?? project.title ?? "GitHub project"}</strong>
            <p>{typeof project === "string" ? "Could provide concrete evidence of your technical work." : project.reason ?? project.description ?? "Could provide concrete evidence of your technical work."}</p>
          </li>
        ))}
      </ul>
    </aside>
  );
}
