import { Link, useLocation } from "wouter";
import { Activity, Search, Brain, FlaskConical, BarChart3 } from "lucide-react";

const navItems = [
  { href: "/", label: "Pipeline Runs", icon: Activity },
  { href: "/ml", label: "ML Analysis", icon: BarChart3 },
  { href: "/knowledge", label: "Knowledge Store", icon: Brain },
];

export default function Layout({ children }: { children: React.ReactNode }) {
  const [location] = useLocation();

  const isActive = (href: string) => {
    if (href === "/") return location === "/";
    return location.startsWith(href);
  };

  const getPageContext = () => {
    if (location.startsWith("/investigations/")) return { icon: FlaskConical, label: "Investigation Detail" };
    if (location.match(/^\/ml\/[^/]+/)) return { icon: BarChart3, label: "ML Run Detail" };
    return null;
  };

  const pageContext = getPageContext();

  return (
    <div className="min-h-screen bg-background flex flex-col" data-testid="layout-root">
      <header className="border-b border-border bg-card/50 backdrop-blur-sm sticky top-0 z-50">
        <div className="max-w-[1400px] mx-auto px-6 h-14 flex items-center gap-8">
          <Link href="/" className="flex items-center gap-2.5 shrink-0" data-testid="link-home">
            <div className="w-8 h-8 rounded-lg bg-primary flex items-center justify-center">
              <Search className="w-4 h-4 text-primary-foreground" />
            </div>
            <span className="font-semibold text-[15px] tracking-tight">Pipeline Dashboard</span>
          </Link>

          <nav className="flex items-center gap-1" data-testid="nav-main">
            {navItems.map((item) => {
              const Icon = item.icon;
              const active = isActive(item.href);
              return (
                <Link key={item.href} href={item.href} data-testid={`nav-${item.label.toLowerCase().replace(/\s+/g, "-")}`}>
                  <span
                    className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-md text-sm font-medium transition-colors cursor-pointer ${
                      active
                        ? "bg-primary/10 text-primary"
                        : "text-muted-foreground hover:text-foreground hover:bg-muted/50"
                    }`}
                  >
                    <Icon className="w-4 h-4" />
                    {item.label}
                  </span>
                </Link>
              );
            })}
            {pageContext && (
              <span className="inline-flex items-center gap-2 px-3 py-1.5 rounded-md text-sm font-medium bg-primary/10 text-primary">
                <pageContext.icon className="w-4 h-4" />
                {pageContext.label}
              </span>
            )}
          </nav>

          <div className="ml-auto flex items-center gap-3">
            <span className="text-xs text-muted-foreground font-mono">v1.0 POC</span>
          </div>
        </div>
      </header>

      <main className="flex-1">
        <div className="max-w-[1400px] mx-auto px-6 py-6">
          {children}
        </div>
      </main>
    </div>
  );
}
