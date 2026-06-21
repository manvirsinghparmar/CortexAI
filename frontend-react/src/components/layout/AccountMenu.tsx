import { useEffect, useRef, useState } from "react";
import { CortexIcon } from "../shared/CortexIcon";
import styles from "./AccountMenu.module.css";

interface AccountMenuProps {
  authEnabled: boolean;
  loggedIn: boolean;
  onLogin?: () => void;
  onLogout?: () => void;
}

export function AccountMenu({
  authEnabled,
  loggedIn,
  onLogin,
  onLogout,
}: AccountMenuProps) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const canLogin = authEnabled && !!onLogin;
  const canLogout = !!onLogout;
  const menuActions = [
    ...(!loggedIn && canLogin ? [{ key: "login", label: "Sign in" }] : []),
    ...(canLogout ? [{ key: "logout", label: "Log off" }] : []),
  ] as const;
  const showMenu = menuActions.length > 0;
  const buttonLabel = loggedIn ? "Account" : "Guest account";

  useEffect(() => {
    if (!open) return;

    const handlePointerDown = (event: PointerEvent) => {
      const target = event.target;
      if (target instanceof Node && rootRef.current?.contains(target)) return;
      setOpen(false);
    };

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };

    document.addEventListener("pointerdown", handlePointerDown);
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("pointerdown", handlePointerDown);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [open]);

  const handleAction = (action: (typeof menuActions)[number]["key"]) => {
    setOpen(false);
    if (action === "logout") {
      onLogout?.();
    } else {
      onLogin?.();
    }
  };

  return (
    <div
      ref={rootRef}
      className={styles.accountMenu}
      onMouseEnter={() => showMenu && setOpen(true)}
      onMouseLeave={(event) => {
        const nextTarget = event.relatedTarget;
        if (nextTarget instanceof Node && !rootRef.current?.contains(nextTarget)) {
          setOpen(false);
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
        <div className={styles.menu} role="menu" aria-label="Account menu">
          {menuActions.map((action) => (
            <button
              key={action.key}
              type="button"
              role="menuitem"
              className={styles.menuItem}
              onClick={() => handleAction(action.key)}
            >
              {action.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
