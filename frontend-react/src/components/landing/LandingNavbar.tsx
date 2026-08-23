import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import brandMarkUrl from "../../assets/brand/brand-mark.svg";
import { CortexIcon } from "../shared/CortexIcon";
import type { AppTheme } from "../../hooks/useTheme";
import styles from "./LandingNavbar.module.css";

interface LandingNavbarProps {
  theme: AppTheme;
  onToggleTheme: () => void;
  loggedIn?: boolean;
  onLogin?: () => void;
}

export function LandingNavbar({
  theme,
  onToggleTheme,
  loggedIn = false,
  onLogin,
}: LandingNavbarProps) {
  const navigate = useNavigate();
  const [scrolled, setScrolled] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  useEffect(() => {
    const handleScroll = () => {
      setScrolled(window.scrollY > 20);
    };
    window.addEventListener("scroll", handleScroll, { passive: true });
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  const scrollToSection = (id: string) => {
    setMobileMenuOpen(false);
    const element = document.getElementById(id);
    if (element) {
      element.scrollIntoView({ behavior: "smooth" });
    }
  };

  return (
    <header className={`${styles.header} ${scrolled ? styles.scrolled : ""}`}>
      <div className={styles.container}>
        <div className={styles.brandGroup}>
          <button
            type="button"
            className={styles.brandButton}
            onClick={() => window.scrollTo({ top: 0, behavior: "smooth" })}
            aria-label="CortexAI Home"
          >
            <img src={brandMarkUrl} alt="" className={styles.brandMark} />
            <span className={styles.brandName}>CortexAI</span>
          </button>
          <span className={styles.gatewayBadge}>Gateway</span>
        </div>

        <nav className={styles.desktopNav} aria-label="Landing page navigation">
          <button
            type="button"
            className={styles.navLink}
            onClick={() => scrollToSection("why-cortex")}
          >
            Why Us
          </button>
          <button
            type="button"
            className={styles.navLink}
            onClick={() => scrollToSection("how-it-works")}
          >
            Architecture
          </button>
          <button
            type="button"
            className={styles.navLink}
            onClick={() => scrollToSection("compare-demo")}
          >
            Compare Demo
          </button>
          <button
            type="button"
            className={styles.navLink}
            onClick={() => scrollToSection("features")}
          >
            Features
          </button>
          <button
            type="button"
            className={styles.navLink}
            onClick={() => scrollToSection("pricing")}
          >
            Pricing
          </button>
          <button
            type="button"
            className={styles.navLink}
            onClick={() => scrollToSection("trust")}
          >
            Trust & Security
          </button>
        </nav>

        <div className={styles.actionGroup}>
          <button
            type="button"
            className={styles.themeToggle}
            onClick={onToggleTheme}
            aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} theme`}
            title={`Switch to ${theme === "dark" ? "light" : "dark"} theme`}
          >
            <CortexIcon name={theme === "dark" ? "sun" : "moon"} size={18} />
          </button>

          {loggedIn ? (
            <button
              type="button"
              className={styles.primaryButton}
              onClick={() => navigate("/")}
            >
              <span>Launch Workspace</span>
              <CortexIcon name="chevron-right" size={14} strokeWidth={2.5} />
            </button>
          ) : (
            <div className={styles.authButtons}>
              {onLogin && (
                <button
                  type="button"
                  className={styles.secondaryButton}
                  onClick={onLogin}
                >
                  Sign In
                </button>
              )}
              <button
                type="button"
                className={styles.primaryButton}
                onClick={() => navigate("/")}
              >
                <span>Launch App</span>
                <CortexIcon name="chevron-right" size={14} strokeWidth={2.5} />
              </button>
            </div>
          )}

          <button
            type="button"
            className={styles.mobileMenuToggle}
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            aria-label="Toggle mobile menu"
            aria-expanded={mobileMenuOpen}
          >
            <span className={styles.hamburgerLine} />
            <span className={styles.hamburgerLine} />
            <span className={styles.hamburgerLine} />
          </button>
        </div>
      </div>

      {mobileMenuOpen && (
        <div className={styles.mobileMenu} role="dialog" aria-label="Mobile Navigation">
          <nav className={styles.mobileNavLinks}>
            <button
              type="button"
              className={styles.mobileNavLink}
              onClick={() => scrollToSection("why-cortex")}
            >
              Why Us
            </button>
            <button
              type="button"
              className={styles.mobileNavLink}
              onClick={() => scrollToSection("how-it-works")}
            >
              Architecture
            </button>
            <button
              type="button"
              className={styles.mobileNavLink}
              onClick={() => scrollToSection("compare-demo")}
            >
              Compare Demo
            </button>
            <button
              type="button"
              className={styles.mobileNavLink}
              onClick={() => scrollToSection("features")}
            >
              Features
            </button>
            <button
              type="button"
              className={styles.mobileNavLink}
              onClick={() => scrollToSection("pricing")}
            >
              Pricing
            </button>
            <button
              type="button"
              className={styles.mobileNavLink}
              onClick={() => scrollToSection("trust")}
            >
              Trust & Security
            </button>
            <button
              type="button"
              className={styles.mobileNavLink}
              onClick={() => {
                setMobileMenuOpen(false);
                navigate("/");
              }}
            >
              Open Chat Workspace
            </button>
          </nav>
        </div>
      )}
    </header>
  );
}
