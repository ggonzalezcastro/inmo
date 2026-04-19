// ⚠️  These re-exports point to the legacy .js versions.
// TODO: rename this file to index.ts and migrate each hook to TypeScript.
// useDebounce, usePagination, and usePermissions already have .ts versions — import them directly.
export { useFormValidation } from './useFormValidation';
export { useModal } from './useModal';
export { useFilters } from './useFilters';
// usePagination — prefer importing from './usePagination' (the .ts version) directly
export { usePagination } from './usePagination.js';
