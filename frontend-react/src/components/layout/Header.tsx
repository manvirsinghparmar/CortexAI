import type { WhoAmIResponse, CognitoConfig } from "../../types";
import styles from "./Header.module.css";

interface HeaderProps {
  whoAmI: WhoAmIResponse | null;
  cognitoConfig: CognitoConfig | null;
  loggedIn: boolean;
  onLogin: () => void;
  onLogout: () => void;
}

export function Header({ whoAmI, cognitoConfig, loggedIn, onLogin, onLogout }: HeaderProps) {
  const authEnabled = cognitoConfig?.enabled ?? false;
  const userLabel = whoAmI?.user_id ?? "Account";

  return (
    <header className={styles.header} id="mainHeader">
      <div className={styles.inner}>
        <div className={styles.logo}>
          <span className={styles.logoText}>CortexAI</span>
        </div>
        <div className={styles.right}>
          {authEnabled && (
            <span className={styles.authWrap}>
              {loggedIn ? (
                <>
                  <span className={styles.userLabel}>{userLabel}</span>
                  <button className={styles.authBtn} onClick={onLogout}>
                    Sign out
                  </button>
                </>
              ) : (
                <button className={styles.authBtn} onClick={onLogin}>
                  Sign in
                </button>
              )}
            </span>
          )}
        </div>
      </div>
    </header>
  );
}
