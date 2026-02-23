import React from 'react';

const ALERT_STYLES = {
  info: 'bg-blue-50 border-blue-400 text-blue-700',
  success: 'bg-green-50 border-green-400 text-green-700',
  warning: 'bg-yellow-50 border-yellow-400 text-yellow-800',
  error: 'bg-red-50 border-red-400 text-red-700',
};

/**
 * Alert block for info, success, warning, error.
 * @param {string} variant - info | success | warning | error
 * @param {React.ReactNode} children - Content
 * @param {string} className
 */
export function Alert({ variant = 'info', children, className = '' }) {
  const style = ALERT_STYLES[variant] || ALERT_STYLES.info;

  return (
    <div
      className={`border-l-4 p-4 text-sm ${style} ${className}`}
      role="alert"
    >
      {children}
    </div>
  );
}

export default Alert;
