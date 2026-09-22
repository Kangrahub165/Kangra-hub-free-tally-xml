const fs = require('fs');
const path = require('path');

const basePath = 'd:/KANGRA HUB FREE TALLY XML/frontend/src/app';
const files = [
  'login/page.tsx',
  'signup/page.tsx',
  'forgot-password/page.tsx',
  'faq/page.tsx',
  'how-it-works/page.tsx',
  'supported-banks/page.tsx',
  'contact/page.tsx',
  'privacy/page.tsx',
  'terms/page.tsx',
  'unlock-pdf/page.tsx',
  'recover/page.tsx',
  'suspended/page.tsx'
];

for (const file of files) {
  const fullPath = path.join(basePath, file);
  if (!fs.existsSync(fullPath)) {
    console.log(`Skipping ${file}`);
    continue;
  }
  
  let content = fs.readFileSync(fullPath, 'utf-8');
  
  // 1. Color replacements: slate- -> navy-
  content = content.replace(/\bslate-/g, 'navy-');
  
  // 2. Gradients and backgrounds
  content = content.replace(/bg-gradient-to-br from-navy-900 via-navy-950 to-brand-950/g, 'gradient-hero');
  content = content.replace(/bg-navy-50/g, 'bg-navy-50 gradient-surface');
  
  // 3. Shadows & Glass
  content = content.replace(/shadow-elevated/g, 'shadow-modal');
  content = content.replace(/bg-white p-/g, 'bg-white glass-card p-');
  content = content.replace(/bg-white rounded/g, 'bg-white glass-card rounded');
  content = content.replace(/bg-white pl-/g, 'bg-white glass-card pl-');
  content = content.replace(/shadow-xs/g, 'shadow-glow-brand');
  
  // 4. Form inputs focus
  content = content.replace(/focus:border-brand-600/g, 'focus:border-accent-500 focus:ring-accent-500/20');
  
  // 5. Opacity borders
  content = content.replace(/border-navy-200/g, 'border-navy-200/60');
  content = content.replace(/border-navy-300/g, 'border-navy-300/60');

  // 6. Animations (basic ones)
  content = content.replace(/max-w-md w-full/g, 'max-w-md w-full animate-slideUp');
  content = content.replace(/max-w-4xl/g, 'max-w-4xl animate-fadeIn');
  content = content.replace(/max-w-7xl/g, 'max-w-7xl animate-fadeIn');
  
  // Apply changes back
  fs.writeFileSync(fullPath, content, 'utf-8');
  console.log(`Processed ${file}`);
}
console.log('Update complete.');
