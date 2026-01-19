import { describe, it, expect, vi } from 'vitest';
import { render, fireEvent, screen } from '@testing-library/react';
import { useRef, useState } from 'react';
import { useClickOutside, useClickOutsideMultiple } from '../useClickOutside';

// Test component for useClickOutside
function TestComponent({ onClickOutside }: { onClickOutside: () => void }) {
  const ref = useRef<HTMLDivElement>(null);
  const [enabled, setEnabled] = useState(true);

  useClickOutside(ref, onClickOutside, enabled);

  return (
    <div>
      <div ref={ref} data-testid="inside">Inside element</div>
      <div data-testid="outside">Outside element</div>
      <button
        data-testid="toggle"
        onClick={() => setEnabled((prev) => !prev)}
      >
        Toggle
      </button>
    </div>
  );
}

// Test component for useClickOutsideMultiple
function TestMultipleComponent({ onClickOutside }: { onClickOutside: () => void }) {
  const ref1 = useRef<HTMLDivElement>(null);
  const ref2 = useRef<HTMLDivElement>(null);

  useClickOutsideMultiple([ref1, ref2], onClickOutside);

  return (
    <div>
      <div ref={ref1} data-testid="inside1">Inside element 1</div>
      <div ref={ref2} data-testid="inside2">Inside element 2</div>
      <div data-testid="outside">Outside element</div>
    </div>
  );
}

describe('useClickOutside', () => {
  it('should call onClickOutside when clicking outside the element', () => {
    const handleClickOutside = vi.fn();
    render(<TestComponent onClickOutside={handleClickOutside} />);

    fireEvent.mouseDown(screen.getByTestId('outside'));

    expect(handleClickOutside).toHaveBeenCalledTimes(1);
  });

  it('should not call onClickOutside when clicking inside the element', () => {
    const handleClickOutside = vi.fn();
    render(<TestComponent onClickOutside={handleClickOutside} />);

    fireEvent.mouseDown(screen.getByTestId('inside'));

    expect(handleClickOutside).not.toHaveBeenCalled();
  });

  it('should not call onClickOutside when disabled', () => {
    const handleClickOutside = vi.fn();
    render(<TestComponent onClickOutside={handleClickOutside} />);

    // Disable the hook
    fireEvent.click(screen.getByTestId('toggle'));

    // Now click outside
    fireEvent.mouseDown(screen.getByTestId('outside'));

    expect(handleClickOutside).not.toHaveBeenCalled();
  });

  it('should re-enable after toggling back', () => {
    const handleClickOutside = vi.fn();
    render(<TestComponent onClickOutside={handleClickOutside} />);

    // Disable then enable
    fireEvent.click(screen.getByTestId('toggle'));
    fireEvent.click(screen.getByTestId('toggle'));

    // Now click outside
    fireEvent.mouseDown(screen.getByTestId('outside'));

    expect(handleClickOutside).toHaveBeenCalledTimes(1);
  });
});

describe('useClickOutsideMultiple', () => {
  it('should call onClickOutside when clicking outside all elements', () => {
    const handleClickOutside = vi.fn();
    render(<TestMultipleComponent onClickOutside={handleClickOutside} />);

    fireEvent.mouseDown(screen.getByTestId('outside'));

    expect(handleClickOutside).toHaveBeenCalledTimes(1);
  });

  it('should not call onClickOutside when clicking inside first element', () => {
    const handleClickOutside = vi.fn();
    render(<TestMultipleComponent onClickOutside={handleClickOutside} />);

    fireEvent.mouseDown(screen.getByTestId('inside1'));

    expect(handleClickOutside).not.toHaveBeenCalled();
  });

  it('should not call onClickOutside when clicking inside second element', () => {
    const handleClickOutside = vi.fn();
    render(<TestMultipleComponent onClickOutside={handleClickOutside} />);

    fireEvent.mouseDown(screen.getByTestId('inside2'));

    expect(handleClickOutside).not.toHaveBeenCalled();
  });
});
