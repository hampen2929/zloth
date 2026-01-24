import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { cn, truncate, formatRelativeTime, generateId } from '../utils';

describe('cn (class name merger)', () => {
  it('should merge multiple class names', () => {
    expect(cn('foo', 'bar')).toBe('foo bar');
  });

  it('should handle conditional classes', () => {
    expect(cn('foo', false && 'bar', 'baz')).toBe('foo baz');
    expect(cn('foo', true && 'bar', 'baz')).toBe('foo bar baz');
  });

  it('should deduplicate conflicting Tailwind classes', () => {
    expect(cn('text-red-500', 'text-blue-500')).toBe('text-blue-500');
    expect(cn('p-4', 'p-2')).toBe('p-2');
  });

  it('should handle empty inputs', () => {
    expect(cn()).toBe('');
    expect(cn('')).toBe('');
  });

  it('should handle arrays and objects', () => {
    expect(cn(['foo', 'bar'])).toBe('foo bar');
    expect(cn({ foo: true, bar: false })).toBe('foo');
  });
});

describe('truncate', () => {
  it('should return the original text if shorter than maxLength', () => {
    expect(truncate('hello', 10)).toBe('hello');
  });

  it('should truncate and add ellipsis if longer than maxLength', () => {
    expect(truncate('hello world', 8)).toBe('hello...');
  });

  it('should handle edge cases', () => {
    expect(truncate('', 5)).toBe('');
    expect(truncate('abc', 3)).toBe('abc');
    expect(truncate('abcd', 3)).toBe('...');
  });

  it('should handle exact length match', () => {
    expect(truncate('hello', 5)).toBe('hello');
  });
});

describe('formatRelativeTime', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2025-01-15T12:00:00Z'));
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('should return "just now" for times less than a minute ago', () => {
    const date = new Date('2025-01-15T11:59:30Z');
    expect(formatRelativeTime(date)).toBe('just now');
  });

  it('should format minutes correctly', () => {
    const date1 = new Date('2025-01-15T11:59:00Z');
    expect(formatRelativeTime(date1)).toBe('1 minute ago');

    const date5 = new Date('2025-01-15T11:55:00Z');
    expect(formatRelativeTime(date5)).toBe('5 minutes ago');
  });

  it('should format hours correctly', () => {
    const date1 = new Date('2025-01-15T11:00:00Z');
    expect(formatRelativeTime(date1)).toBe('1 hour ago');

    const date3 = new Date('2025-01-15T09:00:00Z');
    expect(formatRelativeTime(date3)).toBe('3 hours ago');
  });

  it('should format days correctly', () => {
    const date1 = new Date('2025-01-14T12:00:00Z');
    expect(formatRelativeTime(date1)).toBe('1 day ago');

    const date7 = new Date('2025-01-08T12:00:00Z');
    expect(formatRelativeTime(date7)).toBe('7 days ago');
  });

  it('should handle string dates', () => {
    const dateString = '2025-01-15T11:55:00Z';
    expect(formatRelativeTime(dateString)).toBe('5 minutes ago');
  });
});

describe('generateId', () => {
  it('should return a UUID string', () => {
    const id = generateId();
    expect(id).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i);
  });
});
