import { defineConfig } from 'vitest/config';
export default defineConfig({test:{
  environment:'jsdom', setupFiles:['./src/test/setup.js'],
  coverage:{provider:'v8',include:['src/App.jsx','src/api.js','src/TranscriptSummary.jsx'],reporter:['text','json-summary','html'],
    thresholds:{lines:90,statements:90,functions:90,branches:80}}
}});
