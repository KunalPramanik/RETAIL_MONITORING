/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: ['class', '[data-theme="dark"]'],
  theme: {
    extend: {
      colors: {
        canvas: 'var(--bg-canvas)',
        panel: 'var(--bg-panel)',
        'panel-raised': 'var(--bg-panel-raised)',
        hairline: 'var(--border-hairline)',
        'text-pri': 'var(--text-primary)',
        'text-sec': 'var(--text-secondary)',
        amber: 'var(--signal-amber)',
        'status-ok': 'var(--status-ok)',
        'status-low': 'var(--status-low)',
        'status-med': 'var(--status-medium)',
        'status-high': 'var(--status-high)',
        'mono-val': 'var(--data-mono-text)',
      },
      fontFamily: {
        sans: ['"IBM Plex Sans"', 'system-ui', '-apple-system', 'sans-serif'],
        mono: ['"IBM Plex Mono"', 'monospace'],
      },
      fontSize: {
        'xs-tech': ['12px', '16px'],
        'sm-tech': ['13px', '18px'],
        'base-tech': ['15px', '22px'],
        'md-tech': ['18px', '24px'],
        'lg-tech': ['24px', '32px'],
        'xl-tech': ['32px', '40px'],
      },
      keyframes: {
        'alarm-pulse': {
          '0%, 100%': { borderColor: 'var(--status-high)', boxShadow: '0 0 0 0 rgba(229, 72, 77, 0)' },
          '50%': { borderColor: 'var(--signal-amber)', boxShadow: '0 0 12px 2px rgba(232, 163, 61, 0.4)' },
        },
        'digit-slide': {
          '0%': { transform: 'translateY(-100%)', opacity: '0' },
          '100%': { transform: 'translateY(0)', opacity: '1' },
        }
      },
      animation: {
        'alarm-pulse': 'alarm-pulse 1.5s infinite ease-in-out',
        'digit-roll': 'digit-slide 0.25s cubic-bezier(0.16, 1, 0.3, 1)',
      }
    },
  },
  plugins: [],
}

