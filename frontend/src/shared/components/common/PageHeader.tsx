import { cn } from '@/shared/lib/utils'

interface PageHeaderProps {
  title: string
  description?: string
  actions?: React.ReactNode
  className?: string
}

export function PageHeader({ title, description, actions, className }: PageHeaderProps) {
  return (
    <div className={cn('mb-7', className)}>
      <div className="flex items-center justify-between gap-4">
        <div>
          <h1 className="text-[1.4375rem] font-bold text-foreground tracking-tight leading-tight">
            {title}
          </h1>
          {description && (
            <p className="text-[13px] text-muted-foreground mt-0.5">{description}</p>
          )}
        </div>
        {actions && (
          <div className="flex items-center gap-2 shrink-0">{actions}</div>
        )}
      </div>
      <div className="mt-4 h-px bg-border" />
    </div>
  )
}
