import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi } from "vitest";
import { BrowserRouter } from "react-router-dom";
import { LandingPage } from "../pages/LandingPage";

vi.mock("../hooks/useAuth", () => ({
  useAuth: () => ({
    whoAmI: null,
    cognitoConfig: { enabled: false },
    loading: false,
    loggedIn: false,
    login: vi.fn(),
    logout: vi.fn(),
  }),
}));

describe("LandingPage", () => {
  it("renders hero headline, value proposition, and key CTA buttons", () => {
    render(
      <BrowserRouter>
        <LandingPage />
      </BrowserRouter>,
    );

    expect(
      screen.getByRole("heading", { name: /One Gateway for Every Frontier Model/i }),
    ).toBeInTheDocument();

    expect(
      screen.getByText(/Intelligently route, compare, and synthesize responses/i),
    ).toBeInTheDocument();

    expect(screen.getByRole("button", { name: "Get Started Free" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Explore Plans ($0 – $12.99)" })).toBeInTheDocument();
  });

  it("renders why cortex problem vs solution pillars", () => {
    render(
      <BrowserRouter>
        <LandingPage />
      </BrowserRouter>,
    );

    expect(screen.getByText("WHY CORTEXAI MATTERS")).toBeInTheDocument();
    expect(screen.getByText("Subscription Sprawl & Idling Costs")).toBeInTheDocument();
    expect(screen.getByText("One Unified AI Credit Wallet")).toBeInTheDocument();
    expect(screen.getAllByText("Autonomous Smart Routing (T0–T3)")[0]).toBeInTheDocument();
    expect(screen.getByText("Side-by-Side Compare & Synthesis")).toBeInTheDocument();
  });

  it("renders architecture pipeline steps", () => {
    render(
      <BrowserRouter>
        <LandingPage />
      </BrowserRouter>,
    );

    expect(screen.getByText("ARCHITECTURE & FLOW")).toBeInTheDocument();
    expect(screen.getByText("Ingest & Optional Prompt Rewrite")).toBeInTheDocument();
    expect(screen.getByText("Autonomous Tier Decider (T0–T3)")).toBeInTheDocument();
    expect(screen.getByText("Synchronous Multi-Provider Execution")).toBeInTheDocument();
    expect(screen.getByText("Cortex Synthesis & Atomic Settlement")).toBeInTheDocument();
  });

  it("renders subscription plans Free, Plus, and Pro with monthly/annual toggle", async () => {
    const user = userEvent.setup();
    render(
      <BrowserRouter>
        <LandingPage />
      </BrowserRouter>,
    );

    expect(screen.getByText("TRANSPARENT SUBSCRIPTION TIERS")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Free" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Plus" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Pro" })).toBeInTheDocument();

    // Check recommended badge
    expect(screen.getByText("MOST POPULAR • RECOMMENDED")).toBeInTheDocument();

    // Check initial monthly prices
    expect(screen.getByText("$0")).toBeInTheDocument();
    expect(screen.getByText("$6.99")).toBeInTheDocument();
    expect(screen.getByText("$12.99")).toBeInTheDocument();

    // Toggle to Annual billing
    const annualToggle = screen.getByRole("radio", { name: /Annual billing/i });
    await user.click(annualToggle);

    // Check discounted prices ($5.59 and $10.39)
    expect(screen.getByText("$5.59")).toBeInTheDocument();
    expect(screen.getByText("$10.39")).toBeInTheDocument();
  });

  it("switches demo scenarios in the interactive compare simulator", async () => {
    const user = userEvent.setup();
    render(
      <BrowserRouter>
        <LandingPage />
      </BrowserRouter>,
    );

    const dataTab = screen.getByRole("tab", { name: /Recursive CTE & Window Retention/i });
    await user.click(dataTab);

    expect(
      screen.getByText(/Write a high-performance PostgreSQL query for multi-touch attribution/i),
    ).toBeInTheDocument();
  });

  it("renders trust section and provider status", () => {
    render(
      <BrowserRouter>
        <LandingPage />
      </BrowserRouter>,
    );

    expect(screen.getByText("TRUST, SECURITY & RELIABILITY")).toBeInTheDocument();
    expect(screen.getByText("BYOK Tenant Key Security")).toBeInTheDocument();
    expect(screen.getByText("Zero-Retention Privacy Controls")).toBeInTheDocument();
    expect(screen.getByText("PostgreSQL ACID Durability")).toBeInTheDocument();
  });
});
