import { createFileRoute } from "@tanstack/react-router";
import { PaymentSuccess } from "@/components/ara/plans";
export const Route = createFileRoute("/success")({
  head: () => ({
    meta: [
      { title: "ARATax — Payment status" },
      {
        name: "description",
        content: "Check your ARATax Pro payment status and return to your calculation.",
      },
      { property: "og:title", content: "ARATax — Payment status" },
      { property: "og:description", content: "Return to your ARATax tax workspace." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: PaymentSuccess,
});
