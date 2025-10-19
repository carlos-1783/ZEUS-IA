console.log('Node.js is working!');
console.log('Current directory:', process.cwd());
console.log('Node version:', process.version);
console.log('NPM version:', require('child_process').execSync('npm -v').toString().trim());
