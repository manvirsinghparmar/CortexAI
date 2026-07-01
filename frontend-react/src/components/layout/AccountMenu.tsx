import { useCallback, useEffect, useRef, useState } from "react";
import { CortexIcon, type CortexIconName } from "../shared/CortexIcon";
import type { AppTheme } from "../../hooks/useTheme";
import styles from "./AccountMenu.module.css";

interface AccountMenuProps {
  authEnabled: boolean;
  loggedIn: boolean;
  onLogin?: () => void;
  onLogout?: () => void;
  onUsageInsights?: () => void;
  theme?: AppTheme;
  onToggleTheme?: () => void;
}

type AccountMenuActionKey = "login" | "logout" | "theme" | "usage";

interface AccountMenuAction {
  key: AccountMenuActionKey;
  label: string;
  ariaLabel?: string;
  icon?: CortexIconName;
}

export function AccountMenu({
  authEnabled,
  loggedIn,
  onLogin,
  onLogout,
  onUsageInsights,
  theme,
  onToggleTheme,
}: AccountMenuProps) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const closeTimerRef = useRef<number | null>(null);
  const canLogin = authEnabled && !!onLogin;
  const canLogout = !!onLogout;
  const canOpenUsage = !!onUsageInsights;
  const canToggleTheme = !!theme && !!onToggleTheme;
  const nextTheme = theme === "dark" ? "light" : "dark";
  const menuActions: AccountMenuAction[] = [];
  if (!loggedIn && canLogin) {
    menuActions.push({ key: "login", label: "Sign in" });
  }
  if (canOpenUsage) {
    menuActions.push({
      key: "usage",
      label: "Usage & insights",
      icon: "usage",
    });
  }
  if (canToggleTheme) {
    menuActions.push({
      key: "theme",
      label: nextTheme === "dark" ? "Dark theme" : "Light theme",
      ariaLabel: `Switch to ${nextTheme} theme`,
      icon: nextTheme === "dark" ? "moon" : "sun",
    });
  }
  if (canLogout) {
    menuActions.push({ key: "logout", label: "Log off" });
  }
  const showMenu = menuActions.length > 0;
  const buttonLabel = loggedIn ? "Account" : "Guest account";

  const clearCloseTimer = useCallback(() => {
    if (closeTimerRef.current === null) return;
    window.clearTimeout(closeTimerRef.current);
    closeTimerRef.current = null;
  }, []);

  const openMenu = useCallback(() => {
    clearCloseTimer();
    if (showMenu) setOpen(true);
  }, [clearCloseTimer, showMenu]);

  const closeMenu = useCallback(() => {
    clearCloseTimer();
    setOpen(false);
  }, [clearCloseTimer]);

  const scheduleCloseMenu = useCallback(() => {
    clearCloseTimer();
    closeTimerRef.current = window.setTimeout(() => {
      setOpen(false);
      closeTimerRef.current = null;
    }, 160);
  }, [clearCloseTimer]);

  useEffect(() => {
    return () => {
      if (closeTimerRef.current !== null) {
        window.clearTimeout(closeTimerRef.current);
      }
    };
  }, []);

  useEffect(() => {
    if (!open) return;

    const handlePointerDown = (event: PointerEvent) => {
      const target = event.target;
      if (target instanceof Node && rootRef.current?.contains(target)) return;
      closeMenu();
    };

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") closeMenu();
    };

    document.addEventListener("pointerdown", handlePointerDown);
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("pointerdown", handlePointerDown);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [closeMenu, open]);

  const handleAction = (action: AccountMenuActionKey) => {
    closeMenu();
    if (action === "logout") {
      onLogout?.();
    } else if (action === "theme") {
      onToggleTheme?.();
    } else if (action === "usage") {
      onUsageInsights?.();
    } else {
      onLogin?.();
    }
  };

  return (
    <div
      ref={rootRef}
      className={styles.accountMenu}
      onMouseEnter={openMenu}
      onMouseLeave={(event) => {
        const nextTarget = event.relatedTarget;
        if (!(nextTarget instanceof Node) || !rootRef.current?.contains(nextTarget)) {
          scheduleCloseMenu();
        }
      }}
    >
      <button
        type="button"
        className={styles.accountButton}
        aria-label={buttonLabel}
        aria-haspopup={showMenu ? "menu" : undefined}
        aria-expanded={showMenu ? open : undefined}
        onClick={() => {
          if (showMenu) setOpen(true);
        }}
      >
        <CortexIcon name="user" />
      </button>

      {showMenu && open && (
        <div
          className={styles.menu}
          role="menu"
          aria-label="Account menu"
          onMouseEnter={openMenu}
        >
          {menuActions.map((action) => (
            <button
              key={action.key}
              type="button"
              role="menuitem"
              className={styles.menuItem}
              aria-label={action.ariaLabel}
              onClick={() => handleAction(action.key)}
            >
              {action.icon && <CortexIcon name={action.icon} />}
              <span>{action.label}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
