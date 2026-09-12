import { execFileSync } from 'node:child_process';

export default function globalTeardown() {
  const root = new URL('../../..', import.meta.url).pathname;
  try {
    execFileSync('docker', ['compose', 'exec', '-T', 'api', 'python', 'tests/e2e_inventory_fixture.py', 'verify'], { cwd: root, stdio: 'inherit' });
  } finally {
    execFileSync('docker', ['compose', 'exec', '-T', 'api', 'python', 'tests/e2e_inventory_fixture.py', 'cleanup'], { cwd: root, stdio: 'inherit' });
  }
}
