'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import api from '@/lib/api';

type Step = 'email' | 'otp';

export default function LoginPage() {
  const router = useRouter();
  const [step, setStep] = useState<Step>('email');
  const [email, setEmail] = useState('');
  const [otp, setOtp] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  async function handleSendOtp(e: React.FormEvent) {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await api.post('/api/auth/send-otp', { email: email.trim().toLowerCase() });
      setStep('otp');
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { error?: string } } })
        ?.response?.data?.error ?? 'Failed to send code. Please try again.';
      setError(msg);
    } finally {
      setLoading(false);
    }
  }

  async function handleVerifyOtp(e: React.FormEvent) {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const res = await api.post('/api/auth/verify-otp', {
        email: email.trim().toLowerCase(),
        code: otp.trim(),
      });
      localStorage.setItem('token', res.data.token);
      localStorage.setItem('userEmail', res.data.email);
      document.cookie = `hlp_token=${res.data.token}; path=/; max-age=86400; SameSite=Strict`;
      router.push('/');
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { error?: string } } })
        ?.response?.data?.error ?? 'Invalid or expired code.';
      setError(msg);
      setOtp('');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50">
      <div className="w-full max-w-md rounded-2xl border border-gray-200 bg-white p-8 shadow-sm">
        <div className="mb-8 flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-blue-600 font-bold text-white">
            HL
          </div>
          <div>
            <h1 className="text-xl font-bold text-gray-900">HomeLend Pro</h1>
            <p className="text-xs text-gray-500">Real Estate & Mortgage Platform</p>
          </div>
        </div>

        {step === 'email' ? (
          <>
            <h2 className="mb-1 text-2xl font-bold text-gray-900">Sign in</h2>
            <p className="mb-6 text-sm text-gray-500">
              Enter your email to receive a one-time code.
            </p>
            <form onSubmit={handleSendOtp} className="space-y-4">
              <div>
                <label className="mb-1 block text-sm font-medium text-gray-700">
                  Email address
                </label>
                <input
                  type="email"
                  required
                  autoFocus
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@example.com"
                  className="w-full rounded-lg border border-gray-300 px-4 py-2.5 text-sm
                             focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                />
              </div>
              {error && <p className="text-sm text-red-600">{error}</p>}
              <button
                type="submit"
                disabled={loading}
                className="w-full rounded-lg bg-blue-600 px-4 py-2.5 text-sm font-medium text-white
                           hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {loading ? 'Sending...' : 'Send code'}
              </button>
            </form>
          </>
        ) : (
          <>
            <h2 className="mb-1 text-2xl font-bold text-gray-900">Enter your code</h2>
            <p className="mb-6 text-sm text-gray-500">
              We sent a 6-digit code to <strong>{email}</strong>.
            </p>
            <form onSubmit={handleVerifyOtp} className="space-y-4">
              <div>
                <label className="mb-1 block text-sm font-medium text-gray-700">
                  One-time code
                </label>
                <input
                  type="text"
                  inputMode="numeric"
                  pattern="[0-9]{6}"
                  maxLength={6}
                  required
                  autoFocus
                  value={otp}
                  onChange={(e) => setOtp(e.target.value.replace(/\D/g, ''))}
                  placeholder="000000"
                  className="w-full rounded-lg border border-gray-300 px-4 py-2.5 text-center
                             text-2xl font-mono tracking-widest focus:border-blue-500
                             focus:outline-none focus:ring-1 focus:ring-blue-500"
                />
              </div>
              {error && <p className="text-sm text-red-600">{error}</p>}
              <button
                type="submit"
                disabled={loading || otp.length !== 6}
                className="w-full rounded-lg bg-blue-600 px-4 py-2.5 text-sm font-medium text-white
                           hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {loading ? 'Verifying...' : 'Sign in'}
              </button>
              <button
                type="button"
                onClick={() => { setStep('email'); setError(''); setOtp(''); }}
                className="w-full text-sm text-gray-500 hover:text-gray-700"
              >
                Use a different email
              </button>
            </form>
          </>
        )}
      </div>
    </div>
  );
}
