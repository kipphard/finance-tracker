import { describe, expect, it } from "vitest";
import { num, titleCase } from "./format";

describe("num", () => {
  it("passes through finite numbers", () => {
    expect(num(42)).toBe(42);
    expect(num(-3.5)).toBe(-3.5);
  });
  it("parses numeric strings", () => expect(num("12.5")).toBe(12.5));
  it("treats null and undefined as 0", () => {
    expect(num(null)).toBe(0);
    expect(num(undefined)).toBe(0);
  });
  it("treats empty and non-numeric strings as 0", () => {
    expect(num("")).toBe(0);
    expect(num("abc")).toBe(0);
  });
  it("treats non-finite numbers as 0", () => {
    expect(num(Infinity)).toBe(0);
    expect(num(NaN)).toBe(0);
  });
});

describe("titleCase", () => {
  it("capitalizes a single word", () => expect(titleCase("checking")).toBe("Checking"));
  it("splits snake_case into spaced words", () => expect(titleCase("home_office")).toBe("Home Office"));
  it("capitalizes each space-separated word", () => expect(titleCase("two words")).toBe("Two Words"));
  it("handles the empty string", () => expect(titleCase("")).toBe(""));
});
