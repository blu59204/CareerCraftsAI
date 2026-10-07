import { readFile, writeFile } from 'node:fs/promises';
import { pathToFileURL } from 'node:url';

// Keep Docker ownership in the pinned supervisor. Never accept resource names
// or a shell command from the relay; only the validated owner's bot identifier.
export function addSupervisorPurge(index, docker) {
  if (!index.includes('  reset,') || !index.includes('app.get("/computers",'))
    throw new Error('Pinned supervisor route contract changed; review before building.');
  if (!docker.includes('const docker = new Docker(') || !docker.includes('function statusOf('))
    throw new Error('Pinned supervisor Docker contract changed; review before building.');
  index = index.replace('  reset,', '  reset,\n  purge,');
  index = index.replace('app.get("/computers",', `app.post("/computers/:botId/purge", async (context) => {
  const parsed = resolve(context.req.param("botId"));
  if (!parsed.ok) return context.json({ error: parsed.reason }, 400);
  try {
    await purge(parsed.names);
    return context.json({ purged: true });
  } catch (error) {
    if (error instanceof NameHeldError) return context.json({ error: error.message }, 409);
    if (error instanceof DockerUnavailableError) return context.json({ error: error.message }, 503);
    throw error;
  }
});

app.get("/computers",`);
  docker += `

/** Idempotent erasure, including volumes left by a previously removed computer.
 * A busy volume is a failure, never successful erasure. The next sweep retries.
 */
export async function purge(names: ComputerNames): Promise<void> {
  const owned = (labels: Record<string, string> | undefined) =>
    labels?.[OWNER_LABEL] === "true" &&
    labels?.[NAMESPACE_LABEL] === NAMESPACE && labels?.[BOT_LABEL] === names.botId;
  const container = docker.getContainer(names.container);
  try {
    const info = await container.inspect();
    if (!owned(info.Config?.Labels)) throw new NameHeldError(names.container);
    await container.remove({ force: true, v: false });
  } catch (error) {
    if (error instanceof NameHeldError) throw error;
    if (statusOf(error) !== 404) throw new DockerUnavailableError(String(error));
  }
  for (const name of [names.profileVolume, names.workspaceVolume]) {
    const volume = docker.getVolume(name);
    try {
      const info = await volume.inspect();
      if (!owned(info.Labels)) throw new NameHeldError(name);
      await volume.remove();
    } catch (error) {
      if (error instanceof NameHeldError) throw error;
      if (statusOf(error) !== 404) throw new DockerUnavailableError(String(error));
    }
  }
}
`;
  return { index, docker };
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const root = process.argv[2];
  if (!root) throw new Error('Pass the pinned supervisor source directory.');
  const patched = addSupervisorPurge(
    await readFile(root + '/index.ts', 'utf8'),
    await readFile(root + '/docker.ts', 'utf8'),
  );
  await writeFile(root + '/index.ts', patched.index);
  await writeFile(root + '/docker.ts', patched.docker);
}
