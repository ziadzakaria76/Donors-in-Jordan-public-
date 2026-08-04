const STORAGE_KEY = 'doc2md:theme';

export type Theme = 'dark' | 'light';

export function currentTheme(): Theme {
  return document.documentElement.classList.contains('dark') ? 'dark' : 'light';
}

export function setTheme(theme: Theme): void {
  document.documentElement.classList.toggle('dark', theme === 'dark');
  document
    .querySelector('meta[name="theme-color"]')
    ?.setAttribute('content', theme === 'dark' ? '#0b1020' : '#f8fafc');
  try {
    localStorage.setItem(STORAGE_KEY, theme);
  } catch {
    // Private browsing: the choice just will not survive a reload.
  }
}

export function toggleTheme(): Theme {
  const next: Theme = currentTheme() === 'dark' ? 'light' : 'dark';
  setTheme(next);
  return next;
}
