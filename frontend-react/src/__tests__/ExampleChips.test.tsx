import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { ExampleChips } from "../components/shared/ExampleChips";

describe("ExampleChips", () => {
  it("renders example chips when no responses", () => {
    render(<ExampleChips />);
    expect(screen.getByText("TRY AN EXAMPLE")).toBeDefined();
  });
});
