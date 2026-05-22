import { forwardRef, type InputHTMLAttributes } from "react"
import { cn } from "@/lib/utils"

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string
  error?: string
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ className, label, error, id, ...props }, ref) => (
    <div className="space-y-1.5">
      {label && (
        <label htmlFor={id} className="text-sm font-medium text-muted-foreground">
          {label}
        </label>
      )}
      <input
        ref={ref}
        id={id}
        className={cn(
          "flex h-10 w-full rounded-lg border border-border bg-secondary px-3 py-2 text-sm",
          "placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/50",
          "disabled:cursor-not-allowed disabled:opacity-50 transition-all",
          error && "border-destructive focus:ring-destructive/50",
          className,
        )}
        {...props}
      />
      {error && <p className="text-xs text-destructive">{error}</p>}
    </div>
  ),
)
Input.displayName = "Input"
