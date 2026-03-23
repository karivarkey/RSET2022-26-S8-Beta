module.exports = {
  content: ['./src/**/*.{js,ts,jsx,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {}
  },
  plugins: [],
  theme: {
  extend: {
    keyframes: {
      blob: {
        '0%, 100%': { transform: 'translate(0px, 0px) scale(1)' },
        '33%': { transform: 'translate(30px, -50px) scale(1.1)' },
        '66%': { transform: 'translate(-20px, 20px) scale(0.9)' },
      },
    },
    animation: {
      blob: 'blob 7s infinite',
      'blob-slow': 'blob 10s infinite',
    },
  },
}

}

