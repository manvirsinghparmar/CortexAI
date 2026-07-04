import { describe, expect, it } from "vitest";
import { faviconUrl, publisherName } from "../utils/sourceMeta";

describe("sourceMeta", () => {
  it("uses a publisher suffix from the source title", () => {
    expect(
      publisherName({
        title: "Middle East update | Al Jazeera",
        url: "https://www.aljazeera.com/news/story",
      }),
    ).toBe("Al Jazeera");

    expect(
      publisherName({
        title: "Large language model - Wikipedia",
        url: "https://en.wikipedia.org/wiki/Large_language_model",
      }),
    ).toBe("Wikipedia");
  });

  it("uses common publisher names for known hosts", () => {
    expect(
      publisherName({
        title: "Morning Edition",
        url: "https://www.npr.org/sections/news/",
      }),
    ).toBe("NPR");
  });

  it("falls back to a readable host name for bare domains", () => {
    expect(
      publisherName({
        title: "Local coverage",
        url: "https://www.greenwichtime.com/news/article/example",
      }),
    ).toBe("Greenwich Time");
  });

  it("guards against malformed URLs", () => {
    expect(
      publisherName({
        title: "",
        url: "not a valid url",
      }),
    ).toBe("not a valid url");
  });

  it("builds an https favicon URL from the source host", () => {
    expect(
      faviconUrl({
        title: "Morning Edition",
        url: "https://www.npr.org/sections/news/",
      }),
    ).toBe("https://icons.duckduckgo.com/ip3/npr.org.ico");
  });
});
