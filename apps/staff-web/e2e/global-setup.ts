import { execFileSync } from 'node:child_process';

export default async function globalSetup() {
  const root = new URL('../../..', import.meta.url).pathname;
  execFileSync('docker', ['compose', 'build', 'api'], { cwd: root, stdio: 'inherit' });
  execFileSync('docker', ['compose', 'up', '-d', 'api'], { cwd: root, stdio: 'inherit' });
  for (let attempt = 0; attempt < 60; attempt += 1) {
    try {
      const response = await fetch('http://127.0.0.1:8000/health');
      if (response.ok) break;
    } catch { /* service is still starting */ }
    if (attempt === 59) throw new Error('API did not become healthy for browser certification');
    await new Promise((resolve) => setTimeout(resolve, 1000));
  }
  execFileSync('docker', ['compose', 'exec', '-T', 'api', 'python', 'tests/e2e_inventory_fixture.py', 'seed'], { cwd: root, stdio: 'inherit' });
}
