import { ArrowLeft, CheckCircle2, LifeBuoy, ShieldCheck } from 'lucide-react'
import { Link, useLocation, useSearchParams } from 'react-router-dom'

type Section = { title: string; paragraphs: string[]; bullets?: string[] }

const pages: Record<string, { eyebrow: string; title: string; intro: string; sections: Section[] }> = {
  '/privacy': {
    eyebrow: 'Privacidad',
    title: 'Política de privacidad',
    intro: 'Explica cómo Captame.cl trata información cuando una inmobiliaria usa el CRM y conecta canales profesionales de Meta.',
    sections: [
      { title: 'Quién decide el uso de los datos', paragraphs: ['La inmobiliaria o broker que contrata Captame.cl determina las finalidades comerciales y la atención de sus leads. Captame.cl procesa esa información para prestar el servicio contratado.'] },
      { title: 'Información que se procesa', paragraphs: ['Podemos procesar datos de cuenta, información entregada por leads, mensajes profesionales, archivos, datos de campañas, formularios y resultados comerciales ingresados al CRM.'], bullets: ['No se conectan perfiles personales de Facebook ni cuentas personales de Instagram.', 'Los tokens de Meta se almacenan cifrados y no se muestran en la interfaz.', 'Jefatura puede supervisar las conversaciones corporativas de su organización.'] },
      { title: 'Finalidades', paragraphs: ['La información se usa para administrar leads, atender conversaciones, asignar ejecutivos, crear tareas, generar asistencia de IA revisable y medir campañas con resultados del CRM. Los datos comerciales solo se envían a Meta mediante Conversions API si la función fue habilitada y existe una base autorizada.'] },
      { title: 'Conservación y seguridad', paragraphs: ['Los eventos técnicos brutos de Meta tienen una retención operativa máxima de siete días. El historial normalizado sigue la política contractual del broker. Aplicamos separación por organización, cifrado de credenciales, permisos por rol y auditoría de acciones sensibles.'] },
      { title: 'Derechos y solicitudes', paragraphs: ['Las personas pueden pedir acceso, rectificación o eliminación contactando al broker que las atiende. Las solicitudes relacionadas con una conexión Meta también pueden gestionarse desde la página de eliminación de datos.'] },
    ],
  },
  '/terms': {
    eyebrow: 'Condiciones',
    title: 'Términos de uso',
    intro: 'Reglas generales para utilizar Captame.cl y sus integraciones profesionales con Meta.',
    sections: [
      { title: 'Uso autorizado', paragraphs: ['El servicio está destinado a organizaciones y usuarios autorizados. Cada usuario debe proteger su cuenta y utilizar únicamente activos empresariales o profesionales sobre los que tenga permisos válidos.'] },
      { title: 'Mensajería', paragraphs: ['Los mensajes deben respetar el consentimiento, las ventanas de atención, las plantillas aprobadas y las políticas aplicables de WhatsApp, Instagram y Messenger. Captame.cl puede bloquear envíos cuando falten permisos o exista un conflicto de asignación.'] },
      { title: 'Publicidad', paragraphs: ['Los borradores de anuncios inmobiliarios usan la categoría especial Housing. Solo jefatura puede aprobar, publicar y activar gasto. Toda campaña se publica pausada y requiere una confirmación independiente antes de consumir presupuesto.'] },
      { title: 'Inteligencia artificial', paragraphs: ['Los resúmenes, borradores y sugerencias de tareas son asistencia. El usuario debe revisar el contenido antes de enviarlo o convertirlo en una acción. La IA no activa campañas publicitarias ni presupuesto.'] },
      { title: 'Disponibilidad y cambios', paragraphs: ['Las funciones de Meta dependen de permisos, revisión de la aplicación y disponibilidad de servicios externos. Podemos actualizar estas condiciones cuando cambie el producto o la regulación, informando la fecha de la versión publicada.'] },
    ],
  },
  '/support': {
    eyebrow: 'Ayuda',
    title: 'Soporte de Captame.cl',
    intro: 'Ayuda para conexiones, permisos, mensajería y campañas de Meta.',
    sections: [
      { title: 'Si eres ejecutivo', paragraphs: ['Contacta a la jefatura de tu organización desde el canal interno acordado. Jefatura puede revisar el estado de la conexión, aprobar activos y resolver conflictos sin solicitarte contraseñas ni tokens.'] },
      { title: 'Si eres administrador', paragraphs: ['Revisa “Mis canales” para identificar permisos vencidos, activos pausados o sincronizaciones fallidas. Al solicitar soporte incluye el nombre del broker, canal y hora aproximada del problema; nunca envíes tokens o secretos.'] },
      { title: 'Desconexión y eliminación', paragraphs: ['Puedes desconectar una cuenta desde “Mis canales”. Para una solicitud de eliminación originada en Meta, utiliza la página pública de eliminación de datos.'] },
    ],
  },
  '/data-deletion': {
    eyebrow: 'Privacidad',
    title: 'Eliminación de datos de Meta',
    intro: 'Aquí puedes conocer el resultado de una solicitud o iniciar la desconexión de una cuenta profesional.',
    sections: [
      { title: 'Solicitud desde Meta', paragraphs: ['Si eliminaste Captame.cl desde la configuración de Meta, Meta enviará una solicitud firmada. La integración y sus credenciales se eliminan de Captame.cl; el historial comercial que deba conservar el broker se mantiene sin la conexión activa.'] },
      { title: 'Solicitud directa', paragraphs: ['Si aún tienes acceso, entra a “Mis canales” y desconecta la cuenta correspondiente. Si no puedes ingresar, solicita al administrador de tu broker que gestione la desconexión y la eliminación asociada.'] },
      { title: 'Qué ocurre después', paragraphs: ['Los activos dejan de enviar y recibir, las credenciales quedan revocadas o eliminadas y las automatizaciones se bloquean. Los mensajes históricos no se vuelven a enviar a Meta.'] },
    ],
  },
}

export function LegalPage() {
  const location = useLocation()
  const [params] = useSearchParams()
  const page = pages[location.pathname] || pages['/privacy']
  const confirmationCode = location.pathname === '/data-deletion' ? params.get('code') : null

  return (
    <div className="min-h-screen bg-[#F4F7FB] text-slate-900">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-5 py-4">
          <Link to="/login" className="flex items-center gap-2 text-sm font-bold tracking-tight text-slate-900"><span className="flex h-8 w-8 items-center justify-center rounded-xl bg-[#1A56DB] text-xs text-white">C</span> Captame.cl</Link>
          <nav className="hidden items-center gap-5 text-xs font-semibold text-slate-500 sm:flex"><Link className="hover:text-[#1A56DB]" to="/privacy">Privacidad</Link><Link className="hover:text-[#1A56DB]" to="/terms">Términos</Link><Link className="hover:text-[#1A56DB]" to="/support">Soporte</Link></nav>
        </div>
      </header>
      <main className="mx-auto max-w-5xl px-5 py-10 sm:py-16">
        <div className="grid gap-8 lg:grid-cols-[1fr_270px]">
          <article className="rounded-3xl border border-slate-200 bg-white p-6 shadow-[0_16px_50px_rgba(15,23,42,0.06)] sm:p-10">
            <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-[#1A56DB]">{page.eyebrow}</p>
            <h1 className="mt-3 text-3xl font-bold tracking-tight sm:text-4xl">{page.title}</h1>
            <p className="mt-4 max-w-2xl text-sm leading-7 text-slate-600">{page.intro}</p>
            {confirmationCode && <div className="mt-7 rounded-2xl border border-emerald-200 bg-emerald-50 p-4"><p className="flex items-center gap-2 text-sm font-bold text-emerald-900"><CheckCircle2 className="h-5 w-5" /> Solicitud procesada</p><p className="mt-1 text-xs leading-5 text-emerald-800">Código de confirmación: <span className="font-mono font-bold">{confirmationCode}</span></p></div>}
            <div className="mt-9 space-y-9">{page.sections.map((section) => <section key={section.title}><h2 className="text-lg font-bold tracking-tight">{section.title}</h2>{section.paragraphs.map((paragraph) => <p key={paragraph} className="mt-2 text-sm leading-7 text-slate-600">{paragraph}</p>)}{section.bullets && <ul className="mt-3 space-y-2">{section.bullets.map((bullet) => <li key={bullet} className="flex gap-2 text-sm leading-6 text-slate-600"><CheckCircle2 className="mt-1 h-4 w-4 shrink-0 text-emerald-600" />{bullet}</li>)}</ul>}</section>)}</div>
            <p className="mt-10 border-t border-slate-100 pt-5 text-[11px] text-slate-400">Última actualización: 1 de septiembre de 2026. Este documento debe ser revisado por el responsable legal antes de publicar la integración en producción.</p>
          </article>
          <aside className="space-y-4">
            <div className="rounded-2xl border border-blue-200 bg-blue-50 p-5"><ShieldCheck className="h-6 w-6 text-[#1A56DB]" /><p className="mt-3 text-sm font-bold text-blue-950">Integración profesional</p><p className="mt-1 text-xs leading-5 text-blue-800">Captame.cl admite activos empresariales de Meta y cuentas profesionales aprobadas.</p></div>
            <div className="rounded-2xl border border-slate-200 bg-white p-5"><LifeBuoy className="h-6 w-6 text-slate-500" /><p className="mt-3 text-sm font-bold">¿Necesitas ayuda?</p><Link to="/support" className="mt-3 inline-flex items-center gap-1.5 text-xs font-bold text-[#1A56DB] hover:underline">Ir a soporte <ArrowLeft className="h-3.5 w-3.5 rotate-180" /></Link></div>
          </aside>
        </div>
      </main>
    </div>
  )
}
