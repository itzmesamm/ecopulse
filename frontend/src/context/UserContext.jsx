import { createContext, useContext, useEffect, useState } from "react";
import { useLocation } from "react-router-dom";
import { api } from "../services/api";
import { currentAccount, currentUser as fallbackUser } from "../data/mockData";

const UserContext = createContext({
  user: fallbackUser,
  account: currentAccount,
});

export function UserProvider({ children }) {
  const location = useLocation();
  const [profile, setProfile] = useState({ user: fallbackUser, account: currentAccount });

  useEffect(() => {
    if (!api.isAuthenticated()) {
      setProfile({ user: fallbackUser, account: currentAccount });
      return;
    }
    api.getCurrentUser().then(setProfile).catch(() => {});
  }, [location.pathname]);

  return <UserContext.Provider value={profile}>{children}</UserContext.Provider>;
}

export function useUser() {
  return useContext(UserContext);
}
