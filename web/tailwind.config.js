/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './app/**/*.{js,ts,jsx,tsx}',
    './components/**/*.{js,ts,jsx,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        // Legacy aliases — preserved so existing components don't break
        'reaper-bg':      '#04050a',
        'reaper-surface': '#080b12',
        'reaper-border':  '#141c28',
        'reaper-accent':  '#4d9fd4',
        'reaper-danger':  '#ff2a2a',
        'reaper-warning': '#ff8800',
        'reaper-success': '#39ff14',
        'reaper-muted':   '#506070',

        // Ghost Protocol design tokens
        'ghost-bg':     '#04050a',
        'ghost-surface':'#080b12',
        'ghost-panel':  '#0c1018',
        'ghost-border': '#141c28',
        'ghost-text':   '#b8c8d8',
        'ghost-dim':    '#506070',
        'ghost-label':  '#3d6080',
        'ghost-green':  '#39ff14',
        'ghost-blue':   '#4d9fd4',
        'ghost-red':    '#ff2a2a',
        'ghost-amber':  '#ff8800',
      },
      fontFamily: {
        mono: ['"Share Tech Mono"', 'ui-monospace', 'Consolas', 'monospace'],
      },
      fontSize: {
        'xxs': ['0.65rem', { lineHeight: '1rem' }],
      },
      animation: {
        'fade-in':    'fadeIn 300ms ease-out',
        'slide-up':   'slideUp 300ms ease-out',
        'pulse-soft': 'pulseSoft 2s ease-in-out infinite',
        'blink':      'blink 1.1s step-end infinite',
        'scanline':   'scanline 10s linear infinite',
        'boot':       'boot 500ms ease-out',
      },
      keyframes: {
        fadeIn:    { '0%': { opacity: '0' },                               '100%': { opacity: '1' } },
        slideUp:   { '0%': { opacity: '0', transform: 'translateY(6px)' }, '100%': { opacity: '1', transform: 'translateY(0)' } },
        pulseSoft: { '0%, 100%': { opacity: '1' },                         '50%': { opacity: '0.35' } },
        blink:     { '0%, 100%': { opacity: '1' },                         '50%': { opacity: '0' } },
        scanline:  { '0%': { top: '-4px' },                                '100%': { top: '100vh' } },
        boot:      { '0%': { opacity: '0', letterSpacing: '0.4em' },       '100%': { opacity: '1', letterSpacing: '0.05em' } },
      },
    },
  },
  plugins: [],
};
