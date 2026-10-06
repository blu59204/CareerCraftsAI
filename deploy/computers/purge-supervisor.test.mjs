import assert from 'node:assert/strict';
import test from 'node:test';
import ts from '../../frontend/node_modules/typescript/lib/typescript.js';
import { addSupervisorPurge } from './purge-supervisor.mjs';

class NameHeldError extends Error {}
class DockerUnavailableError extends Error {}
const owner = { 'openbot.supervisor': 'true', 'openbot.namespace': 'test', 'openbot.bot-id': 'u-owner' };
const names = { botId: 'u-owner', container: 'container', profileVolume: 'profile', workspaceVolume: 'workspace' };
function build(resources) {
  const patched = addSupervisorPurge('  reset,\napp.get("/computers",', 'const docker = new Docker(\nfunction statusOf(');
  const source = patched.docker.slice(patched.docker.indexOf('/** Idempotent'));
  const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText;
  const exports = {};
  new Function('exports', 'docker', 'OWNER_LABEL', 'NAMESPACE_LABEL', 'BOT_LABEL',
    'NAMESPACE', 'NameHeldError', 'DockerUnavailableError', 'statusOf', compiled)(
    exports, { getContainer: n => resources[n], getVolume: n => resources[n] },
    'openbot.supervisor', 'openbot.namespace', 'openbot.bot-id', 'test',
    NameHeldError, DockerUnavailableError, e => e.statusCode);
  return exports.purge;
}
function resource(labels, removed, id, { missing = false, busy = false, container = false } = {}) {
  return {
    inspect: async () => {
      if (missing) throw { statusCode: 404 };
      return container ? { Config: { Labels: labels } } : { Labels: labels };
    },
    remove: async () => {
      if (busy) throw { statusCode: 409 };
      removed.push(id);
    },
  };
}

test('purge removes both owned volumes, including orphaned volumes', async () => {
  const removed = [];
  const purge = build({ container: resource(owner, removed, 'container', { missing: true }),
    profile: resource(owner, removed, 'profile'), workspace: resource(owner, removed, 'workspace') });
  await purge(names);
  assert.deepEqual(removed, ['profile', 'workspace']);
});

test('purge rejects matching names with another owner label', async () => {
  const removed = [];
  const purge = build({ container: resource(owner, removed, 'container', { missing: true }),
    profile: resource({ ...owner, 'openbot.bot-id': 'u-other' }, removed, 'profile') });
  await assert.rejects(purge(names), NameHeldError);
  assert.deepEqual(removed, []);
});

test('busy volumes fail and missing resources are idempotent', async () => {
  const removed = [];
  const purge = build({ container: resource(owner, removed, 'container', { container: true }),
    profile: resource(owner, removed, 'profile', { busy: true }) });
  await assert.rejects(purge(names), DockerUnavailableError);
  assert.deepEqual(removed, ['container']);
  const absent = Object.fromEntries(['container', 'profile', 'workspace'].map(id =>
    [id, resource(owner, removed, id, { missing: true })]));
  await build(absent)(names);
});

test('pinned contract drift refuses build', () => {
  assert.throws(() => addSupervisorPurge('unexpected', 'unexpected'));
});
