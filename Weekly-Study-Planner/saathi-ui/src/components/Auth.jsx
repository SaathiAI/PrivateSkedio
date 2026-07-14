/* eslint-disable react-refresh/only-export-components */
/**
 * Auth.jsx - Supabase Authentication Components for SkedioAI
 * 
 * Usage:
 *   - Add AuthProvider wrapper to App.jsx
 *   - Use useAuth() hook to get current user
 */

import { createContext, useContext, useState, useEffect } from 'react';
import { createClient } from '@supabase/supabase-js';
import { clearClientUserState } from "../lib/clientState.js";
import { startTimer } from "../lib/perf.js";
import { tokens } from '../theme.js';

// Initialize Supabase client
const supabaseUrl = import.meta.env.VITE_SUPABASE_URL;
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY;

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

// ─── Auth Context ───
const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [session, setSession] = useState(null);
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(!!supabase);
  const [error, setError] = useState(null);

  useEffect(() => {
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
      setSession(session);
      setUser(session?.user ?? null);
      setLoading(false);
    }).catch((err) => {
      stop();
      console.error('Supabase auth catch:', err);
      setError(err.message);
      setLoading(false);
    });

    // Listen for auth changes
    const { data: { subscription } } = supabase.auth.onAuthStateChange(
      (_event, session) => {
        setSession(session);
        setUser(session?.user ?? null);
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
  return supabase?.auth.getSession().then(({ data }) => data.session?.access_token);
}

// ─── API Helper with Auth ───
export async function authFetch(url, options = {}) {
  if (!supabase) {
    throw new Error('Supabase not configured');
  }

  const { data: { session } } = await supabase.auth.getSession();
  
  const headers = {
    'Content-Type': 'application/json',
    ...options.headers,
  };

  if (session?.access_token) {
    headers['Authorization'] = `Bearer ${session.access_token}`;
  }

  const response = await fetch(url, {
    ...options,
    headers,
  });

  if (response.status === 401) {
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
        <label style={{ display: 'block', marginBottom: 8, fontSize: 12, color: tokens.textMuted, letterSpacing: "0.08em", textTransform: "uppercase" }}>Email</label>
        <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required
          style={{
            width: '100%', padding: '13px 14px', background: "#101010", border: `1px solid ${tokens.border}`,
            borderRadius: 8, fontSize: 14, color: tokens.text, outline: 'none',
          }}
        />
      </div>
      
      <div style={{ marginBottom: 24 }}>
        <label style={{ display: 'block', marginBottom: 8, fontSize: 12, color: tokens.textMuted, letterSpacing: "0.08em", textTransform: "uppercase" }}>Password</label>
        <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required
          style={{
            width: '100%', padding: '13px 14px', background: "#101010", border: `1px solid ${tokens.border}`,
            borderRadius: 8, fontSize: 14, color: tokens.text, outline: 'none',
          }}
        />
      </div>
      
      <button type="submit" disabled={loading}
        style={{
          width: '100%', padding: '13px', background: loading ? tokens.borderHover : tokens.text, color: tokens.bg,
          border: 'none', borderRadius: 8, fontSize: 14, fontWeight: 600, cursor: loading ? 'not-allowed' : 'pointer',
          transition: "background 0.2s", boxShadow: loading ? "none" : "0 12px 30px rgba(238,238,238,0.08)"
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
    if (!supabase) {
      setNotice({ type: 'error', title: 'Auth is not configured', message: 'Missing Supabase environment variables.' });
      return;
    }
    setLoading(true);
    setNotice(null);

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
      
      <div style={{ marginBottom: 16 }}>
        <label style={{ display: 'block', marginBottom: 8, fontSize: 12, color: tokens.textMuted, letterSpacing: "0.08em", textTransform: "uppercase" }}>Name</label>
        <input type="text" value={name} onChange={(e) => setName(e.target.value)} required autoComplete="name"
          style={{
            width: '100%', padding: '13px 14px', background: "#101010", border: `1px solid ${tokens.border}`,
            borderRadius: 8, fontSize: 14, color: tokens.text, outline: 'none',
          }} />
      </div>
      
      <div style={{ marginBottom: 16 }}>
        <label style={{ display: 'block', marginBottom: 8, fontSize: 12, color: tokens.textMuted, letterSpacing: "0.08em", textTransform: "uppercase" }}>Email</label>
        <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoComplete="email"
          style={{
            width: '100%', padding: '13px 14px', background: "#101010", border: `1px solid ${tokens.border}`,
            borderRadius: 8, fontSize: 14, color: tokens.text, outline: 'none',
          }} />
      </div>
      
      <div style={{ marginBottom: 24 }}>
        <label style={{ display: 'block', marginBottom: 8, fontSize: 12, color: tokens.textMuted, letterSpacing: "0.08em", textTransform: "uppercase" }}>Password</label>
        <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required minLength={6} autoComplete="new-password"
          style={{
            width: '100%', padding: '13px 14px', background: "#101010", border: `1px solid ${tokens.border}`,
            borderRadius: 8, fontSize: 14, color: tokens.text, outline: 'none',
          }} />
      </div>
      
      <button type="submit" disabled={disabled}
        style={{
          width: '100%',
          padding: '13px',
          background: disabled ? "#2a2a2a" : tokens.text,
          color: disabled ? tokens.textMuted : tokens.bg,
          border: 'none',
          borderRadius: 8,
          fontSize: 14,
          fontWeight: 600,
          cursor: disabled ? 'not-allowed' : 'pointer',
          transition: 'background 0.2s, color 0.2s',
        }}
      >
        {loading ? 'Creating account...' : isCoolingDown ? `Try again in ${cooldownSeconds}s` : 'Create Account'}
      </button>
    </form>
  );
}

export function SignOut() {
  const { user } = useAuth();

  const handleSignOut = async () => {
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
        width: '100%', padding: '13px', background: loading ? tokens.bgHover : "#101010", 
        border: `1px solid ${tokens.borderHover}`, borderRadius: 8, fontSize: 14, fontWeight: 500, color: tokens.text,
        cursor: loading ? 'not-allowed' : 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 10,
        transition: 'background 0.2s'
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

  return (
    <div style={{ flex: 1, display: 'flex', minHeight: '100vh', background: tokens.bg, color: tokens.text }}>
      
      {/* Left Form Section */}
      <div style={{ 
        width: "min(480px, 100%)", display: 'flex', flexDirection: 'column', 
        justifyContent: 'center', padding: `${tokens.space10} clamp(${tokens.space6}, 5vw, 64px)`,
        borderRight: `1px solid ${tokens.borderSubtle}`,
        position: 'relative', background: tokens.bgCard,
      }}>
          {/* Logo */}
          <div style={{
            position: 'absolute', top: tokens.space8, left: `clamp(${tokens.space6}, 5vw, 64px)`,
            display: 'flex', alignItems: 'center', gap: tokens.space3,
          }}>
             <div style={{
               width: 32, height: 32, borderRadius: tokens.radiusMd,
               background: tokens.text, color: tokens.bg,
               display: "flex", alignItems: "center", justifyContent: "center",
               fontWeight: 700, fontSize: 14,
             }}>S</div>
             <span style={{
               fontSize: 18, fontWeight: 500, color: tokens.text,
               fontFamily: "'Playfair Display', serif", fontStyle: "italic",
             }}>SkedioAI</span>
          </div>
          
          {/* Heading */}
          <div style={{ marginBottom: tokens.space8, marginTop: 80 }}>
            <div style={{
              fontSize: 10, color: tokens.textDim, letterSpacing: "0.12em",
              textTransform: "uppercase", marginBottom: tokens.space4,
            }}>Study operating system</div>
            <h1 style={{
              fontSize: "clamp(28px, 3.5vw, 40px)",
              lineHeight: 1.1,
              marginBottom: tokens.space4,
              color: tokens.text,
              fontFamily: "'Playfair Display', serif",
              fontWeight: 500,
              fontStyle: "italic",
              letterSpacing: '-0.02em',
            }}>
              {mode === 'signin' ? 'Welcome back.' : 'Start studying.'}
            </h1>
            <p style={{ color: tokens.textMuted, fontSize: 14, lineHeight: 1.6, maxWidth: 360 }}>
              {mode === 'signin'
                ? 'Sign in to access your plan, progress, and study coach.'
                : 'Create an account to save plans and track your progress.'}
            </p>
          </div>

          {/* Mode switcher */}
          <div style={{
            display: 'flex', gap: 2, marginBottom: tokens.space6,
            background: tokens.bg, padding: 3, borderRadius: tokens.radiusLg,
            border: `1px solid ${tokens.borderSubtle}`,
          }}>
            <button onClick={() => setMode('signin')}
              style={{
                flex: 1, padding: `${tokens.space2} ${tokens.space3}`,
                background: mode === 'signin' ? tokens.bgCard : 'transparent',
                color: mode === 'signin' ? tokens.text : tokens.textMuted,
                border: 'none', borderRadius: tokens.radiusMd,
                fontSize: 13, cursor: 'pointer', fontWeight: 500,
                transition: `all ${tokens.transitionFast}`,
                boxShadow: mode === 'signin' ? tokens.shadowSm : 'none',
              }}>Sign In</button>
            <button onClick={() => setMode('signup')}
              style={{
                flex: 1, padding: `${tokens.space2} ${tokens.space3}`,
                background: mode === 'signup' ? tokens.bgCard : 'transparent',
                color: mode === 'signup' ? tokens.text : tokens.textMuted,
                border: 'none', borderRadius: tokens.radiusMd,
                fontSize: 13, cursor: 'pointer', fontWeight: 500,
                transition: `all ${tokens.transitionFast}`,
                boxShadow: mode === 'signup' ? tokens.shadowSm : 'none',
              }}>Sign Up</button>
          </div>

          {mode === 'signin' ? <SignIn /> : <SignUp />}

          {/* Divider */}
          <div style={{ display: 'flex', alignItems: 'center', margin: `${tokens.space6} 0`, color: tokens.textDim, fontSize: 10, letterSpacing: '0.1em' }}>
            <div style={{ flex: 1, height: 1, background: tokens.borderSubtle }} />
            <span style={{ padding: `0 ${tokens.space4}` }}>OR</span>
            <div style={{ flex: 1, height: 1, background: tokens.borderSubtle }} />
          </div>

          <GoogleSignIn />

          {!supabaseUrl && (
            <div style={{
              marginTop: tokens.space6, padding: tokens.space4,
              background: tokens.yellowBg, border: `1px solid ${tokens.yellowBorder}`,
              borderRadius: tokens.radiusMd, fontSize: 12, color: tokens.yellowText,
            }}>
              Add <b>VITE_SUPABASE_URL</b> to your .env file to enable auth.
            </div>
          )}
      </div>

      {/* Right Product Preview Section */}
      <div style={{ 
        flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
        background: tokens.bg, position: 'relative', overflow: 'hidden', padding: tokens.space10,
      }}>
        <div style={{ 
            width: 'min(680px, 100%)', border: `1px solid ${tokens.borderSubtle}`, borderRadius: tokens.radiusXl,
            background: tokens.bgCard, boxShadow: tokens.shadowXl, overflow: "hidden",
            animation: 'fadeUp 0.6s cubic-bezier(0.16, 1, 0.3, 1)',
        }}>
           {/* Preview header */}
           <div style={{
             padding: tokens.space5, borderBottom: `1px solid ${tokens.borderSubtle}`,
             display: "flex", justifyContent: "space-between", alignItems: "center",
           }}>
             <div>
               <div style={{ fontSize: 10, color: tokens.textDim, letterSpacing: "0.1em", textTransform: "uppercase" }}>Today</div>
               <div style={{ marginTop: 4, fontSize: 20, fontFamily: "'Playfair Display', serif", fontWeight: 500, fontStyle: "italic" }}>Maths sprint</div>
             </div>
             <div style={{ display: "flex", gap: tokens.space2 }}>
               <span style={{
                 padding: `${tokens.space1} ${tokens.space3}`, borderRadius: tokens.radiusFull,
                 background: tokens.greenBg, border: `1px solid ${tokens.greenBorder}`,
                 color: tokens.greenText, fontSize: 11, fontWeight: 500,
               }}>Synced</span>
               <span style={{
                 padding: `${tokens.space1} ${tokens.space3}`, borderRadius: tokens.radiusFull,
                 background: tokens.accentMuted, border: `1px solid ${tokens.accentBorder}`,
                 color: tokens.accent, fontSize: 11, fontWeight: 500,
               }}>Coach</span>
             </div>
           </div>

           {/* Preview grid */}
           <div style={{ padding: tokens.space5, display: "grid", gridTemplateColumns: "1fr 1fr", gap: tokens.space3 }}>
             {[
               ["08:00", "Quadratics warm-up", "18/24 checked"],
               ["15:00", "Statistics practice", "Calendar protected"],
               ["18:30", "Reschedule check", "No conflict"],
               ["21:00", "Light review", "Optional buffer"],
             ].map(([time, title, meta]) => (
               <div key={title} style={{
                 border: `1px solid ${tokens.borderSubtle}`,
                 borderRadius: tokens.radiusMd, background: tokens.bg,
                 padding: tokens.space4,
               }}>
                 <div style={{ fontSize: 11, color: tokens.textDim, marginBottom: tokens.space2 }}>{time}</div>
                 <div style={{ fontSize: 13, color: tokens.text, fontWeight: 500, marginBottom: tokens.space2 }}>{title}</div>
                 <div style={{ fontSize: 11, color: tokens.greenText }}>{meta}</div>
               </div>
             ))}
           </div>

           {/* Footer note */}
           <div style={{ padding: `0 ${tokens.space5} ${tokens.space5}` }}>
             <div style={{
               border: `1px solid ${tokens.borderSubtle}`,
               borderRadius: tokens.radiusMd, padding: tokens.space4,
               background: tokens.bg,
             }}>
               <div style={{ color: tokens.textMuted, fontSize: 12, lineHeight: 1.6 }}>
                 SkedioAI manages your plan, calendar, and progress — so you can focus on studying.
               </div>
             </div>
           </div>
        </div>
      </div>
    </div>
  );
}
