import { describe, it, expect } from 'vitest';
import { classifyError, getErrorDisplay } from '../error-handling';

describe('classifyError', () => {
  describe('network errors', () => {
    it.each([
      'Network error occurred',
      'Connection refused',
      'Request timeout',
      'ECONNREFUSED',
      'fetch failed',
    ])('should classify "%s" as network error', (errorMessage) => {
      expect(classifyError(errorMessage)).toBe('network');
    });
  });

  describe('authentication errors', () => {
    it.each([
      'Unauthorized access',
      '401 Unauthorized',
      'Authentication failed',
      'Invalid API key',
      'api key expired',
    ])('should classify "%s" as auth error', (errorMessage) => {
      expect(classifyError(errorMessage)).toBe('auth');
    });
  });

  describe('permission errors', () => {
    it.each([
      'Permission denied',
      '403 Forbidden',
      'Forbidden resource',
      'Access denied to this resource',
    ])('should classify "%s" as permission error', (errorMessage) => {
      expect(classifyError(errorMessage)).toBe('permission');
    });
  });

  describe('rate limit errors', () => {
    it.each([
      'Rate limit exceeded',
      '429 Too Many Requests',
      'Too many requests',
      'Quota exceeded',
    ])('should classify "%s" as rate_limit error', (errorMessage) => {
      expect(classifyError(errorMessage)).toBe('rate_limit');
    });
  });

  describe('conflict errors', () => {
    it.each([
      'Merge conflict detected',
      'Conflict in branch',
      'Rebase failed due to conflicts',
    ])('should classify "%s" as conflict error', (errorMessage) => {
      expect(classifyError(errorMessage)).toBe('conflict');
    });
  });

  describe('execution errors', () => {
    it.each([
      'Execution error in process',
      'Process failed',
      'Exception thrown',
    ])('should classify "%s" as execution error', (errorMessage) => {
      expect(classifyError(errorMessage)).toBe('execution');
    });
  });

  describe('unknown errors', () => {
    it('should return unknown for null/undefined', () => {
      expect(classifyError(null)).toBe('unknown');
      expect(classifyError(undefined)).toBe('unknown');
      expect(classifyError('')).toBe('unknown');
    });

    it('should return unknown for unrecognized errors', () => {
      expect(classifyError('Something unexpected happened')).toBe('unknown');
    });
  });
});

describe('getErrorDisplay', () => {
  it('should return correct display for network errors', () => {
    const display = getErrorDisplay('Connection timeout');
    expect(display.type).toBe('network');
    expect(display.title).toBe('Connection Error');
    expect(display.retryable).toBe(true);
    expect(display.actions).toHaveLength(1);
    expect(display.actions[0].type).toBe('retry');
  });

  it('should return correct display for auth errors', () => {
    const display = getErrorDisplay('Invalid API key');
    expect(display.type).toBe('auth');
    expect(display.title).toBe('Authentication Error');
    expect(display.retryable).toBe(false);
    expect(display.actions.some((a) => a.type === 'settings')).toBe(true);
    expect(display.actions.some((a) => a.type === 'switch_model')).toBe(true);
  });

  it('should return correct display for permission errors', () => {
    const display = getErrorDisplay('403 Forbidden');
    expect(display.type).toBe('permission');
    expect(display.title).toBe('Permission Error');
    expect(display.retryable).toBe(false);
    expect(display.actions.some((a) => a.href === '#settings-github')).toBe(true);
  });

  it('should return correct display for rate limit errors', () => {
    const display = getErrorDisplay('Rate limit exceeded');
    expect(display.type).toBe('rate_limit');
    expect(display.title).toBe('API Rate Limit Reached');
    expect(display.retryable).toBe(true);
    expect(display.actions.some((a) => a.type === 'retry_delayed')).toBe(true);
    expect(display.actions.find((a) => a.type === 'retry_delayed')?.delayMs).toBe(60000);
  });

  it('should return correct display for conflict errors', () => {
    const display = getErrorDisplay('Merge conflict');
    expect(display.type).toBe('conflict');
    expect(display.title).toBe('Conflict Error');
    expect(display.retryable).toBe(false);
    expect(display.actions.some((a) => a.type === 'view_logs')).toBe(true);
  });

  it('should return correct display for execution errors', () => {
    const display = getErrorDisplay('Script execution failed');
    expect(display.type).toBe('execution');
    expect(display.title).toBe('Execution Error');
    expect(display.retryable).toBe(true);
    expect(display.actions.some((a) => a.type === 'retry')).toBe(true);
  });

  it('should return correct display for unknown errors', () => {
    const display = getErrorDisplay(null);
    expect(display.type).toBe('unknown');
    expect(display.title).toBe('An error occurred');
    expect(display.retryable).toBe(true);
  });

  it('should preserve original error message for execution and unknown types', () => {
    const errorMessage = 'Custom error: something went wrong';
    const display = getErrorDisplay(errorMessage);
    expect(display.message).toBe(errorMessage);
  });
});
