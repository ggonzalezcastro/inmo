import { useState, useCallback } from 'react';

/**
 * Hook for form validation state and helpers.
 * @param {Object} initialErrors - Initial errors object { fieldName: message }
 * @returns {[Object, function, function]} [errors, setFieldError, validate]
 * - errors: { [field]: message }
 * - setFieldError: (field, message) => void
 * - validate: (values, rules) => boolean - runs rules, sets errors, returns true if valid
 */
export function useFormValidation(initialErrors = {}) {
  const [errors, setErrors] = useState(initialErrors);

  const setFieldError = useCallback((field, message) => {
    setErrors((prev) => (message ? { ...prev, [field]: message } : { ...prev, [field]: undefined }));
  }, []);

  const validate = useCallback((values, rules) => {
    const next = {};
    let valid = true;
    for (const [field, rule] of Object.entries(rules)) {
      const message = rule(values[field], values);
      if (message) {
        next[field] = message;
        valid = false;
      }
    }
    setErrors(next);
    return valid;
  }, []);

  const clearErrors = useCallback(() => setErrors({}), []);

  return { errors, setErrors, setFieldError, validate, clearErrors };
}

export default useFormValidation;
