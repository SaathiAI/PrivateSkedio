import { tokens } from "../theme.js";

export const GlobalStyles = () => (
  <style>{`
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Playfair+Display:ital,wght@0,400;0,500;0,600;1,400;1,500&display=swap');

    *, *::before, *::after {
      box-sizing: border-box;
      margin: 0;
      padding: 0;
    }

    html {
      -webkit-font-smoothing: antialiased;
      -moz-osx-font-smoothing: grayscale;
      text-rendering: optimizeLegibility;
    }

    body {
      background: ${tokens.bg};
      color: ${tokens.text};
      font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
      font-size: 14px;
      line-height: 1.5;
      letter-spacing: -0.01em;
    }

    /* Refined scrollbar */
    ::-webkit-scrollbar {
      width: 5px;
      height: 5px;
    }
    ::-webkit-scrollbar-track {
      background: transparent;
    }
    ::-webkit-scrollbar-thumb {
      background: ${tokens.borderHover};
      border-radius: 10px;
    }
    ::-webkit-scrollbar-thumb:hover {
      background: ${tokens.textDim};
    }

    /* Focus styles — accessible and refined */
    :focus-visible {
      outline: 2px solid ${tokens.accent};
      outline-offset: 2px;
      border-radius: 4px;
    }

    button:focus-visible,
    [role="button"]:focus-visible {
      outline: 2px solid ${tokens.accent};
      outline-offset: 2px;
    }

    /* Smooth transitions for interactive elements */
    button, a, input, select, textarea {
      transition: all ${tokens.transitionFast};
    }

    /* Input focus states */
    input:focus,
    select:focus,
    textarea:focus {
      outline: none;
      border-color: ${tokens.accent} !important;
      box-shadow: 0 0 0 3px ${tokens.accentMuted};
    }

    /* Animations — refined easing */
    @keyframes spin {
      to { transform: rotate(360deg); }
    }

    @keyframes fadeUp {
      from {
        opacity: 0;
        transform: translateY(8px);
      }
      to {
        opacity: 1;
        transform: translateY(0);
      }
    }

    @keyframes fadeIn {
      from { opacity: 0; }
      to { opacity: 1; }
    }

    @keyframes pulse {
      0%, 100% { opacity: 0.4; }
      50% { opacity: 1; }
    }

    @keyframes slideRight {
      from {
        transform: translateX(100%);
        opacity: 0;
      }
      to {
        transform: translateX(0);
        opacity: 1;
      }
    }

    @keyframes modalScaleUp {
      0% {
        transform: scale(0.96) translateY(8px);
        opacity: 0;
      }
      100% {
        transform: scale(1) translateY(0);
        opacity: 1;
      }
    }

    @keyframes popIn {
      0% {
        transform: scale(0.9);
        opacity: 0;
      }
      70% {
        transform: scale(1.02);
      }
      100% {
        transform: scale(1);
        opacity: 1;
      }
    }

    @keyframes sidebarIn {
      from {
        opacity: 0;
        transform: translateX(-8px);
      }
      to {
        opacity: 1;
        transform: translateX(0);
      }
    }

    @keyframes shimmer {
      0% { background-position: -200% 0; }
      100% { background-position: 200% 0; }
    }

    @keyframes breathe {
      0%, 100% { opacity: 0.4; transform: scale(1); }
      50% { opacity: 0.7; transform: scale(1.02); }
    }

    /* Sidebar icon button — refined */
    .sidebar-icon-btn {
      background: transparent;
      border: none;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      width: 40px;
      height: 40px;
      border-radius: ${tokens.radiusLg};
      color: ${tokens.textMuted};
      transition: all ${tokens.transitionNormal};
      position: relative;
    }

    .sidebar-icon-btn:hover {
      color: ${tokens.text};
      background: ${tokens.bgHover};
      transform: translateY(-1px);
    }

    .sidebar-icon-btn:active {
      transform: scale(0.95);
    }

    /* Utility classes */
    .truncate {
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .glass {
      background: ${tokens.glassBg};
      backdrop-filter: blur(12px);
      -webkit-backdrop-filter: blur(12px);
    }

    /* Reduced motion */
    @media (prefers-reduced-motion: reduce) {
      *, *::before, *::after {
        animation-duration: 0.01ms !important;
        animation-iteration-count: 1 !important;
        transition-duration: 0.01ms !important;
      }
    }
  `}</style>
);
