/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ['"Source Sans 3"', "Segoe UI", "sans-serif"],
        display: ['"IBM Plex Sans"', "Segoe UI", "sans-serif"],
      },
      colors: {
        brand: {
          50: "#eef6f4",
          100: "#d5ebe5",
          500: "#1f6f5b",
          600: "#185a4a",
          700: "#134639",
          900: "#0b2a22",
        },
        ink: {
          700: "#243038",
          900: "#12181c",
        },
      },
      backgroundImage: {
        "app-wash":
          "radial-gradient(1200px 600px at 10% -10%, rgba(31,111,91,0.18), transparent 55%), radial-gradient(900px 500px at 100% 0%, rgba(36,48,56,0.08), transparent 50%), linear-gradient(180deg, #f5f7f6 0%, #e8eeec 100%)",
      },
    },
  },
  plugins: [],
};
