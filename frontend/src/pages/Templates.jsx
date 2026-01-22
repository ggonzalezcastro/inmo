import NavBar from '../components/NavBar';
import TemplateManager from '../components/TemplateManager';

/**
 * Templates Page - Manage message templates
 */
export default function Templates() {
  return (
    <div className="min-h-screen bg-gray-100">
      <NavBar />

      {/* Main Content */}
      <main className="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
        <TemplateManager />
      </main>
    </div>
  );
}

