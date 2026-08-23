import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../pages/ChatPage", () => ({ ChatPage: () => <div>Chat route</div> }));
vi.mock("../pages/CreditsPage", () => ({ CreditsPage: () => <div>Credits route</div> }));
vi.mock("../pages/ModelsPage", () => ({ ModelsPage: () => <div>Models route</div> }));
vi.mock("../pages/UsageInsightsPage", () => ({
  UsageInsightsPage: () => <div>Usage route</div>,
}));
vi.mock("../pages/PricingPage", () => ({ PricingPage: () => <div>Pricing route</div> }));
vi.mock("../pages/LandingPage", () => ({ LandingPage: () => <div>Landing route</div> }));
vi.mock("../pages/BillingPage", () => ({ BillingPage: () => <div>Billing route</div> }));

import { App } from "../App";

describe("subscription routes", () => {
  beforeEach(() => window.history.replaceState({}, "", "/"));
  afterEach(cleanup);

  it("routes /home to the marketing landing page", () => {
    window.history.replaceState({}, "", "/home");
    render(<App />);
    expect(screen.getByText("Landing route")).toBeInTheDocument();
  });

  it("routes /pricing to the consumer plan catalogue", () => {
    window.history.replaceState({}, "", "/pricing");
    render(<App />);
    expect(screen.getByText("Pricing route")).toBeInTheDocument();
  });

  it("routes /account/billing to account plan management", () => {
    window.history.replaceState({}, "", "/account/billing");
    render(<App />);
    expect(screen.getByText("Billing route")).toBeInTheDocument();
  });

  it("routes /credits to the AI credit balance and activity page", () => {
    window.history.replaceState({}, "", "/credits");
    render(<App />);
    expect(screen.getByText("Credits route")).toBeInTheDocument();
  });
});
