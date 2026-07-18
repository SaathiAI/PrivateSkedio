/* eslint-disable react-refresh/only-export-components */
/**
 * Auth.jsx - Supabase Authentication Components for SkedioAI
 * 
 * Usage:
 *   - Add AuthProvider wrapper to App.jsx
 *   - Use useAuth() hook to get current user
 */

import { createContext, useContext, useState, useEffect, useRef } from 'react';
import { createClient } from '@supabase/supabase-js';
import { clearClientUserState } from "../lib/clientState.js";
import { startTimer } from "../lib/perf.js";
import { tokens } from '../theme.js';

// Initialize Supabase client
const supabaseUrl = import.meta.env.VITE_SUPABASE_URL;
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY;
const DEV_ADMIN_AUTH_KEY = 'skedio_dev_admin_auth';
const DEV_ADMIN_USER_ID = 'dev-admin';
const allowDevAdminAuth = import.meta.env.DEV || import.meta.env.VITE_ENABLE_DEV_ADMIN === '1';

// Create client - will show error if env vars not set
let supabase = null;
if (supabaseUrl && supabaseAnonKey) {
  supabase = createClient(supabaseUrl, supabaseAnonKey);
} else {
  console.warn('Supabase credentials not set. Add VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY to .env');
}

const parseAuthCooldownSeconds = (message = '') => {
  const match = message.match(/after\s+(\d+)\s+seconds?/i);
  return match ? Number(match[1]) : 0;
};

const isAuthRateLimitError = (message = '') => {
  const normalized = message.toLowerCase();
  return normalized.includes('rate limit') || normalized.includes('too many requests');
};

const friendlyAuthError = (message = '') => {
  const normalized = message.toLowerCase();
  if (isAuthRateLimitError(message)) {
    return 'Too many signup emails were requested. Wait a minute, then try again, or use Google sign-in.';
  }
  if (normalized.includes('already registered') || normalized.includes('already exists')) {
    return 'That email already has an account. Switch to Sign In instead.';
  }
  if (normalized.includes('invalid email')) {
    return 'Enter a valid email address.';
  }
  if (normalized.includes('password')) {
    return 'Use a stronger password with at least 6 characters.';
  }
  return message || 'Please check the details and try again.';
};

const authNoticeStyles = {
  error: {
    background: "rgba(248, 113, 113, 0.10)",
    border: "rgba(248, 113, 113, 0.55)",
    color: "#fca5a5",
  },
  success: {
    background: "rgba(34, 197, 94, 0.10)",
    border: "rgba(34, 197, 94, 0.45)",
    color: "#86efac",
  },
  warning: {
    background: "rgba(245, 158, 11, 0.10)",
    border: "rgba(245, 158, 11, 0.45)",
    color: "#fbbf24",
  },
};

const authFieldStyle = {
  width: '100%',
  padding: '14px 15px',
  background: tokens.bgCard,
  border: `1px solid ${tokens.border}`,
  borderRadius: 12,
  fontSize: 14,
  color: tokens.text,
  outline: 'none',
  boxSizing: 'border-box',
  transition: `border-color ${tokens.transitionNormal}, box-shadow ${tokens.transitionNormal}, background ${tokens.transitionNormal}`,
};

const authLabelStyle = {
  display: 'block',
  marginBottom: 8,
  fontSize: 11,
  color: tokens.textMuted,
  letterSpacing: "0.08em",
  textTransform: "uppercase",
  fontWeight: 700,
};

const authPrimaryButtonStyle = {
  width: '100%',
  padding: '14px',
  background: `linear-gradient(135deg, ${tokens.accent} 0%, #a5aff3 100%)`,
  color: "#fffefa",
  border: 'none',
  borderRadius: 12,
  fontSize: 14,
  fontWeight: 700,
  cursor: 'pointer',
  transition: `transform ${tokens.transitionFast}, box-shadow ${tokens.transitionNormal}, opacity ${tokens.transitionNormal}`,
  boxShadow: '0 16px 34px rgba(140,153,236,0.24)',
};

const buildDevAdminSession = () => ({
  access_token: `dev:${DEV_ADMIN_USER_ID}`,
  user: {
    id: DEV_ADMIN_USER_ID,
    email: 'admin@skedio.local',
    user_metadata: {
      name: 'Skedio Admin',
      role: 'admin',
    },
    app_metadata: {
      role: 'admin',
    },
  },
});

const readDevAdminSession = () => {
  if (!allowDevAdminAuth) return null;
  try {
    return localStorage.getItem(DEV_ADMIN_AUTH_KEY) === '1' ? buildDevAdminSession() : null;
  } catch {
    return null;
  }
};

const setDevAdminSession = () => {
  if (!allowDevAdminAuth) return null;
  localStorage.setItem(DEV_ADMIN_AUTH_KEY, '1');
  return buildDevAdminSession();
};

const clearDevAdminSession = () => {
  try {
    localStorage.removeItem(DEV_ADMIN_AUTH_KEY);
  } catch {
    // localStorage may be unavailable in restricted browsers.
  }
};

// ─── Auth Context ───
const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const initialDevSession = supabase ? null : readDevAdminSession();
  const [session, setSession] = useState(initialDevSession);
  const [user, setUser] = useState(initialDevSession?.user ?? null);
  const [loading, setLoading] = useState(!initialDevSession && !!supabase);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (initialDevSession) {
      return;
    }

    if (!supabase) {
      console.warn('Supabase not initialized - checking .env file');
      return;
    }

    // Get initial session
    const stop = startTimer('auth:getSession');
    supabase.auth.getSession().then(({ data: { session }, error: err }) => {
      stop();
      if (err) {
        console.error('Supabase auth error:', err);
        setError(err.message);
      }
      if (session) {
        clearDevAdminSession();
      }
      const nextSession = session || readDevAdminSession();
      setSession(nextSession);
      setUser(nextSession?.user ?? null);
      setLoading(false);
    }).catch((err) => {
      stop();
      console.error('Supabase auth catch:', err);
      setError(err.message);
      setLoading(false);
    });

    // Listen for auth changes
    const { data: { subscription } } = supabase.auth.onAuthStateChange(
      (event, session) => {
        if (session) {
          clearDevAdminSession();
        }
        if (event === 'SIGNED_OUT') {
          clearDevAdminSession();
        }
        const nextSession = session || (event === 'SIGNED_OUT' ? null : readDevAdminSession());
        setSession(nextSession);
        setUser(nextSession?.user ?? null);
        setLoading(false);
      }
    );

    return () => subscription.unsubscribe();
  }, []);

  const value = {
    session,
    user,
    loading,
    error,
    supabase,
    isAuthenticated: !!session,
    isDevAdmin: session?.access_token?.startsWith('dev:') || false,
    signInAsDevAdmin: async () => {
      await supabase?.auth.signOut({ scope: 'local' }).catch(() => {});
      const nextSession = setDevAdminSession();
      if (!nextSession) return false;
      setSession(nextSession);
      setUser(nextSession.user);
      setLoading(false);
      setError(null);
      return true;
    },
    signOutDevAdmin: () => {
      clearDevAdminSession();
      setSession(null);
      setUser(null);
    },
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}

// ─── Auth Helper Functions ───
export function getSupabase() {
  return supabase;
}

export function getAccessToken() {
  return supabase?.auth.getSession().then(({ data }) => (
    data.session?.access_token || readDevAdminSession()?.access_token
  )) || Promise.resolve(readDevAdminSession()?.access_token);
}

// ─── API Helper with Auth ───
export async function authFetch(url, options = {}) {
  const realSession = supabase ? (await supabase.auth.getSession()).data.session : null;
  const devSession = realSession ? null : readDevAdminSession();

  if (!supabase && !devSession) {
    throw new Error('Supabase not configured');
  }

  const session = realSession || devSession;
  
  const headers = {
    'Content-Type': 'application/json',
    ...options.headers,
  };

  if (session?.access_token) {
    headers['Authorization'] = `Bearer ${session.access_token}`;
    if (session.access_token.startsWith('dev:')) {
      headers['X-Skedio-Dev-User'] = session.user?.id || DEV_ADMIN_USER_ID;
    }
  }

  const response = await fetch(url, {
    ...options,
    headers,
  });

  if (response.status === 401) {
    if (session?.access_token?.startsWith('dev:')) {
      return response;
    }
    const { data } = await supabase.auth.refreshSession();
    const retryToken = data?.session?.access_token;
    if (retryToken && retryToken !== session?.access_token) {
      return fetch(url, {
        ...options,
        headers: {
          ...headers,
          Authorization: `Bearer ${retryToken}`,
        },
      });
    }
  }

  return response;
}

// ─── Auth Components ───
export function SignIn({ onSuccess }) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!supabase) {
      setError('Supabase not configured');
      return;
    }

    setLoading(true);
    setError('');
    clearDevAdminSession();

    const stop = startTimer('auth:signIn');
    const { data, error } = await supabase.auth.signInWithPassword({
      email,
      password,
    });
    stop();

    if (error) {
      setError(error.message);
      setLoading(false);
    } else if (onSuccess) {
      onSuccess(data.user);
    }
  };

  return (
    <form onSubmit={handleSubmit} style={{ width: '100%' }}>
      
      {error && (
        <div style={{ 
          padding: '10px 14px', background: tokens.redBg, border: `1px solid ${tokens.red}`,
          borderRadius: 8, marginBottom: 16, color: tokens.red, fontSize: 14 
        }}>{error}</div>
      )}
      
      <div style={{ marginBottom: 16 }}>
        <label style={authLabelStyle}>Email</label>
        <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required
          autoComplete="email"
          placeholder="Enter your email"
          style={authFieldStyle}
        />
      </div>
      
      <div style={{ marginBottom: 14 }}>
        <label style={authLabelStyle}>Password</label>
        <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required
          autoComplete="current-password"
          placeholder="Enter your password"
          style={authFieldStyle}
        />
      </div>

      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, marginBottom: 22 }}>
        <label style={{ display: 'inline-flex', alignItems: 'center', gap: 8, fontSize: 12, color: tokens.textSecondary, cursor: 'pointer' }}>
          <input type="checkbox" style={{ accentColor: tokens.accent }} />
          Remember for 30 days
        </label>
        <button
          type="button"
          style={{
            border: 'none',
            background: 'transparent',
            padding: 0,
            color: tokens.accentHover,
            fontSize: 12,
            fontWeight: 600,
            cursor: 'pointer',
            fontFamily: 'inherit',
          }}
        >
          Forgot password
        </button>
      </div>
      
      <button type="submit" disabled={loading}
        style={{
          ...authPrimaryButtonStyle,
          background: loading ? tokens.borderHover : authPrimaryButtonStyle.background,
          cursor: loading ? 'not-allowed' : 'pointer',
          opacity: loading ? 0.7 : 1,
          boxShadow: loading ? 'none' : authPrimaryButtonStyle.boxShadow,
        }}
      >
        {loading ? 'Signing in...' : 'Sign In'}
      </button>
    </form>
  );
}

export function SignUp({ onSuccess }) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [name, setName] = useState('');
  const [agree, setAgree] = useState(true);
  const [notice, setNotice] = useState(null);
  const [loading, setLoading] = useState(false);
  const [cooldownUntil, setCooldownUntil] = useState(() => {
    const stored = Number(localStorage.getItem('saathi_signup_cooldown_until') || 0);
    return Number.isFinite(stored) ? stored : 0;
  });
  const [cooldownSeconds, setCooldownSeconds] = useState(0);

  useEffect(() => {
    const updateCooldown = () => {
      const seconds = Math.max(0, Math.ceil((cooldownUntil - Date.now()) / 1000));
      setCooldownSeconds(seconds);
      if (seconds === 0) {
        localStorage.removeItem('saathi_signup_cooldown_until');
      }
      return seconds;
    };

    if (!cooldownUntil || updateCooldown() === 0) return undefined;
    const interval = window.setInterval(updateCooldown, 1000);
    return () => window.clearInterval(interval);
  }, [cooldownUntil]);

  const isCoolingDown = cooldownSeconds > 0;

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (isCoolingDown) return;
    if (!agree) {
      setNotice({
        type: 'warning',
        title: 'Confirm before continuing',
        message: 'Please confirm the account terms before creating your workspace.',
      });
      return;
    }
    if (!supabase) {
      setNotice({ type: 'error', title: 'Auth is not configured', message: 'Missing Supabase environment variables.' });
      return;
    }
    setLoading(true);
    setNotice(null);
    clearDevAdminSession();

    const stop = startTimer('auth:signUp');
    const { data, error } = await supabase.auth.signUp({
      email: email.trim(),
      password,
      options: { data: { name: name.trim() } }
    });
    stop();

    if (error) {
      const seconds = parseAuthCooldownSeconds(error.message);
      if (seconds > 0 || isAuthRateLimitError(error.message)) {
        const cooldown = seconds || 60;
        const until = Date.now() + cooldown * 1000;
        localStorage.setItem('saathi_signup_cooldown_until', String(until));
        setCooldownUntil(until);
        setCooldownSeconds(cooldown);
        setNotice({
          type: 'warning',
          title: 'Try again in a moment',
          message: `Too many signup emails were requested. Retry in ${cooldown} seconds, or use Google sign-in.`,
        });
      } else {
        setNotice({
          type: 'error',
          title: 'Could not create account',
          message: friendlyAuthError(error.message),
        });
      }
    } 
    else if (data.user) {
      setNotice({
        type: 'success',
        title: 'Account created',
        message: data.session ? 'You are signed in.' : 'Check your email to confirm your account.',
      });
      if (onSuccess) onSuccess(data.user);
    } 
    else {
      setNotice({
        type: 'success',
        title: 'Check your email',
        message: 'We sent a confirmation link to finish creating your account.',
      });
    }
    setLoading(false);
  };

  const disabled = loading || isCoolingDown;
  const noticeTheme = notice ? authNoticeStyles[notice.type] || authNoticeStyles.error : null;

  return (
    <form onSubmit={handleSubmit} style={{ width: '100%' }}>
      
      {notice && (
        <div style={{ 
          padding: '12px 14px', 
          background: noticeTheme.background,
          border: `1px solid ${noticeTheme.border}`,
          borderRadius: 9,
          marginBottom: 16, 
          color: noticeTheme.color,
          fontSize: 13,
          lineHeight: 1.45,
        }}>
          <div style={{ fontWeight: 700, marginBottom: 3 }}>{notice.title}</div>
          <div style={{ color: notice.type === 'warning' ? '#fde68a' : noticeTheme.color }}>{notice.message}</div>
        </div>
      )}
      
      <div style={{ marginBottom: 14 }}>
        <label style={authLabelStyle}>Name</label>
        <input type="text" value={name} onChange={(e) => setName(e.target.value)} required autoComplete="name"
          placeholder="Enter your full name"
          style={authFieldStyle} />
      </div>
      
      <div style={{ marginBottom: 14 }}>
        <label style={authLabelStyle}>Email</label>
        <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoComplete="email"
          placeholder="Enter your email"
          style={authFieldStyle} />
      </div>
      
      <div style={{ marginBottom: 14 }}>
        <label style={authLabelStyle}>Password</label>
        <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required minLength={6} autoComplete="new-password"
          placeholder="Create a password"
          style={authFieldStyle} />
      </div>

      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, marginBottom: 22 }}>
        <label style={{ display: 'inline-flex', alignItems: 'center', gap: 8, fontSize: 12, color: tokens.textSecondary, cursor: 'pointer', lineHeight: 1.4 }}>
          <input
            type="checkbox"
            checked={agree}
            onChange={(e) => setAgree(e.target.checked)}
            style={{ accentColor: tokens.accent }}
          />
          I agree to the account terms
        </label>
        <span style={{ color: tokens.accentHover, fontSize: 12, fontWeight: 600, whiteSpace: 'nowrap' }}>
          Use 6+ characters
        </span>
      </div>
      
      <button type="submit" disabled={disabled}
        style={{
          ...authPrimaryButtonStyle,
          background: disabled ? tokens.borderHover : authPrimaryButtonStyle.background,
          color: disabled ? tokens.textMuted : "#fffefa",
          cursor: disabled ? 'not-allowed' : 'pointer',
          opacity: disabled ? 0.7 : 1,
          boxShadow: disabled ? 'none' : authPrimaryButtonStyle.boxShadow,
        }}
      >
        {loading ? 'Creating account...' : isCoolingDown ? `Try again in ${cooldownSeconds}s` : 'Create Account'}
      </button>
    </form>
  );
}

export function SignOut() {
  const { user, isDevAdmin, signOutDevAdmin } = useAuth();

  const handleSignOut = async () => {
    if (isDevAdmin) {
      signOutDevAdmin?.();
      window.location.reload();
      return;
    }
    if (!supabase) return;
    try {
      clearClientUserState(localStorage, user?.id);
    } catch (error) {
      console.warn('Failed to clear local SkedioAI state during sign-out', error);
    }
    const stop = startTimer('auth:signOut');
    await supabase.auth.signOut({ scope: 'local' });
    stop();
    window.location.reload();
  };
  return (
    <button onClick={handleSignOut}
      style={{
        padding: '8px 16px', background: 'transparent', border: `1px solid ${tokens.border}`, borderRadius: 6,
        fontSize: 13, cursor: 'pointer', color: tokens.textMuted,
      }}
    >
      Sign Out
    </button>
  );
}

export function GoogleSignIn() {
  const [loading, setLoading] = useState(false);

  const handleGoogleSignIn = async () => {
    if (!supabase) return;
    setLoading(true);
    clearDevAdminSession();
    const { error } = await supabase.auth.signInWithOAuth({
      provider: 'google',
      options: {
        redirectTo: window.location.origin,
        queryParams: {
          prompt: 'select_account',
        },
      },
    });
    if (error) { console.error('Google sign in error:', error); setLoading(false); }
  };

  return (
    <button onClick={handleGoogleSignIn} disabled={loading}
      style={{
        width: '100%', padding: '13px', background: loading ? tokens.bgHover : tokens.bgCard, 
        border: `1px solid ${tokens.border}`, borderRadius: 12, fontSize: 14, fontWeight: 600, color: tokens.text,
        cursor: loading ? 'not-allowed' : 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 10,
        transition: 'background 0.2s, border-color 0.2s, transform 0.12s',
      }}
    >
      {loading ? 'Signing in...' : <><GoogleIcon />Continue with Google</>}
    </button>
  );
}

function GoogleIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18">
      <path fill="#4285F4" d="M17.64 9.2c0-.637-.057-1.251-.164-1.84H9v3.481h4.844a4.14 4.14 0 0 1-1.796 2.716v2.259h2.908c1.702-1.567 2.684-3.875 2.684-6.615z"/>
      <path fill="#34A853" d="M9 18c2.43 0 4.467-.806 5.956-2.18l-2.908-2.259c-.806.54-1.837.86-3.048.86-2.344 0-4.328-1.584-5.036-3.711H.957v2.332A8.997 8.997 0 0 0 9 18z"/>
      <path fill="#FBBC05" d="M3.964 10.71A5.41 5.41 0 0 1 3.682 9c0-.593.102-1.17.282-1.71V4.958H.957A8.996 8.996 0 0 0 0 9c0 1.452.348 2.827.957 4.042l3.007-2.332z"/>
      <path fill="#EA4335" d="M9 3.58c1.321 0 2.508.454 3.44 1.345l2.582-2.58C13.463.891 11.426 0 9 0A8.997 8.997 0 0 0 .957 4.958L3.964 7.29C4.672 5.163 6.656 3.58 9 3.58z"/>
    </svg>
  );
}

function AuthCursorTrail() {
  const frameRef = useRef(null);
  const canvasRef = useRef(null);

  useEffect(() => {
    const frame = frameRef.current;
    const canvas = canvasRef.current;
    if (!frame || !canvas) return undefined;

    const media = window.matchMedia('(prefers-reduced-motion: reduce)');
    if (media.matches) return undefined;

    const ctx = canvas.getContext('2d');
    if (!ctx) return undefined;

    let animationFrame = 0;
    let mouseMoved = false;
    const params = {
      pointsNumber: 40,
      widthFactor: 0.3,
      spring: 0.4,
      friction: 0.5,
    };

    const pointer = { x: 0, y: 0 };
    const trail = Array.from({ length: params.pointsNumber }, () => ({
      x: 0,
      y: 0,
      dx: 0,
      dy: 0,
    }));

    const syncToCenter = () => {
      const width = frame.clientWidth;
      const height = frame.clientHeight;
      pointer.x = width * 0.52;
      pointer.y = height * 0.48;
      trail.forEach((point) => {
        point.x = pointer.x;
        point.y = pointer.y;
        point.dx = 0;
        point.dy = 0;
      });
    };

    const resizeCanvas = () => {
      const dpr = window.devicePixelRatio || 1;
      const width = frame.clientWidth;
      const height = frame.clientHeight;
      canvas.width = width * dpr;
      canvas.height = height * dpr;
      canvas.style.width = `${width}px`;
      canvas.style.height = `${height}px`;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      syncToCenter();
    };

    const updatePointer = (clientX, clientY) => {
      const rect = frame.getBoundingClientRect();
      pointer.x = clientX - rect.left;
      pointer.y = clientY - rect.top;
    };

    const handlePointerMove = (event) => {
      mouseMoved = true;
      updatePointer(event.clientX, event.clientY);
    };

    const handlePointerEnter = (event) => {
      mouseMoved = true;
      updatePointer(event.clientX, event.clientY);
    };

    const handleTouchMove = (event) => {
      if (!event.targetTouches?.[0]) return;
      mouseMoved = true;
      updatePointer(event.targetTouches[0].clientX, event.targetTouches[0].clientY);
    };

    const draw = () => {
      const width = frame.clientWidth;
      const height = frame.clientHeight;

      ctx.clearRect(0, 0, width, height);
      if (!mouseMoved) {
        animationFrame = window.requestAnimationFrame(draw);
        return;
      }

      trail.forEach((point, index) => {
        const prev = index === 0 ? pointer : trail[index - 1];
        const spring = index === 0 ? params.spring * 0.45 : params.spring;
        point.dx += (prev.x - point.x) * spring;
        point.dy += (prev.y - point.y) * spring;
        point.dx *= params.friction;
        point.dy *= params.friction;
        point.x += point.dx;
        point.y += point.dy;
      });

      ctx.save();
      ctx.lineCap = 'round';
      ctx.lineJoin = 'round';
      ctx.strokeStyle = 'rgba(79, 123, 255, 0.72)';
      ctx.beginPath();
      ctx.moveTo(trail[0].x, trail[0].y);

      for (let index = 1; index < trail.length - 1; index += 1) {
        const xc = 0.5 * (trail[index].x + trail[index + 1].x);
        const yc = 0.5 * (trail[index].y + trail[index + 1].y);
        ctx.lineWidth = params.widthFactor * (params.pointsNumber - index);
        ctx.quadraticCurveTo(trail[index].x, trail[index].y, xc, yc);
        ctx.stroke();
      }

      ctx.lineTo(trail[trail.length - 1].x, trail[trail.length - 1].y);
      ctx.stroke();

      ctx.restore();
      animationFrame = window.requestAnimationFrame(draw);
    };

    const resizeObserver = new ResizeObserver(resizeCanvas);
    resizeObserver.observe(frame);
    resizeCanvas();

    window.addEventListener('mousemove', handlePointerMove);
    window.addEventListener('click', handlePointerEnter);
    window.addEventListener('touchmove', handleTouchMove, { passive: true });
    animationFrame = window.requestAnimationFrame(draw);

    return () => {
      resizeObserver.disconnect();
      window.removeEventListener('mousemove', handlePointerMove);
      window.removeEventListener('click', handlePointerEnter);
      window.removeEventListener('touchmove', handleTouchMove);
      window.cancelAnimationFrame(animationFrame);
    };
  }, []);

  return (
    <>
      <div
        ref={frameRef}
        aria-hidden="true"
        style={{
          position: 'fixed',
          inset: 0,
        }}
      />
      <canvas
        ref={canvasRef}
        aria-hidden="true"
        style={{
          position: 'fixed',
          inset: 0,
          width: '100%',
          height: '100%',
          pointerEvents: 'none',
          opacity: 0.9,
          mixBlendMode: 'multiply',
          zIndex: 2,
        }}
      />
    </>
  );
}

function MascotPanel() {
  return (
    <div
      style={{
        position: 'relative',
        width: '100%',
        height: '100%',
        borderRadius: 24,
        overflow: 'hidden',
        background: 'linear-gradient(180deg, #edf1f9 0%, #e7ebf6 100%)',
        boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.68)',
      }}
    >
      <img
        src="/skedio_mascot.png"
        alt="SkedioAI mascot illustration"
        style={{
          width: '100%',
          height: '100%',
          objectFit: 'cover',
          display: 'block',
        }}
      />
    </div>
  );
}

function SkedioMark({ size = 34 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 64 64" fill="none" aria-hidden="true">
      <path d="M32 28 20 16M32 28l12-12M32 28v17" stroke="#1c1a17" strokeWidth="5" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M32 45c-4 4-8 5-13 5M32 45c4 4 8 5 13 5M32 45c-1 5-3 8-7 11M32 45c1 5 3 8 7 11" stroke="#1c1a17" strokeWidth="2.6" strokeLinecap="round" />
      <path d="M32 57c-2.2-2.8-2.2-4.9 0-7.4 2.2 2.5 2.2 4.6 0 7.4Z" fill="#8c99ec" stroke="#1c1a17" strokeWidth="1.4" />
      <path d="M32 5c5 5.2 5 10.3 0 15.5C27 15.3 27 10.2 32 5Z" fill="#9ead78" />
      <path d="M16 17c5.5.8 8.5 3.8 9.2 9.2C19.8 25.5 16.8 22.5 16 17Z" fill="#8d9f68" />
      <path d="M48 17c-.8 5.5-3.8 8.5-9.2 9.2C39.5 20.8 42.5 17.8 48 17Z" fill="#8d9f68" />
      <path d="M11 30c4.4-.7 7.4.9 9.1 4.8C15.8 35.4 12.8 33.8 11 30Z" fill="#bcc2f4" />
      <path d="M53 30c-1.8 3.8-4.8 5.4-9.1 4.8C45.6 30.9 48.6 29.3 53 30Z" fill="#bcc2f4" />
      <path d="M24 30c3.1.6 4.8 2.4 5.2 5.5C26.1 34.9 24.4 33.1 24 30Z" fill="#9ead78" />
      <path d="M40 30c-.4 3.1-2.1 4.9-5.2 5.5C35.2 32.4 36.9 30.6 40 30Z" fill="#9ead78" />
    </svg>
  );
}

// ─── Auth Gate Component ───
export function AuthGate({ children, fallback }) {
  const { isAuthenticated, loading, error } = useAuth();
  
  if (loading) {
    return (
      <div style={{ 
        minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center',
        background: tokens.bg, flexDirection: 'column', gap: 16
      }}>
        <div style={{ 
          width: 24, height: 24, border: `2px solid ${tokens.border}`, borderTopColor: tokens.indigo,
          borderRadius: '50%', animation: 'spin 0.6s linear infinite'
        }} />
        <span style={{ color: tokens.textMuted, fontSize: 14 }}>Loading...</span>
        {error && <span style={{ color: tokens.red, fontSize: 12 }}>Error: {error}</span>}
      </div>
    );
  }

  if (!isAuthenticated) {
    if (fallback) {
      if (typeof fallback === 'function') return <fallback />;
      return fallback;
    }
    return <DefaultLoginScreen />;
  }

  return children;
}

export function DefaultLoginScreen() {
  const [mode, setMode] = useState('signin');
  const { signInAsDevAdmin } = useAuth();

  const handleDevAdmin = () => {
    void signInAsDevAdmin?.();
  };

  return (
    <div style={{ minHeight: '100vh', position: 'relative', background: 'linear-gradient(180deg, #fcfbf7 0%, #f4f2eb 100%)', color: tokens.text, padding: '20px 24px', boxSizing: 'border-box' }}>
      <AuthCursorTrail />
      <div
        style={{
          width: 'min(1360px, 100%)',
          height: 'calc(100vh - 40px)',
          margin: '0 auto',
          position: 'relative',
          borderRadius: 28,
          background: 'rgba(255, 254, 250, 0.96)',
          border: `1px solid ${tokens.borderSubtle}`,
          boxShadow: '0 28px 80px rgba(76, 88, 132, 0.12)',
          display: 'grid',
          gridTemplateColumns: 'minmax(420px, 0.95fr) minmax(460px, 1.05fr)',
          overflow: 'hidden',
        }}
      >
        <div style={{ position: 'relative', zIndex: 1, padding: '22px 28px', display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: 0, overflow: 'hidden' }}>
          <div style={{ width: '100%', maxWidth: 360 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 18 }}>
              <SkedioMark size={34} />
              <span style={{
                fontSize: 19, fontWeight: 700, color: tokens.text,
                fontFamily: 'Inter, system-ui, sans-serif',
                letterSpacing: '-0.02em',
              }}>SkedioAI</span>
            </div>

            <div style={{ marginBottom: 18 }}>
              <h1 style={{
                fontSize: 50,
                lineHeight: 0.98,
                margin: 0,
                marginBottom: 10,
                color: tokens.text,
                fontFamily: 'Inter, system-ui, sans-serif',
                fontWeight: 800,
                letterSpacing: '-0.03em',
              }}>
                {mode === 'signin' ? 'Welcome Back!' : 'Create account'}
              </h1>
              <p style={{ color: tokens.textSecondary, fontSize: 14, lineHeight: 1.6, margin: 0 }}>
                {mode === 'signin'
                  ? 'Sign in with your email and password.'
                  : 'Set up your account and start planning with clarity.'}
              </p>
            </div>

            <div style={{
              display: 'flex', gap: 2, marginBottom: 18,
              background: tokens.bg, padding: 4, borderRadius: 16,
              border: `1px solid ${tokens.borderSubtle}`,
            }}>
              <button onClick={() => setMode('signin')}
                style={{
                  flex: 1, padding: '11px 12px',
                  background: mode === 'signin' ? tokens.bgCard : 'transparent',
                  color: mode === 'signin' ? tokens.text : tokens.textMuted,
                  border: 'none', borderRadius: 12,
                  fontSize: 14, cursor: 'pointer', fontWeight: 700,
                  transition: `all ${tokens.transitionFast}`,
                  boxShadow: mode === 'signin' ? tokens.shadowSm : 'none',
                }}>Sign In</button>
              <button onClick={() => setMode('signup')}
                style={{
                  flex: 1, padding: '11px 12px',
                  background: mode === 'signup' ? tokens.bgCard : 'transparent',
                  color: mode === 'signup' ? tokens.text : tokens.textMuted,
                  border: 'none', borderRadius: 12,
                  fontSize: 14, cursor: 'pointer', fontWeight: 700,
                  transition: `all ${tokens.transitionFast}`,
                  boxShadow: mode === 'signup' ? tokens.shadowSm : 'none',
                }}>Sign Up</button>
            </div>

            {mode === 'signin' ? <SignIn /> : <SignUp />}

            <div style={{ display: 'flex', alignItems: 'center', margin: '14px 0', color: tokens.textDim, fontSize: 11 }}>
              <div style={{ flex: 1, height: 1, background: tokens.borderSubtle }} />
              <span style={{ padding: `0 ${tokens.space4}` }}>Or login with</span>
              <div style={{ flex: 1, height: 1, background: tokens.borderSubtle }} />
            </div>

            <GoogleSignIn />

            {allowDevAdminAuth && (
              <>
                <div style={{ display: 'flex', alignItems: 'center', margin: '14px 0 10px', color: tokens.textDim, fontSize: 10, letterSpacing: '0.1em' }}>
                  <div style={{ flex: 1, height: 1, background: tokens.borderSubtle }} />
                  <span style={{ padding: `0 ${tokens.space4}` }}>DEV</span>
                  <div style={{ flex: 1, height: 1, background: tokens.borderSubtle }} />
                </div>

                <button
                  type="button"
                  onClick={handleDevAdmin}
                  style={{
                    width: '100%',
                    padding: '13px',
                    background: tokens.accentMuted,
                    color: tokens.text,
                    border: `1px solid ${tokens.accentBorder}`,
                    borderRadius: 14,
                    fontSize: 14,
                    fontWeight: 800,
                    cursor: 'pointer',
                    fontFamily: 'inherit',
                  }}
                >
                  Continue as sample admin
                </button>
              </>
            )}

            {!supabaseUrl && (
              <div style={{
                marginTop: 18, padding: tokens.space4,
                background: tokens.yellowBg, border: `1px solid ${tokens.yellowBorder}`,
                borderRadius: 12, fontSize: 12, color: tokens.yellowText,
              }}>
                Add <b>VITE_SUPABASE_URL</b> to your .env file to enable auth.
              </div>
            )}
          </div>
        </div>

        <div style={{ position: 'relative', zIndex: 1, padding: 20, minHeight: 0 }}>
          <MascotPanel />
        </div>
      </div>
    </div>
  );
}
