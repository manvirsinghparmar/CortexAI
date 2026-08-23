import { useState, useEffect } from "react";
import { useAuth } from "../hooks/useAuth";
import { useTheme } from "../hooks/useTheme";
import { useCursorSpotlight } from "../components/landing/useCursorSpotlight";
import { LandingNavbar } from "../components/landing/LandingNavbar";
import { LandingHero } from "../components/landing/LandingHero";
import { WhyCortexSection } from "../components/landing/WhyCortexSection";
import { HowItWorksSteps } from "../components/landing/HowItWorksSteps";
import { InteractiveCompareDemo } from "../components/landing/InteractiveCompareDemo";
import { FeatureHighlights } from "../components/landing/FeatureHighlights";
import { PricingSection } from "../components/landing/PricingSection";
import { TrustSection } from "../components/landing/TrustSection";
import { LandingFooter } from "../components/landing/LandingFooter";
import styles from "./LandingPage.module.css";

export function LandingPage() {
  const { theme, toggleTheme } = useTheme();
  const { loggedIn, login } = useAuth();
  const containerRef = useCursorSpotlight();
  const [scrollProgress, setScrollProgress] = useState(0);

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
      />

      {/* Main Page Flow */}
      <main id="main-content">
        <LandingHero />
        <WhyCortexSection />
        <HowItWorksSteps />
        <InteractiveCompareDemo />
        <FeatureHighlights />
        <PricingSection />
        <TrustSection />
      </main>

      {/* Footer */}
      <LandingFooter theme={theme} onToggleTheme={toggleTheme} />
    </div>
  );
}
