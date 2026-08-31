import { cn } from "@/lib/utils";

export function SettingsSection({
  className,
  title,
  description,
  children,
}: {
  className?: string;
  title: React.ReactNode;
  description?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <section className={cn(className)}>
      <header className="space-y-2">
        <div className="type-body font-semibold">{title}</div>
        {description && (
          <div className="text-muted-foreground type-body">{description}</div>
        )}
      </header>
      <main className="mt-4">{children}</main>
    </section>
  );
}
