import './style.css';
import { mountApp } from './ui/app';

const root = document.getElementById('app');
if (!root) throw new Error('#app is missing from index.html');
mountApp(root);

// Registered lazily so it never competes with first paint. `autoUpdate` means
// a new deploy is picked up on the next launch without prompting.
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    void import('virtual:pwa-register').then(({ registerSW }) => {
      registerSW({ immediate: true });
    });
  });
}
