'use client';

import {
  createContext,
  useContext,
  useState,
  useRef,
  useEffect,
  useCallback,
  type ReactNode,
  type KeyboardEvent,
} from 'react';
import { cn } from '@/lib/utils';

// Context for menu state
interface MenuContextValue {
  isOpen: boolean;
  setIsOpen: (open: boolean) => void;
  activeIndex: number;
  setActiveIndex: (index: number) => void;
  itemCount: number;
  registerItem: () => number;
  buttonRef: React.RefObject<HTMLButtonElement | null>;
}

const MenuContext = createContext<MenuContextValue | null>(null);

function useMenu() {
  const context = useContext(MenuContext);
  if (!context) {
    throw new Error('Menu components must be used within a Menu');
  }
  return context;
}

// Menu Root
interface MenuProps {
  children: ReactNode;
}

export function Menu({ children }: MenuProps) {
  const [isOpen, setIsOpenState] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);
  const [itemCount, setItemCount] = useState(0);
  const buttonRef = useRef<HTMLButtonElement | null>(null);
  const itemCountRef = useRef(0);

  // Wrap setIsOpen to reset activeIndex when closing
  const setIsOpen = useCallback((open: boolean) => {
    setIsOpenState(open);
    if (!open) {
      setActiveIndex(-1);
    }
  }, []);

  // Reset item count on each render
  useEffect(() => {
    itemCountRef.current = 0;
  });

  const registerItem = useCallback(() => {
    const index = itemCountRef.current;
    itemCountRef.current += 1;
    setItemCount(itemCountRef.current);
    return index;
  }, []);

  return (
    <MenuContext.Provider
      value={{
        isOpen,
        setIsOpen,
        activeIndex,
        setActiveIndex,
        itemCount,
        registerItem,
        buttonRef,
      }}
    >
      <div className="relative inline-block">{children}</div>
    </MenuContext.Provider>
  );
}

// Menu Button (Trigger)
interface MenuButtonProps {
  children: ReactNode;
  className?: string;
  'aria-label'?: string;
}

export function MenuButton({ children, className, 'aria-label': ariaLabel }: MenuButtonProps) {
  const { isOpen, setIsOpen, setActiveIndex, itemCount, buttonRef } = useMenu();

  const handleKeyDown = (e: KeyboardEvent) => {
    switch (e.key) {
      case 'Enter':
      case ' ':
      case 'ArrowDown':
        e.preventDefault();
        setIsOpen(true);
        setActiveIndex(0);
        break;
      case 'ArrowUp':
        e.preventDefault();
        setIsOpen(true);
        setActiveIndex(itemCount - 1);
        break;
    }
  };

  return (
    <button
      ref={buttonRef}
      type="button"
      className={className}
      onClick={() => setIsOpen(!isOpen)}
      onKeyDown={handleKeyDown}
      aria-expanded={isOpen}
      aria-haspopup="menu"
      aria-label={ariaLabel}
    >
      {children}
    </button>
  );
}

// Menu Items (Container)
interface MenuItemsProps {
  children: ReactNode;
  className?: string;
  align?: 'left' | 'right';
}

export function MenuItems({ children, className, align = 'left' }: MenuItemsProps) {
  const { isOpen, setIsOpen, activeIndex, setActiveIndex, itemCount, buttonRef } = useMenu();
  const menuRef = useRef<HTMLDivElement>(null);

  // Handle keyboard navigation
  const handleKeyDown = (e: KeyboardEvent) => {
    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault();
        setActiveIndex((activeIndex + 1) % itemCount);
        break;
      case 'ArrowUp':
        e.preventDefault();
        setActiveIndex((activeIndex - 1 + itemCount) % itemCount);
        break;
      case 'Home':
        e.preventDefault();
        setActiveIndex(0);
        break;
      case 'End':
        e.preventDefault();
        setActiveIndex(itemCount - 1);
        break;
      case 'Escape':
        e.preventDefault();
        setIsOpen(false);
        buttonRef.current?.focus();
        break;
      case 'Tab':
        setIsOpen(false);
        break;
    }
  };

  // Close on click outside
  useEffect(() => {
    if (!isOpen) return;

    const handleClickOutside = (e: MouseEvent) => {
      if (
        menuRef.current &&
        !menuRef.current.contains(e.target as Node) &&
        buttonRef.current &&
        !buttonRef.current.contains(e.target as Node)
      ) {
        setIsOpen(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [isOpen, setIsOpen, buttonRef]);

  // Focus menu when opened
  useEffect(() => {
    if (isOpen && menuRef.current) {
      menuRef.current.focus();
    }
  }, [isOpen]);

  if (!isOpen) return null;

  return (
    <div
      ref={menuRef}
      role="menu"
      tabIndex={-1}
      onKeyDown={handleKeyDown}
      className={cn(
        'absolute z-50 mt-1 min-w-[160px] py-1',
        'bg-gray-800 border border-gray-700 rounded-lg shadow-lg',
        'focus:outline-none',
        'animate-in fade-in zoom-in-95 duration-150',
        align === 'right' ? 'right-0' : 'left-0',
        className
      )}
    >
      {children}
    </div>
  );
}

// Menu Item
interface MenuItemProps {
  children: ReactNode;
  onClick?: () => void;
  disabled?: boolean;
  className?: string;
  icon?: ReactNode;
}

export function MenuItem({ children, onClick, disabled, className, icon }: MenuItemProps) {
  const { activeIndex, setIsOpen, buttonRef, registerItem } = useMenu();
  const itemRef = useRef<HTMLButtonElement>(null);
  const [itemIndex, setItemIndex] = useState<number>(-1);

  // Register this item and get its index - intentional for menu item tracking
  useEffect(() => {
    const index = registerItem();
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setItemIndex(index);
  }, [registerItem]);

  const isActive = activeIndex === itemIndex && itemIndex >= 0;

  // Focus when active
  useEffect(() => {
    if (isActive && itemRef.current) {
      itemRef.current.focus();
    }
  }, [isActive]);

  const handleClick = () => {
    if (disabled) return;
    onClick?.();
    setIsOpen(false);
    buttonRef.current?.focus();
  };

  const handleKeyDown = (e: KeyboardEvent) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      handleClick();
    }
  };

  return (
    <button
      ref={itemRef}
      role="menuitem"
      type="button"
      onClick={handleClick}
      onKeyDown={handleKeyDown}
      disabled={disabled}
      tabIndex={isActive ? 0 : -1}
      className={cn(
        'w-full px-3 py-2 text-left text-sm',
        'flex items-center gap-2',
        'transition-colors focus:outline-none',
        isActive && !disabled && 'bg-gray-700 text-gray-100',
        !isActive && !disabled && 'text-gray-300 hover:bg-gray-700/50',
        disabled && 'text-gray-500 cursor-not-allowed',
        className
      )}
    >
      {icon && <span className="flex-shrink-0 w-4 h-4">{icon}</span>}
      {children}
    </button>
  );
}

// Menu Divider
export function MenuDivider() {
  return <div className="my-1 border-t border-gray-700" role="separator" />;
}

// Menu Label (non-interactive)
interface MenuLabelProps {
  children: ReactNode;
  className?: string;
}

export function MenuLabel({ children, className }: MenuLabelProps) {
  return (
    <div
      className={cn('px-3 py-1.5 text-xs font-medium text-gray-500 uppercase', className)}
      role="presentation"
    >
      {children}
    </div>
  );
}
