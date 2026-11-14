import { act, cleanup, render } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { AraProvider } from "@/components/ara/provider";
import { useAra, type State } from "@/components/ara/context";

afterEach(cleanup);

function setup() {
  const ref: { current: State | null } = { current: null };
  function Probe() {
    ref.current = useAra();
    return null;
  }
  render(
    <AraProvider>
      <Probe />
    </AraProvider>,
  );
  const add = (label: string) =>
    act(() =>
      ref.current!.addEntry({
        source: "form",
        label,
        request: { residency: {} },
        response: { taxes: { net_tax_owed_or_refund: 1 } },
        language: "en",
      }),
    );
  return { ref, add };
}

describe("calculation history", () => {
  it("adds new entries to the top and activates them", () => {
    const { ref, add } = setup();
    add("first");
    add("second");
    expect(ref.current!.history.map((e) => e.label)).toEqual(["second", "first"]);
    expect(ref.current!.active?.label).toBe("second");
    expect(ref.current!.result).toEqual({ taxes: { net_tax_owed_or_refund: 1 } });
  });

  it("switches, updates and removes entries", () => {
    const { ref, add } = setup();
    add("first");
    add("second");
    const first = ref.current!.history[1]!;
    act(() => ref.current!.setActiveId(first.id));
    expect(ref.current!.active?.label).toBe("first");
    act(() => ref.current!.updateEntry(first.id, { language: "ru" }));
    expect(ref.current!.active?.language).toBe("ru");
    act(() => ref.current!.removeEntry(first.id));
    expect(ref.current!.history.map((e) => e.label)).toEqual(["second"]);
    expect(ref.current!.active?.label).toBe("second");
  });

  it("keeps at most 20 entries", () => {
    const { ref, add } = setup();
    for (let i = 0; i < 25; i++) add(`#${i}`);
    expect(ref.current!.history).toHaveLength(20);
    expect(ref.current!.history[0]!.label).toBe("#24");
  });
});
