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

    @keyframes assistantPanelIn {
      from {
        transform: translateX(28px);
        opacity: 0;
      }
      to {
        transform: translateX(0);
        opacity: 1;
      }
    }

    @keyframes settingsSlideIn {
      from {
        transform: translateX(18px);
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

    @keyframes logoLeafDriftA {
      0%, 100% { transform: rotate(-2deg) translateY(0); }
      50% { transform: rotate(1deg) translateY(-1px); }
    }

    @keyframes logoLeafDriftB {
      0%, 100% { transform: rotate(1deg) translateY(0); }
      50% { transform: rotate(-2deg) translateY(-1.5px); }
    }

    @keyframes logoLeafDriftC {
      0%, 100% { transform: rotate(0deg) translateY(0); }
      50% { transform: rotate(2deg) translateY(-1px); }
    }

    @keyframes logoGlowPulse {
      0%, 100% {
        filter: drop-shadow(0 0 0 rgba(188, 194, 244, 0.00)) drop-shadow(0 0 0 rgba(158, 173, 120, 0.00));
      }
      50% {
        filter: drop-shadow(0 0 5px rgba(188, 194, 244, 0.55)) drop-shadow(0 0 10px rgba(158, 173, 120, 0.34));
      }
    }

    @keyframes logoGlowBloom {
      0% {
        opacity: 0.92;
        filter: drop-shadow(0 0 0 rgba(188, 194, 244, 0));
      }
      50% {
        opacity: 1;
        filter: drop-shadow(0 0 8px rgba(188, 194, 244, 0.72)) drop-shadow(0 0 14px rgba(158, 173, 120, 0.42));
      }
      100% {
        opacity: 1;
        filter: drop-shadow(0 0 5px rgba(188, 194, 244, 0.55)) drop-shadow(0 0 10px rgba(158, 173, 120, 0.34));
      }
    }

    @keyframes logoRootPulse {
      0%, 100% {
        transform: scale(1);
        filter: drop-shadow(0 0 0 rgba(140, 153, 236, 0));
      }
      50% {
        transform: scale(1.05);
        filter: drop-shadow(0 0 7px rgba(140, 153, 236, 0.45));
      }
    }

    .sk-app-sidebar {
      width: 76px;
      height: calc(100dvh - 28px);
      margin: 14px 0 14px 14px;
      border: 1px solid ${tokens.sidebarBorder};
      border-radius: 22px;
      background: ${tokens.sidebarBg};
      display: flex;
      flex-direction: column;
      padding: 14px 10px 16px;
      flex-shrink: 0;
      box-shadow: 0 18px 42px rgba(36, 34, 30, 0.08);
      position: sticky;
      top: 14px;
      z-index: 5;
      overflow: hidden;
      transition:
        width 220ms cubic-bezier(0.16, 1, 0.3, 1),
        box-shadow 220ms cubic-bezier(0.16, 1, 0.3, 1);
    }

    .sk-app-sidebar:hover,
    .sk-app-sidebar:focus-within {
      width: 210px;
      box-shadow: 0 22px 54px rgba(36, 34, 30, 0.11);
    }

    .sk-sidebar-brand,
    .sk-sidebar-profile,
    .sk-sidebar-settings {
      width: 100%;
      border: 1px solid transparent;
      background: transparent;
      color: ${tokens.text};
      font-family: inherit;
      cursor: pointer;
      display: flex;
      align-items: center;
      gap: 0;
      text-align: left;
      white-space: nowrap;
    }

    .sk-sidebar-brand {
      height: 52px;
      padding: 0;
      margin-bottom: 40px;
      border-radius: 14px;
      justify-content: center;
    }

    .sk-app-sidebar:hover .sk-sidebar-brand,
    .sk-app-sidebar:focus-within .sk-sidebar-brand {
      justify-content: flex-start;
      gap: 12px;
      padding: 0 8px;
    }

    .sk-sidebar-brand:hover {
      background: ${tokens.bgHover};
    }

    .sk-sidebar-logo {
      width: 38px;
      height: 38px;
      border-radius: 12px;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      flex: 0 0 auto;
    }

    .sk-sidebar-brand-copy,
    .sk-sidebar-label,
    .sk-sidebar-user-copy {
      opacity: 0;
      transform: translateX(-6px);
      width: 0;
      max-width: 0;
      flex: 0 0 0;
      transition:
        opacity 150ms ease,
        max-width 180ms cubic-bezier(0.16, 1, 0.3, 1),
        transform 180ms cubic-bezier(0.16, 1, 0.3, 1);
      pointer-events: none;
      overflow: hidden;
    }

    .sk-app-sidebar:hover .sk-sidebar-brand-copy,
    .sk-app-sidebar:focus-within .sk-sidebar-brand-copy,
    .sk-app-sidebar:hover .sk-sidebar-label,
    .sk-app-sidebar:focus-within .sk-sidebar-label,
    .sk-app-sidebar:hover .sk-sidebar-user-copy,
    .sk-app-sidebar:focus-within .sk-sidebar-user-copy {
      opacity: 1;
      transform: translateX(0);
      width: auto;
      max-width: 150px;
      flex: 1 1 auto;
      pointer-events: auto;
    }

    .sk-sidebar-brand-title,
    .sk-sidebar-user-name {
      display: block;
      font-size: 15px;
      line-height: 1.1;
      font-weight: 650;
      color: ${tokens.text};
      overflow: hidden;
      text-overflow: ellipsis;
    }

    .sk-sidebar-brand-subtitle,
    .sk-sidebar-user-meta {
      display: block;
      margin-top: 3px;
      font-size: 12px;
      line-height: 1.1;
      color: ${tokens.textMuted};
      overflow: hidden;
      text-overflow: ellipsis;
    }

    .sk-sidebar-nav {
      display: grid;
      gap: 8px;
      width: 100%;
      padding-bottom: 128px;
    }

    .sk-sidebar-settings-group {
      display: grid;
      gap: 4px;
      width: 100%;
    }

    .sk-sidebar-item {
      align-items: center !important;
      transition:
        color ${tokens.transitionNormal},
        background ${tokens.transitionNormal},
        border-color ${tokens.transitionNormal};
    }

    .sk-app-sidebar:hover .sk-sidebar-item,
    .sk-app-sidebar:focus-within .sk-sidebar-item {
      justify-content: flex-start !important;
      gap: 10px !important;
      padding: 0 11px !important;
    }

    .sk-sidebar-item:hover {
      background: ${tokens.bgHover} !important;
      border-color: transparent !important;
      color: ${tokens.text} !important;
    }

    .sk-sidebar-icon {
      width: 20px;
      height: 20px;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      flex: 0 0 auto;
    }

    .sk-sidebar-label {
      display: inline-flex;
      align-items: center;
      overflow: hidden;
      text-overflow: ellipsis;
      font-size: 14px;
      line-height: 1.15;
      text-align: left;
      min-height: 20px;
    }

    .sk-app-sidebar:hover .sk-sidebar-label,
    .sk-app-sidebar:focus-within .sk-sidebar-label {
      flex: 0 1 auto;
      max-width: 190px;
    }

    .sk-sidebar-expand-mark {
      display: none;
      margin-left: auto;
      color: ${tokens.textMuted};
      font-size: 16px;
      line-height: 1;
      font-weight: 500;
    }

    .sk-app-sidebar:hover .sk-sidebar-expand-mark,
    .sk-app-sidebar:focus-within .sk-sidebar-expand-mark {
      display: inline-flex;
    }

    .sk-sidebar-settings-children {
      display: none;
      margin-left: 22px;
      padding-left: 17px;
      border-left: 1px solid ${tokens.border};
      gap: 2px;
    }

    .sk-app-sidebar:hover .sk-sidebar-settings-group.is-open .sk-sidebar-settings-children,
    .sk-app-sidebar:focus-within .sk-sidebar-settings-group.is-open .sk-sidebar-settings-children {
      display: grid;
    }

    .sk-sidebar-settings-child {
      border: none;
      background: transparent;
      color: ${tokens.textSecondary};
      border-radius: 8px;
      min-height: 34px;
      padding: 8px 10px;
      text-align: left;
      font-family: inherit;
      font-size: 13px;
      font-weight: 600;
      cursor: pointer;
    }

    .sk-sidebar-settings-child:hover {
      background: ${tokens.bgHover};
      color: ${tokens.text};
    }

    .sk-sidebar-settings-child[aria-current="page"] {
      background: ${tokens.accentMuted};
      color: ${tokens.accentHover};
      font-weight: 750;
    }

    .sk-sidebar-item[aria-current="page"]::before {
      content: "";
      position: absolute;
      left: 4px;
      width: 3px;
      height: 18px;
      border-radius: 999px;
      background: ${tokens.accent};
    }

    .sk-sidebar-bottom {
      position: absolute;
      left: 10px;
      right: 10px;
      bottom: 16px;
      margin-top: 0;
      padding-top: 18px;
      border-top: 1px solid ${tokens.borderSubtle};
      display: grid;
      gap: 10px;
      justify-items: center;
    }

    .sk-sidebar-profile,
    .sk-sidebar-settings {
      height: 42px;
      width: 42px;
      padding: 0;
      border-radius: 12px;
      justify-content: center;
      flex: 0 0 auto;
      transition:
        background ${tokens.transitionNormal},
        border-color ${tokens.transitionNormal},
        color ${tokens.transitionNormal};
    }

    .sk-app-sidebar:hover .sk-sidebar-profile,
    .sk-app-sidebar:focus-within .sk-sidebar-profile,
    .sk-app-sidebar:hover .sk-sidebar-settings,
    .sk-app-sidebar:focus-within .sk-sidebar-settings {
      width: 100%;
      padding: 0 10px;
      gap: 10px;
      justify-content: flex-start;
    }

    .sk-sidebar-profile:hover,
    .sk-sidebar-settings:hover {
      background: ${tokens.bgHover} !important;
      color: ${tokens.text};
    }

    .sk-sidebar-settings[aria-current="page"] {
      background: ${tokens.accentMuted};
      border-color: ${tokens.accentBorder};
      color: ${tokens.text};
    }

    .sk-sidebar-settings .sk-sidebar-icon {
      width: 20px;
      height: 20px;
      display: inline-flex;
      align-items: center;
      justify-content: center;
    }

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
    }

    .sk-ai-launcher {
      transition:
        transform ${tokens.transitionNormal},
        box-shadow ${tokens.transitionNormal},
        border-color ${tokens.transitionNormal},
        background ${tokens.transitionNormal};
      animation: aiLauncherFloat 5.2s ease-in-out infinite;
    }

    .sk-ai-launcher:hover,
    .sk-ai-launcher:focus-within {
      animation: none;
      transform: translateX(-50%) translateY(-4px);
      box-shadow: 0 26px 58px rgba(140, 153, 236, 0.24) !important;
      border-color: ${tokens.border} !important;
    }

    .sk-ai-launcher input:focus,
    .sk-ai-launcher input:focus-visible {
      border-color: transparent !important;
      box-shadow: none !important;
      outline: none !important;
    }

    @keyframes aiLauncherFloat {
      0%, 100% {
        transform: translateX(-50%) translateY(0);
      }
      50% {
        transform: translateX(-50%) translateY(-6px);
      }
    }

    .sk-logo-mark {
      filter: drop-shadow(0 8px 14px rgba(140, 153, 236, 0.18));
      overflow: visible;
    }

    .sk-logo-mark .sk-logo-wood,
    .sk-logo-mark .sk-logo-root-core,
    .sk-logo-mark .sk-logo-leaf {
      transform-box: fill-box;
      transform-origin: center;
      transition:
        filter 220ms cubic-bezier(0.16, 1, 0.3, 1),
        opacity 220ms cubic-bezier(0.16, 1, 0.3, 1),
        transform 220ms cubic-bezier(0.16, 1, 0.3, 1);
    }

    .sk-logo-mark .sk-logo-wood {
      transform-origin: center 70%;
    }

    .sk-logo-mark .sk-logo-root-core {
      transform-origin: center 75%;
    }

    .sk-logo-mark .sk-logo-leaf {
      opacity: 0.98;
    }

    .sk-logo-mark .sk-logo-leaf-top {
      animation: logoLeafDriftA 5.4s ease-in-out infinite;
    }

    .sk-logo-mark .sk-logo-leaf-left,
    .sk-logo-mark .sk-logo-leaf-outer-right {
      animation: logoLeafDriftB 6.1s ease-in-out infinite;
    }

    .sk-logo-mark .sk-logo-leaf-right,
    .sk-logo-mark .sk-logo-leaf-outer-left,
    .sk-logo-mark .sk-logo-leaf-inner-left,
    .sk-logo-mark .sk-logo-leaf-inner-right {
      animation: logoLeafDriftC 5.8s ease-in-out infinite;
    }

    .sk-sidebar-brand:hover .sk-logo-mark .sk-logo-wood,
    .sk-ai-launcher:hover .sk-logo-mark .sk-logo-wood,
    .sk-ai-launcher:focus-within .sk-logo-mark .sk-logo-wood {
      transform: translateY(-0.5px);
    }

    .sk-sidebar-brand:hover .sk-logo-mark .sk-logo-leaf,
    .sk-ai-launcher:hover .sk-logo-mark .sk-logo-leaf,
    .sk-ai-launcher:focus-within .sk-logo-mark .sk-logo-leaf {
      filter: drop-shadow(0 0 3px rgba(188, 194, 244, 0.28));
    }

    .sk-logo-mark.is-awake .sk-logo-leaf {
      opacity: 1;
      animation-name: logoGlowBloom, logoLeafDriftA;
      animation-duration: 520ms, 5.4s;
      animation-delay: 0ms, 520ms;
      animation-fill-mode: forwards, both;
      animation-timing-function: cubic-bezier(0.16, 1, 0.3, 1), ease-in-out;
      animation-iteration-count: 1, infinite;
    }

    .sk-logo-mark.is-awake .sk-logo-leaf-left,
    .sk-logo-mark.is-awake .sk-logo-leaf-outer-right {
      animation-name: logoGlowBloom, logoLeafDriftB;
      animation-delay: 70ms, 590ms;
    }

    .sk-logo-mark.is-awake .sk-logo-leaf-right,
    .sk-logo-mark.is-awake .sk-logo-leaf-outer-left {
      animation-name: logoGlowBloom, logoLeafDriftC;
      animation-delay: 140ms, 660ms;
    }

    .sk-logo-mark.is-awake .sk-logo-leaf-inner-left,
    .sk-logo-mark.is-awake .sk-logo-leaf-inner-right {
      animation-name: logoGlowBloom, logoLeafDriftA;
      animation-delay: 210ms, 730ms;
    }

    .sk-logo-mark.is-awake .sk-logo-root-core {
      animation: logoRootPulse 2.8s ease-in-out infinite;
    }

    .sk-logo-mark.is-awake .sk-logo-wood {
      filter: drop-shadow(0 6px 10px rgba(21, 24, 39, 0.08));
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
