import { cn } from "@/lib/utils"
import type { HTMLAttributes } from "react"

const variants = {
  default: "bg-primary/10 text-primary border-primary/20",
  success: "bg-green-500/10 text-green-400 border-green-500/20",
  warning: "bg-yellow-500/10 text-yellow-400 border-yellow-500/20",
  danger: "bg-red-500/10 text-red-400 border-red-500/20",
  outline: "bg-transparent text-muted-foreground border-border",
} as const

interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  variant?: keyof typeof variants
}

export function Badge({ className, variant = "default", ...props }: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold transition-colors",
        variants[variant], className,
      )}
      {...props}
    />
  )
}
