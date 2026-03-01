import { useState, useEffect } from 'react'
import { Plus, Trash2, UserCheck, UserX, Loader2 } from 'lucide-react'
import { toast } from 'sonner'
import { type ColumnDef } from '@tanstack/react-table'
import { Button } from '@/shared/components/ui/button'
import { Input } from '@/shared/components/ui/input'
import { Label } from '@/shared/components/ui/label'
import { Badge } from '@/shared/components/ui/badge'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/shared/components/ui/select'
import { PageHeader } from '@/shared/components/common/PageHeader'
import { DataTable } from '@/shared/components/common/DataTable'
import { ConfirmDialog } from '@/shared/components/common/ConfirmDialog'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/shared/components/ui/dialog'
import { getErrorMessage } from '@/shared/types/api'
import { cn, getInitials } from '@/shared/lib/utils'
import type { AuthUser } from '@/shared/types/auth'
import { usersService } from '../services/users.service'

export function UsersPage() {
  const [users, setUsers] = useState<AuthUser[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [showCreate, setShowCreate] = useState(false)
  const [deleteTarget, setDeleteTarget] = useState<AuthUser | null>(null)
  const [isDeleting, setIsDeleting] = useState(false)
  const [togglingId, setTogglingId] = useState<number | null>(null)

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [name, setName] = useState('')
  const [role, setRole] = useState<'admin' | 'agent'>('agent')
  const [creating, setCreating] = useState(false)

  const load = async () => {
    setIsLoading(true)
    try {
      const data = await usersService.getAll()
      setUsers(Array.isArray(data) ? data : [])
    } catch (error) {
      toast.error(getErrorMessage(error))
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    setCreating(true)
    try {
      const user = await usersService.create({ email, password, name: name || undefined, role })
      setUsers((prev) => [...prev, user])
      toast.success('Usuario creado')
      setShowCreate(false)
      setEmail('')
      setPassword('')
      setName('')
      setRole('agent')
    } catch (error) {
      toast.error(getErrorMessage(error))
    } finally {
      setCreating(false)
    }
  }

  const handleToggleActive = async (user: AuthUser) => {
    setTogglingId(user.id)
    try {
      const updated = await usersService.update(user.id, { is_active: !user.is_active })
      setUsers((prev) => prev.map((u) => (u.id === user.id ? updated : u)))
      toast.success(updated.is_active ? 'Usuario activado' : 'Usuario desactivado')
    } catch (error) {
      toast.error(getErrorMessage(error))
    } finally {
      setTogglingId(null)
    }
  }

  const handleDelete = async () => {
    if (!deleteTarget) return
    setIsDeleting(true)
    try {
      await usersService.delete(deleteTarget.id)
      setUsers((prev) => prev.filter((u) => u.id !== deleteTarget.id))
      toast.success('Usuario eliminado')
    } catch (error) {
      toast.error(getErrorMessage(error))
    } finally {
      setIsDeleting(false)
      setDeleteTarget(null)
    }
  }

  const columns: ColumnDef<AuthUser>[] = [
    {
      id: 'user',
      header: 'Usuario',
      cell: ({ row }) => {
        const u = row.original
        return (
          <div className="flex items-center gap-3">
            <div className={cn(
              'w-8 h-8 rounded-full flex items-center justify-center text-xs font-semibold shrink-0',
              u.is_active ? 'bg-primary/10 text-primary' : 'bg-muted text-muted-foreground'
            )}>
              {getInitials(u.name || u.email)}
            </div>
            <div>
              <p className="text-sm font-medium">{u.name || u.email}</p>
              <p className="text-xs text-muted-foreground">{u.email}</p>
            </div>
          </div>
        )
      },
    },
    {
      accessorKey: 'role',
      header: 'Rol',
      cell: ({ row }) => (
        <Badge variant={row.original.role === 'admin' ? 'default' : 'secondary'} className="capitalize">
          {row.original.role}
        </Badge>
      ),
    },
    {
      accessorKey: 'is_active',
      header: 'Estado',
      cell: ({ row }) => (
        <span className={cn(
          'inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium',
          row.original.is_active
            ? 'bg-emerald-100 text-emerald-700 border-emerald-200'
            : 'bg-slate-100 text-slate-600 border-slate-200'
        )}>
          {row.original.is_active ? 'Activo' : 'Inactivo'}
        </span>
      ),
    },
    {
      id: 'actions',
      header: '',
      cell: ({ row }) => {
        const u = row.original
        const loading = togglingId === u.id
        return (
          <div className="flex items-center gap-1">
            <Button
              variant="ghost"
              size="icon"
              className={cn('h-8 w-8', u.is_active ? 'text-amber-600 hover:text-amber-700' : 'text-emerald-600 hover:text-emerald-700')}
              onClick={() => handleToggleActive(u)}
              disabled={loading}
              title={u.is_active ? 'Desactivar' : 'Activar'}
              aria-label={u.is_active ? 'Desactivar usuario' : 'Activar usuario'}
            >
              {loading ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : u.is_active ? (
                <UserX className="h-4 w-4" />
              ) : (
                <UserCheck className="h-4 w-4" />
              )}
            </Button>
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8 text-destructive hover:text-destructive"
              aria-label="Eliminar usuario"
              onClick={() => setDeleteTarget(u)}
            >
              <Trash2 className="h-4 w-4" />
            </Button>
          </div>
        )
      },
    },
  ]

  return (
    <div className="p-8 space-y-6">
      <PageHeader
        title="Usuarios"
        description="Gestiona los agentes y administradores del equipo"
        actions={
          <Button size="sm" onClick={() => setShowCreate(true)}>
            <Plus className="mr-2 h-4 w-4" />
            Nuevo Usuario
          </Button>
        }
      />

      <DataTable
        columns={columns}
        data={users}
        isLoading={isLoading}
        total={users.length}
        emptyTitle="Sin usuarios"
        emptyDescription="Agrega agentes o administradores a tu equipo"
      />

      <Dialog open={showCreate} onOpenChange={setShowCreate}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Nuevo Usuario</DialogTitle>
          </DialogHeader>
          <form onSubmit={handleCreate} className="space-y-4">
            <div className="space-y-2">
              <Label>Nombre (opcional)</Label>
              <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="Juan Pérez" />
            </div>
            <div className="space-y-2">
              <Label>Email</Label>
              <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required placeholder="agente@empresa.cl" />
            </div>
            <div className="space-y-2">
              <Label>Contraseña</Label>
              <Input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required minLength={8} placeholder="Mínimo 8 caracteres" />
            </div>
            <div className="space-y-2">
              <Label>Rol</Label>
              <Select value={role} onValueChange={(v) => setRole(v as 'admin' | 'agent')}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="agent">Agente</SelectItem>
                  <SelectItem value="admin">Administrador</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <DialogFooter>
              <Button variant="outline" type="button" onClick={() => setShowCreate(false)}>Cancelar</Button>
              <Button type="submit" disabled={creating}>
                {creating && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                Crear Usuario
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      <ConfirmDialog
        open={!!deleteTarget}
        onOpenChange={(open) => !open && setDeleteTarget(null)}
        title="Eliminar usuario"
        description={`¿Eliminar a "${deleteTarget?.name || deleteTarget?.email}"? Esta acción es irreversible.`}
        confirmLabel="Eliminar"
        onConfirm={handleDelete}
        isLoading={isDeleting}
      />
    </div>
  )
}
