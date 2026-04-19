/**
 * Shared validation helpers.
 */

export function required(value, fieldName = 'Campo') {
  if (value == null || String(value).trim() === '') {
    return `${fieldName} es requerido`;
  }
  return null;
}

export function email(value) {
  if (!value) return null;
  const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  return re.test(value) ? null : 'Email no válido';
}

export function minLength(value, min, fieldName = 'Campo') {
  if (!value) return null;
  return value.length < min ? `${fieldName} debe tener al menos ${min} caracteres` : null;
}

export function maxLength(value, max, fieldName = 'Campo') {
  if (!value) return null;
  return value.length > max ? `${fieldName} no debe superar ${max} caracteres` : null;
}

export function passwordStrength(value) {
  if (!value) return null;
  if (value.length < 8) return 'La contraseña debe tener al menos 8 caracteres';
  if (!/[A-Z]/.test(value)) return 'Debe incluir al menos una mayúscula';
  if (!/[a-z]/.test(value)) return 'Debe incluir al menos una minúscula';
  if (!/[0-9]/.test(value)) return 'Debe incluir al menos un número';
  return null;
}
