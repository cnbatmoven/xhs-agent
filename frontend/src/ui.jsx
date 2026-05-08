import React from 'react';
import { T } from './tokens.js';

export const Ico = {
  search: (p) => <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" {...p}><circle cx="6" cy="6" r="4" /><path d="M9 9l4 4" /></svg>,
  link: (p) => <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" {...p}><path d="M6 8a3 3 0 004.2 0l2-2a3 3 0 10-4.2-4.2L7 3" /><path d="M8 6a3 3 0 00-4.2 0l-2 2a3 3 0 104.2 4.2L7 11" /></svg>,
  user: (p) => <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" {...p}><circle cx="7" cy="5" r="2.5" /><path d="M2.5 12c.5-2.5 2.3-3.5 4.5-3.5s4 1 4.5 3.5" /></svg>,
  hash: (p) => <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" {...p}><path d="M2 5h10M2 9h10M5.5 2l-1 10M9.5 2l-1 10" /></svg>,
  upload: (p) => <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" {...p}><path d="M2 10v2h10v-2M7 2v8M4 5l3-3 3 3" /></svg>,
  filter: (p) => <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" {...p}><path d="M1 3h12M3 7h8M5 11h4" /></svg>,
  download: (p) => <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" {...p}><path d="M2 11v1h10v-1M7 2v8M4 7l3 3 3-3" /></svg>,
  copy: (p) => <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.5" {...p}><rect x="4" y="4" width="8" height="8" rx="1" /><path d="M2 10V3a1 1 0 011-1h7" /></svg>,
  expand: (p) => <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" {...p}><path d="M9 2h3v3M5 12H2V9M12 2L8 6M2 12l4-4" /></svg>,
  send: (p) => <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" {...p}><path d="M12 7L2 2l2 5-2 5z" /></svg>,
  plus: (p) => <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" {...p}><path d="M7 2v10M2 7h10" /></svg>,
  table: (p) => <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.5" {...p}><rect x="2" y="2" width="10" height="10" /><path d="M2 5.5h10M2 9h10M5.5 2v10" /></svg>,
  json: (p) => <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" {...p}><path d="M5 2H3v10h2M9 2h2v10H9" /></svg>,
  grid: (p) => <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.5" {...p}><rect x="2" y="2" width="4" height="4" /><rect x="8" y="2" width="4" height="4" /><rect x="2" y="8" width="4" height="4" /><rect x="8" y="8" width="4" height="4" /></svg>,
  chart: (p) => <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" {...p}><path d="M2 12h10M4 9v3M7 5v7M10 7v5" /></svg>,
  doc: (p) => <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" {...p}><path d="M3 1h6l3 3v9H3z" /><path d="M5 6h4M5 9h4" /></svg>,
  trash: (p) => <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" {...p}><path d="M2 3.5h10M5.5 3.5V2h3v1.5M4 5l.5 7h5L10 5" /></svg>,
};

export function Pill({ children, color = T.fg2, bg = T.bg3, br = T.br1 }) {
  return <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, padding: '2px 7px', borderRadius: 999, background: bg, border: `1px solid ${br}`, color, fontSize: 11, fontFamily: T.mono, lineHeight: 1.4 }}>{children}</span>;
}

export function Dot({ color = T.ok }) {
  return <span style={{ display: 'inline-block', width: 6, height: 6, borderRadius: '50%', background: color }} />;
}

export function Kbd({ children }) {
  return <span style={{ display: 'inline-block', padding: '1px 5px', borderRadius: 4, background: T.bg3, border: `1px solid ${T.br1}`, color: T.fg2, fontSize: 10, fontFamily: T.mono, lineHeight: 1.4 }}>{children}</span>;
}

export function Num({ children, color = T.fg1 }) {
  return <span style={{ fontFamily: T.mono, fontVariantNumeric: 'tabular-nums', color }}>{children}</span>;
}

export const btnIcon = {
  width: 28,
  height: 28,
  display: 'inline-flex',
  alignItems: 'center',
  justifyContent: 'center',
  background: 'transparent',
  border: 'none',
  borderRadius: 6,
  color: T.fg3,
  cursor: 'pointer',
};

export const btnPrimary = {
  display: 'inline-flex',
  alignItems: 'center',
  gap: 6,
  padding: '7px 12px',
  background: T.red,
  border: 'none',
  borderRadius: 8,
  color: '#fff',
  fontSize: 12,
  fontWeight: 600,
  cursor: 'pointer',
};
