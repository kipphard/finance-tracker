import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { AccountOut } from "../api/types";
import { ReconcileModal } from "./ReconcileModal";

// vi.hoisted so the spies exist before vi.mock's hoisted factory runs.
const { apiGet, apiPost } = vi.hoisted(() => ({ apiGet: vi.fn(), apiPost: vi.fn() }));
vi.mock("../api/client", () => ({ apiGet, apiPost }));

// A discrepancy preview so the adjusting entry is non-zero (else "Book adjustment" stays disabled).
const PREVIEW = {
  account_id: "acc-1",
  as_of: "2026-06-25",
  computed_balance: "100",
  asserted_balance: "120",
  delta: "20",
  currency: "EUR",
};

beforeEach(() => {
  apiGet.mockResolvedValue([]); // reconcile history
  apiPost.mockImplementation((path: string) =>
    Promise.resolve(path.endsWith("/preview") ? PREVIEW : { ...PREVIEW, adjusted: true, transaction_id: "tx1" }),
  );
});
afterEach(() => {
  cleanup(); // manual since vitest globals are off
  vi.clearAllMocks();
});

const account = { id: "acc-1", name: "Giro", currency: "EUR", latest_balance: "100" } as AccountOut;

describe("ReconcileModal", () => {
  it("books an adjusting entry for the asserted balance", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    const onDone = vi.fn();
    render(<ReconcileModal account={account} onClose={onClose} onDone={onDone} />);

    // The "Real balance" number input → assert a value different from the computed balance.
    const balance = screen.getByRole("spinbutton");
    await user.clear(balance);
    await user.type(balance, "120");

    // Preview (mocked) flips the button enabled once the non-zero delta lands.
    const book = screen.getByRole("button", { name: "Book adjustment" });
    await waitFor(() => expect(book).toBeEnabled());

    await user.click(book);

    const today = new Date().toISOString().slice(0, 10);
    expect(apiPost).toHaveBeenCalledWith("/accounts/acc-1/reconcile", {
      asserted_balance: "120",
      as_of: today,
    });
    expect(onDone).toHaveBeenCalled();
  });
});
