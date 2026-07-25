/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        'brand-white': '#F8FAFC',
        'brand-light-gray': '#E2E8F0',
        'brand-gray': '#94A3B8',
        'brand-dark-gray': '#334155',
        'brand-dark': '#0F172A',
        'brand-purple': '#8B5CF6',
        'brand-indigo': '#6366F1',
        'brand-blue': '#3B82F6',
        'status-green': '#10B981',
        'status-yellow': '#F59E0B',
        'status-red': '#EF4444',
      },
      spacing: {
        '128': '32rem',
        '144': '36rem',
      },
      borderRadius: {
        '4xl': '2rem',
        '5xl': '2.5rem',
      },
      boxShadow: {
        'glass': '0 4px 30px rgba(0, 0, 0, 0.1)',
        'soft': '0 10px 25px -5px rgba(0, 0, 0, 0.05), 0 8px 10px -6px rgba(0, 0, 0, 0.01)',
      }
    },
  },
  plugins: [],
}
