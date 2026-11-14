import { fireEvent, render, screen, cleanup } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { AraProvider } from "@/components/ara/provider";
import { useAra } from "@/components/ara/context";
import { useAra as useSharedAra } from "@/components/ara/context";

afterEach(cleanup);

function Consumer() {
  const session = useAra();
  const shared = useSharedAra();
  return (
    <>
      <output>{session.year}</output>
      <output>{String(session === shared)}</output>
      <button onClick={() => session.setYear(2026)}>Change year</button>
    </>
  );
}

describe("ARA shared session", () => {
  it("shares the same context between the provider and both consumer imports", () => {
    render(
      <AraProvider>
        <Consumer />
      </AraProvider>,
    );
    expect(screen.getByText("2025")).toBeInTheDocument();
    expect(screen.getByText("true")).toBeInTheDocument();
  });

  it("retains session values when the workspace rerenders", () => {
    const view = render(
      <AraProvider>
        <Consumer />
      </AraProvider>,
    );
    fireEvent.click(screen.getByText("Change year"));
    view.rerender(
      <AraProvider>
        <Consumer />
      </AraProvider>,
    );
    expect(screen.getByText("2026")).toBeInTheDocument();
  });
});
