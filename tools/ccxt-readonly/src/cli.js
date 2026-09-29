import { capabilityMatrix } from './index.js';

const command = process.argv[2];
if (command !== 'capabilities') {
  console.error('Usage: npm run smoke:local');
  process.exitCode = 2;
} else {
  console.log(JSON.stringify(capabilityMatrix(), null, 2));
}
