/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Background layers
        bg: {
          0: "#070B12",
          1: "#0B111B",
          2: "#101827",
        },
        // Panel surfaces
        surface: {
          1: "#111A28",
          2: "#162133",
          3: "#1B283B",
        },
        // Borders
        border: {
          DEFAULT: "#26364A",
          subtle: "#1B2839",
          strong: "#34475E",
        },
        // Primary identity
        "space-blue": {
          DEFAULT: "#155A8A",
          bright: "#1F78B4",
        },
        // Indian identity accent
        saffron: {
          DEFAULT: "#F28C28",
          bright: "#F6A23A",
        },
        // Text scale
        text: {
          primary: "#E8EDF3",
          secondary: "#AAB7C5",
          muted: "#738397",
        },
        // Semantic status
        status: {
          success: "#38A169",
          warning: "#D99A24",
          danger: "#D9534F",
          info: "#4B93C3",
        },
      },
      fontFamily: {
        sans: ['"IBM Plex Sans"', 'ui-sans-serif', 'system-ui', '-apple-system', 'sans-serif'],
        mono: ['"IBM Plex Mono"', 'ui-monospace', 'SFMono-Regular', 'Menlo', 'monospace'],
      },
      fontSize: {
        "2xs": ["10px", "14px"],
        xs: ["11px", "16px"],
        sm: ["12px", "18px"],
        base: ["13px", "20px"],
        md: ["14px", "22px"],
        lg: ["16px", "24px"],
        xl: ["18px", "26px"],
        "2xl": ["20px", "28px"],
        "3xl": ["24px", "32px"],
        "kpi-sm": ["20px", "28px"],
        "kpi-md": ["24px", "32px"],
        "kpi-lg": ["28px", "36px"],
      },
      borderRadius: {
        sm: "4px",
        DEFAULT: "5px",
        md: "6px",
        lg: "8px",
      },
      spacing: {
        "0.5": "4px",
        1: "8px",
        1.5: "12px",
        2: "16px",
        3: "24px",
        4: "32px",
        5: "40px",
      },
      boxShadow: {
        panel: "0 1px 3px rgba(0,0,0,0.4)",
        none: "none",
      },
      transitionDuration: {
        DEFAULT: "150ms",
        fast: "120ms",
        normal: "150ms",
        slow: "180ms",
      },
    },
  },
  plugins: [],
}
