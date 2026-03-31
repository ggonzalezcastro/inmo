import { cn } from '@/shared/lib/utils'

interface PageHeaderProps {
  title: string
  description?: string
  actions?: React.ReactNode
  className?: string
}

export function PageHeader({ title, description, actions, className }: PageHeaderProps) {
  return (
    <div className={cn('mb-5 sm:mb-7', className)}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-xl sm:text-[1.4375rem] font-bold text-foreground tracking-tight leading-tight">
            {title}
          </h1>
          {description && (
            <p className="text-[13px] text-muted-foreground mt-0.5">{description}</p>
          )}
        </div>
        {actions && (
          <div className="flex items-center gap-2 flex-wrap">{actions}</div>
        )}
      </div>
      <div className="mt-3 sm:mt-4 h-px bg-border" />
    </div>
  )
}
