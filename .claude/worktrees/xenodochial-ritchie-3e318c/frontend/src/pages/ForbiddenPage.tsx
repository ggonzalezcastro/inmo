import { Link } from 'react-router-dom';

export default function ForbiddenPage() {
  return (
    <div className="min-h-screen bg-gray-100 flex items-center justify-center px-4">
      <div className="max-w-md w-full text-center">
        <h1 className="text-6xl font-bold text-gray-800">403</h1>
        <p className="mt-2 text-xl text-gray-600">Acceso denegado</p>
        <p className="mt-2 text-gray-500">
          No tienes permisos para acceder a esta página.
        </p>
        <div className="mt-8 flex justify-center gap-4">
          <Link
            to="/pipeline"
            className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 font-medium"
          >
            Ir al Pipeline
          </Link>
          <Link
            to="/dashboard"
            className="px-4 py-2 bg-gray-200 text-gray-800 rounded-md hover:bg-gray-300 font-medium"
          >
            Dashboard
          </Link>
        </div>
      </div>
    </div>
  );
}
