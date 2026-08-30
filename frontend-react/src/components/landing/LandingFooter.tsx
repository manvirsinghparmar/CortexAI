import { useNavigate } from "react-router-dom";
import brandMarkUrl from "../../assets/brand/brand-mark.svg";
import { CortexIcon } from "../shared/CortexIcon";
import { ScrollReveal } from "./ScrollReveal";
import type { AppTheme } from "../../hooks/useTheme";
import styles from "./LandingFooter.module.css";

interface LandingFooterProps {
  theme: AppTheme;
  onToggleTheme: () => void;
  onNavigate: (id: string) => void;
}

export function LandingFooter({ theme, onToggleTheme, onNavigate }: LandingFooterProps) {
  const navigate = useNavigate();

  const scrollToTop = () => {
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const scrollToSection = (id: string) => {
    onNavigate(id);
  };

  return (
    <footer className={styles.footer}>
      {/* Final Call to Action Banner */}
      <div className={styles.ctaWrapper}>
        <ScrollReveal variant="zoom-in" className={styles.ctaCard}>
          <div className={styles.ctaGlow} aria-hidden="true" />
          <div className={styles.ctaContent}>
            <span className={styles.ctaEyebrow}>START ORCHESTRATING IN SECONDS</span>
            <h2 className={styles.ctaTitle}>
              Ready to Supercharge Your AI Stack?
            </h2>
            <p className={styles.ctaSubtitle}>
              Experience multi-model comparison, smart routing, and Cortex synthesis with 100,000 free monthly AI credits.
            </p>
            <div className={styles.ctaActions}>
              <button
                type="button"
                className={styles.ctaPrimary}
                onClick={() => navigate("/")}
              >
                <span>Launch CortexAI Workspace</span>
                <CortexIcon name="chevron-right" size={16} strokeWidth={2.5} />
              </button>
              <button
                type="button"
                className={styles.ctaSecondary}
                onClick={() => scrollToSection("pricing")}
              >
                <span>View Subscription Plans</span>
              </button>
            </div>
          </div>
        </ScrollReveal>
      </div>

      {/* Main Footer Links */}
      <div className={styles.container}>
        <div className={styles.linksGrid}>
          {/* Col 1: Brand & Tagline */}
          <div className={styles.brandCol}>
            <div className={styles.brandGroup}>
              <img src={brandMarkUrl} alt="" className={styles.brandMark} />
              <span className={styles.brandName}>CortexAI</span>
            </div>
            <p className={styles.brandTagline}>
              Multi-provider LLM orchestration gateway. One unified API and workspace for OpenAI, Claude, Gemini, DeepSeek, and Grok.
            </p>
            <div className={styles.themeToggleRow}>
              <button
                type="button"
                className={styles.themeButton}
                onClick={onToggleTheme}
                aria-label={`Toggle theme (currently ${theme})`}
              >
                <CortexIcon name={theme === "dark" ? "sun" : "moon"} size={16} />
                <span>{theme === "dark" ? "Light Mode" : "Dark Mode"}</span>
              </button>
            </div>
          </div>

          {/* Col 2: Product */}
          <div className={styles.linkCol}>
            <h4>Product</h4>
            <ul>
              <li>
                <button type="button" onClick={() => navigate("/")}>
                  Ask & Chat
                </button>
              </li>
              <li>
                <button type="button" onClick={() => navigate("/")}>
                  Multi-Model Compare
                </button>
              </li>
              <li>
                <button type="button" onClick={() => navigate("/models")}>
                  Models Catalogue
                </button>
              </li>
              <li>
                <button type="button" onClick={() => navigate("/credits")}>
                  AI Credit Wallet
                </button>
              </li>
              <li>
                <button type="button" onClick={() => navigate("/usage")}>
                  Usage Insights
                </button>
              </li>
            </ul>
          </div>

          {/* Col 3: Architecture & Gateway */}
          <div className={styles.linkCol}>
            <h4>Architecture</h4>
            <ul>
              <li>
                <button type="button" onClick={() => scrollToSection("how-it-works")}>
                  Smart Router (T0–T3)
                </button>
              </li>
              <li>
                <button type="button" onClick={() => scrollToSection("compare-demo")}>
                  Cortex Synthesis Engine
                </button>
              </li>
              <li>
                <button type="button" onClick={() => scrollToSection("trust")}>
                  BYOK Key Encryption
                </button>
              </li>
              <li>
                <button type="button" onClick={() => scrollToSection("features")}>
                  Tavily Web Research
                </button>
              </li>
              <li>
                <button type="button" onClick={() => scrollToSection("trust")}>
                  Circuit Breakers & Uptime
                </button>
              </li>
            </ul>
          </div>

          {/* Col 4: Plans & Governance */}
          <div className={styles.linkCol}>
            <h4>Plans & Trust</h4>
            <ul>
              <li>
                <button type="button" onClick={() => scrollToSection("pricing")}>
                  Free Tier (100k credits)
                </button>
              </li>
              <li>
                <button type="button" onClick={() => scrollToSection("pricing")}>
                  Plus Tier ($6.99/mo)
                </button>
              </li>
              <li>
                <button type="button" onClick={() => scrollToSection("pricing")}>
                  Pro Tier ($12.99/mo)
                </button>
              </li>
              <li>
                <button type="button" onClick={() => navigate("/account/billing")}>
                  Stripe Billing Portal
                </button>
              </li>
              <li>
                <button type="button" onClick={() => scrollToSection("trust")}>
                  Privacy & PII Redaction
                </button>
              </li>
            </ul>
          </div>
        </div>

        {/* Bottom Bar */}
        <div className={styles.bottomBar}>
          <p className={styles.copyright}>
            © {new Date().getFullYear()} CortexAI Inc. All rights reserved. Multi-provider LLM orchestration gateway.
          </p>

          <button
            type="button"
            className={styles.backToTopButton}
            onClick={scrollToTop}
            aria-label="Back to top"
          >
            <span>Back to top</span>
            <CortexIcon name="chevron-down" size={14} style={{ transform: "rotate(180deg)" }} />
          </button>
        </div>
      </div>
    </footer>
  );
}
