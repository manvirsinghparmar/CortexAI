import { useState, useEffect, useRef, useCallback } from "react";
import { useAuth } from "../hooks/useAuth";
import { useTheme } from "../hooks/useTheme";
import { useCursorSpotlight } from "../components/landing/useCursorSpotlight";
import { CortexIcon } from "../components/shared/CortexIcon";
import { LandingNavbar } from "../components/landing/LandingNavbar";
import { LandingHero } from "../components/landing/LandingHero";
import { WhyCortexSection } from "../components/landing/WhyCortexSection";
import { HowItWorksSteps } from "../components/landing/HowItWorksSteps";
import { InteractiveCompareDemo } from "../components/landing/InteractiveCompareDemo";
import { FeatureHighlights } from "../components/landing/FeatureHighlights";
import { PricingSection } from "../components/landing/PricingSection";
import { TrustSection } from "../components/landing/TrustSection";
import { BillingNotes } from "../components/landing/BillingNotes";
import { LandingFooter } from "../components/landing/LandingFooter";
import styles from "./LandingPage.module.css";

const DETAIL_ANCHOR_IDS = new Set([
  "how-it-works",
  "compare-demo",
  "features",
  "trust",
  "learn-more-details",
]);

export function LandingPage() {
  const { theme, toggleTheme } = useTheme();
  const { loggedIn, login } = useAuth();
  const containerRef = useCursorSpotlight();
  const [scrollProgress, setScrollProgress] = useState(0);
  const [detailsExpanded, setDetailsExpanded] = useState(false);
  const pendingScrollId = useRef<string | null>(null);

  useEffect(() => {
    const handleScroll = () => {
      const totalHeight = document.documentElement.scrollHeight - window.innerHeight;
      if (totalHeight > 0) {
        const progress = Math.min(100, Math.max(0, (window.scrollY / totalHeight) * 100));
        setScrollProgress(progress);
      }
    };

    window.addEventListener("scroll", handleScroll, { passive: true });
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  useEffect(() => {
    if (!detailsExpanded || !pendingScrollId.current) return;
    const id = pendingScrollId.current;
    pendingScrollId.current = null;
    const raf = requestAnimationFrame(() => {
      document.getElementById(id)?.scrollIntoView({ behavior: "smooth" });
    });
    return () => cancelAnimationFrame(raf);
  }, [detailsExpanded]);

  const handleNavigate = useCallback(
    (id: string) => {
      if (DETAIL_ANCHOR_IDS.has(id) && !detailsExpanded) {
        pendingScrollId.current = id;
        setDetailsExpanded(true);
        return;
      }
      document.getElementById(id)?.scrollIntoView({ behavior: "smooth" });
    },
    [detailsExpanded],
  );

  return (
    <div ref={containerRef} className={styles.pageContainer}>
      {/* Scroll-linked progress bar */}
      <div
        className={styles.scrollProgressBar}
        style={{ transform: `scaleX(${scrollProgress / 100})` }}
        aria-hidden="true"
      />

      {/* Ambient cursor spotlight overlay */}
      <div className={styles.spotlightOverlay} aria-hidden="true" />

      {/* Navigation Header */}
      <LandingNavbar
        theme={theme}
        onToggleTheme={toggleTheme}
        loggedIn={loggedIn}
        onLogin={login}
        onNavigate={handleNavigate}
      />

      {/* Main Page Flow */}
      <main id="main-content">
        <LandingHero />
        <WhyCortexSection />
        <PricingSection />

        <div className={styles.learnMoreWrap}>
          <button
            type="button"
            className={styles.learnMoreLink}
            onClick={() => handleNavigate("learn-more-details")}
            aria-expanded={detailsExpanded}
          >
            <span>
              {detailsExpanded
                ? "Show less"
                : "See architecture, live demo & full details"}
            </span>
            <CortexIcon
              name="chevron-down"
              size={16}
              style={{ transform: detailsExpanded ? "rotate(180deg)" : undefined }}
            />
          </button>
        </div>

        {detailsExpanded && (
          <div id="learn-more-details">
            <HowItWorksSteps />
            <InteractiveCompareDemo />
            <FeatureHighlights />
            <TrustSection />
            <BillingNotes />
          </div>
        )}
      </main>

      {/* Footer */}
      <LandingFooter theme={theme} onToggleTheme={toggleTheme} onNavigate={handleNavigate} />
    </div>
  );
}
