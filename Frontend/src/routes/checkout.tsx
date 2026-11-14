import { createFileRoute } from "@tanstack/react-router";
import { Checkout } from "@/components/ara/plans";
export const Route = createFileRoute("/checkout")({
  head: () => ({
    meta: [
      { title: "ARATax Pro — Checkout" },
      { name: "description", content: "ARATax Pro subscription checkout and payment availability." },
      { property: "og:title", content: "ARATax Pro — Checkout" },
      { property: "og:description", content: "Your next step toward complete tax clarity." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: Checkout,
});
