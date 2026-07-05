// Merge into tailwind.config.js -> theme.extend
// Mirrors tokens.css. Pair with a darkMode strategy (class or [data-theme]).
// e.g. darkMode: ['selector', '[data-theme="dark"]']

module.exports = {
  theme: {
    extend: {
      colors: {
        cx: {
          canvas: 'var(--cx-canvas)',
          sidebar: 'var(--cx-sidebar)',
          surface: 'var(--cx-surface)',
          'surface-2': 'var(--cx-surface-2)',
          'surface-3': 'var(--cx-surface-3)',
          hairline: 'var(--cx-hairline)',
          'hairline-soft': 'var(--cx-hairline-soft)',
          ink: {
            900: 'var(--cx-ink-900)',
            700: 'var(--cx-ink-700)',
            600: 'var(--cx-ink-600)',
            500: 'var(--cx-ink-500)',
            400: 'var(--cx-ink-400)',
            300: 'var(--cx-ink-300)',
          },
          accent: {
            DEFAULT: 'var(--cx-accent)',
            hover: 'var(--cx-accent-hover)',
            soft: 'var(--cx-accent-soft)',
            border: 'var(--cx-accent-border)',
          },
          success: {
            DEFAULT: 'var(--cx-success)',
            text: 'var(--cx-success-text)',
            soft: 'var(--cx-success-soft)',
            border: 'var(--cx-success-border)',
          },
          prov: {
            a: 'var(--cx-prov-a)', 'a-soft': 'var(--cx-prov-a-soft)',
            b: 'var(--cx-prov-b)', 'b-soft': 'var(--cx-prov-b-soft)',
            c: 'var(--cx-prov-c)', 'c-soft': 'var(--cx-prov-c-soft)',
            d: 'var(--cx-prov-d)', 'd-soft': 'var(--cx-prov-d-soft)',
          },
        },
      },
      fontFamily: {
        display: ['"Space Grotesk"', 'system-ui', 'sans-serif'],
        ui: ['Manrope', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'ui-monospace', 'monospace'],
      },
      borderRadius: {
        'cx-sm': '6px', 'cx-md': '8px', 'cx-lg': '10px',
        'cx-xl': '12px', 'cx-2xl': '14px', 'cx-card': '16px', 'cx-phone': '34px',
      },
      boxShadow: {
        'cx-sm': 'var(--cx-shadow-sm)',
        'cx-card': 'var(--cx-shadow-card)',
        'cx-pop': 'var(--cx-shadow-pop)',
        'cx-accent': 'var(--cx-shadow-accent)',
      },
      letterSpacing: {
        'cx-display': '-0.025em',
        'cx-eyebrow': '0.16em',
      },
    },
  },
};
