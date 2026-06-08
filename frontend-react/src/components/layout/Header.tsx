import type { WhoAmIResponse, CognitoConfig } from "../../types";

interface HeaderProps {
  whoAmI: WhoAmIResponse | null;
  cognitoConfig: CognitoConfig | null;
  loggedIn: boolean;
  onLogin: () => void;
  onLogout: () => void;
}

// Auth is shown in the Sidebar. Kept for API compatibility.
export function Header(_props: HeaderProps) {
  void _props;
  return null;
}
