/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{vue,ts,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'SF Pro Display', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'sans-serif'],
      },
      colors: {
        orbit: '#7dd3fc',
        nebula: '#a78bfa',
        plasma: '#22d3ee',
        flare: '#fbbf24',
        cosmic: {
          blue: '#38bdf8',
          purple: '#a78bfa',
          pink: '#ec4899',
        },
        astro: {
          gold: '#d4af37',
          bright: '#f5d76e',
          cream: '#f3e5b8',
          dusk: '#8a744a',
        },
      },
      boxShadow: {
        glow: '0 0 40px rgba(125, 211, 252, 0.28)',
        'glow-gold': '0 0 40px rgba(212, 175, 55, 0.32)',
        'glow-lg': '0 0 70px rgba(125, 211, 252, 0.35)',
        'glow-purple': '0 0 45px rgba(168, 85, 247, 0.35)',
        'deep-glass': '0 8px 32px rgba(0, 0, 0, 0.5)',
      },
      backdropBlur: {
        xs: '2px',
      },
      keyframes: {
        shimmer: {
          '0%': { backgroundPosition: '-200% 0' },
          '100%': { backgroundPosition: '200% 0' },
        },
      },
      animation: {
        shimmer: 'shimmer 2.5s linear infinite',
      },
    },
  },
  plugins: [],
};
