import { createFileRoute } from "@tanstack/react-router";
import { motion, useReducedMotion } from "framer-motion";
import { useAra } from "@/components/ara/context";
import { Calculation } from "@/components/ara/calculation";
import { Results } from "@/components/ara/results";
import { Documents } from "@/components/ara/documents";
import { Chat } from "@/components/ara/chat";
export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "ARATax: taxes for freelancers and visa holders" },
      {
        name: "description",
        content:
          "ARATax helps US freelancers and immigrants on work visas find their tax residency status, the right IRS form, deductions and refunds.",
      },
      { property: "og:title", content: "ARATax: taxes for freelancers and visa holders" },
      {
        property: "og:description",
        content:
          "ARATax helps US freelancers and immigrants on work visas find their tax residency status, the right IRS form, deductions and refunds.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: Index,
});
function Index() {
  const a = useAra();
  const reduced = useReducedMotion();
  return (
    <motion.div
      key={a.section}
      initial={reduced ? false : { opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
    >
      {a.section === "new" ? (
        <Calculation />
      ) : a.section === "chat" ? (
        <Chat />
      ) : a.section === "results" ? (
        <Results />
      ) : (
        <Documents />
      )}
    </motion.div>
  );
}
