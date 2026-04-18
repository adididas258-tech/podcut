/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        bg: '#0C0C0E',
        surface: '#141416',
        border: '#1E1E24',
        'border-light': '#2A2A32',
        'text-primary': '#F0F0F2',
        'text-secondary': '#8A8A96',
        'text-muted': '#52525E',
        accent: '#4B7BEC',
        'accent-dim': '#1E2D5A',
        positive: '#22C55E',
        negative: '#EF4444',
        neutral: '#8A8A96',
        mixed: '#F59E0B',
      },
      fontFamily: {
        sans: ['"Inter"', 'system-ui', 'sans-serif'],
        serif: ['"Playfair Display"', 'Georgia', 'serif'],
      },
      animation: {
        'fade-up': 'fadeUp 0.3s ease-out',
        'slide-up': 'slideUp 0.4s cubic-bezier(0.16,1,0.3,1)',
        'pulse-soft': 'pulseSoft 2s ease-in-out infinite',
        'shimmer': 'shimmer 1.5s infinite',
      },
      keyframes: {
        fadeUp: { from: { opacity: 0, transform: 'translateY(8px)' }, to: { opacity: 1, transform: 'translateY(0)' } },
        slideUp: { from: { transform: 'translateY(100%)' }, to: { transform: 'translateY(0)' } },
        pulseSoft: { '0%,100%': { opacity: 1 }, '50%': { opacity: 0.5 } },
        shimmer: { '0%': { backgroundPosition: '-200% 0' }, '100%': { backgroundPosition: '200% 0' } },
      }
    },
  },
  plugins: [],
}
