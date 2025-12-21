'use client';

import React from 'react';
import { Modal, ModalBody, ModalFooter } from './Modal';
import { Button } from './Button';
import {
  ExclamationTriangleIcon,
  InformationCircleIcon,
  TrashIcon,
} from '@heroicons/react/24/outline';

export type ConfirmVariant = 'danger' | 'warning' | 'info';

export interface ConfirmDialogProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => void;
  title: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  variant?: ConfirmVariant;
  isLoading?: boolean;
}

const variantConfig: Record<
  ConfirmVariant,
  {
    icon: React.ReactNode;
    iconBg: string;
    buttonVariant: 'danger' | 'primary';
  }
> = {
  danger: {
    icon: <TrashIcon className="h-6 w-6 text-red-400" />,
    iconBg: 'bg-red-500/10',
    buttonVariant: 'danger',
  },
  warning: {
    icon: <ExclamationTriangleIcon className="h-6 w-6 text-yellow-400" />,
    iconBg: 'bg-yellow-500/10',
    buttonVariant: 'primary',
  },
  info: {
    icon: <InformationCircleIcon className="h-6 w-6 text-blue-400" />,
    iconBg: 'bg-blue-500/10',
    buttonVariant: 'primary',
  },
};

export function ConfirmDialog({
  isOpen,
  onClose,
  onConfirm,
  title,
  message,
  confirmLabel = 'Confirm',
  cancelLabel = 'Cancel',
  variant = 'danger',
  isLoading = false,
}: ConfirmDialogProps) {
  const config = variantConfig[variant];

  const handleConfirm = () => {
    onConfirm();
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      size="sm"
      showCloseButton={false}
      closeOnOverlayClick={!isLoading}
      closeOnEscape={!isLoading}
    >
      <ModalBody>
        <div className="flex flex-col items-center text-center">
          <div
            className={`p-3 rounded-full ${config.iconBg} mb-4`}
            aria-hidden="true"
          >
            {config.icon}
          </div>
          <h3 className="text-lg font-semibold text-gray-100 mb-2">{title}</h3>
          <p className="text-sm text-gray-400">{message}</p>
        </div>
      </ModalBody>
      <ModalFooter className="justify-center">
        <Button
          variant="secondary"
          onClick={onClose}
          disabled={isLoading}
        >
          {cancelLabel}
        </Button>
        <Button
          variant={config.buttonVariant}
          onClick={handleConfirm}
          isLoading={isLoading}
        >
          {confirmLabel}
        </Button>
      </ModalFooter>
    </Modal>
  );
}

// Hook for easier usage
import { useState, useCallback } from 'react';

interface UseConfirmDialogOptions {
  title: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  variant?: ConfirmVariant;
}

export function useConfirmDialog() {
  const [isOpen, setIsOpen] = useState(false);
  const [options, setOptions] = useState<UseConfirmDialogOptions | null>(null);
  const [resolveRef, setResolveRef] = useState<((value: boolean) => void) | null>(null);

  const confirm = useCallback((opts: UseConfirmDialogOptions): Promise<boolean> => {
    setOptions(opts);
    setIsOpen(true);
    return new Promise((resolve) => {
      setResolveRef(() => resolve);
    });
  }, []);

  const handleClose = useCallback(() => {
    setIsOpen(false);
    resolveRef?.(false);
    setResolveRef(null);
  }, [resolveRef]);

  const handleConfirm = useCallback(() => {
    setIsOpen(false);
    resolveRef?.(true);
    setResolveRef(null);
  }, [resolveRef]);

  const ConfirmDialogComponent = options ? (
    <ConfirmDialog
      isOpen={isOpen}
      onClose={handleClose}
      onConfirm={handleConfirm}
      title={options.title}
      message={options.message}
      confirmLabel={options.confirmLabel}
      cancelLabel={options.cancelLabel}
      variant={options.variant}
    />
  ) : null;

  return { confirm, ConfirmDialog: ConfirmDialogComponent };
}
