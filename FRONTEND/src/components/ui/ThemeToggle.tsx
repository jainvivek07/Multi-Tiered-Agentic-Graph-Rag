import { Sun, Moon } from 'lucide-react';
import { useThemeStore } from '../../store/themeStore';
import styles from './ThemeToggle.module.css';

export function ThemeToggle() {
  const { theme, toggle } = useThemeStore();
  return (
    <button
      onClick={toggle}
      className={styles.toggle}
      aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
      title={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
    >
      <span className={styles.track}>
        <span className={[styles.thumb, theme === 'light' ? styles.light : ''].join(' ')}>
          {theme === 'dark' ? <Moon size={12} /> : <Sun size={12} />}
        </span>
      </span>
    </button>
  );
}
