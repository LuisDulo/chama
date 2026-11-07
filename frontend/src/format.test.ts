import { describe, expect, it } from "vitest";

import { messageFrom } from "./api";
import { can, describeContributions, money } from "./format";

describe("money", () => {
  it("shows two decimals and thousands separators", () => {
    expect(money("12500", "KES")).toBe("KES 12,500.00");
  });
});

describe("can", () => {
  it("checks the caller's permissions", () => {
    expect(can(["view_finances"], "view_finances")).toBe(true);
    expect(can([], "view_finances")).toBe(false);
    expect(can(undefined, "view_finances")).toBe(false);
  });
});

describe("describeContributions", () => {
  it("describes a fixed monthly rule", () => {
    const text = describeContributions(
      { amount_type: "fixed", minimum_amount: "1000.00", maximum_amount: "1000.00", frequency: "monthly", due_day: 5, grace_period_days: 3, late_penalty: "100.00" },
      "KES",
    );
    expect(text).toBe("KES 1,000.00 every month on day 5, 3 grace days, KES 100.00 late penalty");
  });

  it("describes a flexible weekly rule", () => {
    const text = describeContributions(
      { amount_type: "flexible", minimum_amount: "500", maximum_amount: "10000", frequency: "weekly", due_weekday: "friday", grace_period_days: 2, late_penalty: "50" },
      "KES",
    );
    expect(text).toContain("KES 500.00 to KES 10,000.00 every week on Friday");
  });
});

describe("messageFrom", () => {
  it("reads every shape of DRF error", () => {
    expect(messageFrom({ detail: "Not allowed" })).toBe("Not allowed");
    expect(messageFrom({ amount: ["Too small"] })).toBe("Too small");
    expect(messageFrom(["This chama is full"])).toBe("This chama is full");
    expect(messageFrom({ non_field_errors: ["Give an email"] })).toBe("Give an email");
    expect(messageFrom(null)).toBe("Something went wrong. Please try again.");
  });
});
