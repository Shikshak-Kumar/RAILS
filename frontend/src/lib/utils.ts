import type { RiskLevel } from '@/types';

export function riskColor(level: RiskLevel): {
  bg: string;
  text: string;
  border: string;
  dot: string;
  label: string;
} {
  switch (level) {
    case 'CRITICAL':
      return {
        bg: 'bg-red-600',
        text: 'text-red-400',
        border: 'border-red-600',
        dot: 'bg-red-500',
        label: 'CRITICAL',
      };
    case 'HIGH':
      return {
        bg: 'bg-red-500/90',
        text: 'text-red-400',
        border: 'border-red-500',
        dot: 'bg-red-400',
        label: 'HIGH',
      };
    case 'MEDIUM':
      return {
        bg: 'bg-yellow-500',
        text: 'text-yellow-400',
        border: 'border-yellow-500',
        dot: 'bg-yellow-400',
        label: 'MEDIUM',
      };
    case 'LOW':
    default:
      return {
        bg: 'bg-green-600',
        text: 'text-green-400',
        border: 'border-green-600',
        dot: 'bg-green-500',
        label: 'LOW',
      };
  }
}

export function riskBarColor(score: number): string {
  if (score >= 0.85) return 'bg-red-600';
  if (score >= 0.7) return 'bg-red-500';
  if (score >= 0.4) return 'bg-yellow-500';
  return 'bg-green-600';
}

export function formatCurrency(amount: number, currency = 'USD'): string {
  const symbols: Record<string, string> = {
    USD: '$', EUR: '€', GBP: '£', INR: '₹', AED: 'AED ', SGD: 'S$', CHF: 'CHF ',
  };
  const symbol = symbols[currency] ?? '';
  if (amount >= 1_000_000_000) return `${symbol}${(amount / 1_000_000_000).toFixed(2)}B`;
  if (amount >= 1_000_000) return `${symbol}${(amount / 1_000_000).toFixed(2)}M`;
  if (amount >= 1_000) return `${symbol}${(amount / 1_000).toFixed(1)}K`;
  return `${symbol}${amount.toFixed(2)}`;
}

export function formatNumber(n: number): string {
  return n.toLocaleString('en-US');
}

export function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const sec = Math.floor(diff / 1000);
  if (sec < 60) return `${sec}s ago`;
  const min = Math.floor(sec / 60);
  if (min < 60) return `${min}m ago`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr}h ago`;
  const day = Math.floor(hr / 24);
  if (day < 30) return `${day}d ago`;
  return new Date(iso).toLocaleDateString();
}

export function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
}
