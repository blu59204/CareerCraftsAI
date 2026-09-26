import Link from "next/link";
import { ChevronRight } from "lucide-react";
import { JsonLd } from "@/components/seo/JsonLd";

const SITE_URL = "https://careercraftsai.me";

interface Crumb {
  name: string;
  href: string;
}

/** Home is implicit — pass only the trail after it, e.g. [{ name: "Pricing", href: "/pricing" }]. */
export function Breadcrumbs({ trail }: { trail: Crumb[] }) {
  const items = [{ name: "Home", href: "/" }, ...trail];

  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: items.map((item, index) => ({
      "@type": "ListItem",
      position: index + 1,
      name: item.name,
      item: `${SITE_URL}${item.href}`,
    })),
  };

  return (
    <>
      <JsonLd data={jsonLd} />
      <nav aria-label="Breadcrumb" className="mb-6 flex items-center gap-1.5 text-sm text-muted-foreground">
        {items.map((item, index) => {
          const isLast = index === items.length - 1;
          return (
            <span key={item.href} className="flex items-center gap-1.5">
              {index > 0 && <ChevronRight className="h-3.5 w-3.5" />}
              {isLast ? (
                <span className="text-foreground">{item.name}</span>
              ) : (
                <Link href={item.href} className="hover:text-foreground hover:underline">
                  {item.name}
                </Link>
              )}
            </span>
          );
        })}
      </nav>
    </>
  );
}
