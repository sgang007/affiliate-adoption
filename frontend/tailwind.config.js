/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        // Tinted darks (never pure gray/black) per impeccable guidance.
        ink: '#0b1020',
        panel: '#111730',
        edge: '#232c4e',
        fog: '#8d97b8',
        snow: '#e9edf8',
        mint: '#2dd4bf',
        gold: '#f4b740',
        coral: '#fb7185',
        leaf: '#34d399',
      },
      fontFamily: {
        display: ['"Space Grotesk"', 'sans-serif'],
        body: ['Sora', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'monospace'],
      },
      boxShadow: {
        glow: '0 0 24px rgba(45, 212, 191, 0.18)',
        gold: '0 0 24px rgba(244, 183, 64, 0.22)',
      },
    },
  },
  plugins: [],
}
