import { createContext, useContext, useEffect, useState, type ReactNode, } from "react";

import { authService } from "../features/auth/authService";
import { tokenStorage } from "../utils/tokenStorage";
import type { LoginCredentials, CurrentUser } from "../features/auth/types";

interface AuthContextType {
    isAuthenticated: boolean;
    loading: boolean;
    user: CurrentUser | null;
    login: (credentials: LoginCredentials) => Promise<void>;
    logout: () => void
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

interface AuthProviderProps {
    children: ReactNode
}

export function AuthProvider({ children }: AuthProviderProps){
    const [isAuthenticated, setIsAuthenticated] = useState(
        () => Boolean(tokenStorage.getAccessToken())
    );

    const [user, setUser] = useState<CurrentUser | null>(null)

    const [loading, setLoading] = useState(
        () => Boolean(tokenStorage.getAccessToken())
    )

    // Restore the authenticated user when the application loads
    useEffect(() => {
        let isMounted = true;

        const fetchCurrentUser = async () => {
            if (!tokenStorage.getAccessToken()){
                setLoading(false)
                return;
            }
            try {
                const currentUser = await authService.getCurrentUser();

                if (isMounted) {
                    setUser(currentUser)
                    setIsAuthenticated(true)
                }
            } catch (error) {
                console.log("Failed to restore user session", error)

                if (isMounted) {
                    tokenStorage.clearTokens();
                    setUser(null)
                    setIsAuthenticated(false)
                }
            } finally {
                if (isMounted) {
                    setLoading(false);
                }
            }
        }

        fetchCurrentUser()

        return () => {
            isMounted = false
        }
    }, []);

    const login = async (credentials: LoginCredentials) => {
        const tokens = await authService.login(credentials);

        tokenStorage.saveTokens(tokens.access, tokens.refresh)

        try {
            const currentUser = await authService.getCurrentUser();

            setUser(currentUser)
            setIsAuthenticated(true)
        } catch (error) {
            tokenStorage.clearTokens();
            setUser(null)
            setIsAuthenticated(false)
            throw error
        }
    }

    const logout = () => {
        tokenStorage.clearTokens();
        setUser(null);
        setIsAuthenticated(false)
    }

    return (
        <AuthContext.Provider value={{
            isAuthenticated,
            loading,
            user,
            login,
            logout
        }}>
            {children}
        </AuthContext.Provider>
    )

}

export function useAuth() {
    const context = useContext(AuthContext);

    if (!context) {
        throw new Error("useAuth must be used inside an AuthProvider");
    }

    return context
}