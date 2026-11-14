import { createFileRoute } from "@tanstack/react-router";
import { Plans } from "@/components/ara/plans";
export const Route = createFileRoute("/pricing")({
  head: () => ({
    meta: [
      { title: "ARATax plans — Free & Pro" },
      {
        name: "description",
        content: "Compare ARATax Free and the $12/month Pro tax assistant plan.",
      },
      { property: "og:title", content: "ARATax plans — Free & Pro" },
      { property: "og:description", content: "Choose the tax clarity you need with ARATax." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: Plans,
});
