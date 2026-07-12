import { describe, expect, it } from "vitest";
import { extractSuggestedFollowUps } from "../followups/suggestedFollowups";

describe("extractSuggestedFollowUps", () => {
  it("extracts markdown bullet options after an assistant follow-up lead-in", () => {
    const text = [
      "Bottom line: Jal jeera is not a proven liver treatment.",
      "",
      "If you want, I can also give you:",
      "",
      "- a scientific evidence summary for each ingredient, or",
      "- a safer jal jeera recipe optimized for digestion and low sodium.",
    ].join("\n");

    expect(extractSuggestedFollowUps(text)).toEqual([
      "a scientific evidence summary for each ingredient",
      "a safer jal jeera recipe optimized for digestion and low sodium",
    ]);
  });

  it("extracts numbered options and caps the row", () => {
    const text = [
      "I can also provide:",
      "1. Show the full odds table",
      "2. Explain dark-horse teams",
      "3. Compare the top five favorites",
      "4. Build a bracket view",
    ].join("\n");

    expect(extractSuggestedFollowUps(text)).toEqual([
      "Show the full odds table",
      "Explain dark-horse teams",
      "Compare the top five favorites",
    ]);
  });

  it("does not invent chips for generic unstructured final questions", () => {
    expect(
      extractSuggestedFollowUps(
        "That is the summary. Would you like me to explain anything else?",
      ),
    ).toEqual([]);
  });

  it("extracts inline options only when the lead-in uses a colon", () => {
    expect(
      extractSuggestedFollowUps(
        "If you want, I can also give you: a short checklist, or a rollout plan.",
      ),
    ).toEqual(["a short checklist", "a rollout plan"]);
  });

  it("extracts a single concrete offer at the end of an answer", () => {
    expect(
      extractSuggestedFollowUps(
        [
          "That is the main way a mixed fleet can outperform an all-F-35 force.",
          "",
          "If you want, I can turn this into a **force-design concept for Canada** with a sample split of missions between F-35 and Gripen.",
        ].join("\n"),
      ),
    ).toEqual([
      "Turn this into a force-design concept for Canada with a sample split of missions between F-35 and Gripen",
    ]);
  });

  it("turns a single 'give you' offer into a user-style prompt", () => {
    expect(
      extractSuggestedFollowUps(
        "If you want, I can give you a safer jal jeera recipe optimized for digestion.",
      ),
    ).toEqual([
      "Give me a safer jal jeera recipe optimized for digestion",
    ]);
  });

  it("does not chip vague single-offer endings", () => {
    expect(
      extractSuggestedFollowUps(
        "If you want, I can provide more details.",
      ),
    ).toEqual([]);
  });

  it("extracts a quoted focused follow-up query", () => {
    expect(
      extractSuggestedFollowUps(
        [
          "For specific expected dates or phases of deployment, additional details would be required.",
          'A focused follow-up query could be: "What are the latest updates on the testing phases and expected deployment date for the Tejas Mk2 in the Indian Air Force?" This could provide more accurate information.',
        ].join("\n"),
      ),
    ).toEqual([
      "What are the latest updates on the testing phases and expected deployment date for the Tejas Mk2 in the Indian Air Force?",
    ]);
  });

  it("extracts alternate quoted follow-up question wording", () => {
    expect(
      extractSuggestedFollowUps(
        'You could ask: "Show the official deployment timeline for Tejas Mk2."',
      ),
    ).toEqual(["Show the official deployment timeline for Tejas Mk2"]);
  });

  it("extracts a markdown-bold quoted specific query", () => {
    expect(
      extractSuggestedFollowUps(
        [
          "The provided sources focus on his international performance and future.",
          'For a more detailed analysis of his recent club form, a specific query would be needed, such as: **"What were Cristiano Ronaldo\'s goal and assist statistics for Al-Nassr in the most recent season?"**',
        ].join("\n"),
      ),
    ).toEqual([
      "What were Cristiano Ronaldo's goal and assist statistics for Al-Nassr in the most recent season?",
    ]);
  });

  it("does not extract unquoted follow-up-query suggestions", () => {
    expect(
      extractSuggestedFollowUps(
        "A focused follow-up query could be helpful if more official dates are needed.",
      ),
    ).toEqual([]);
  });
});
