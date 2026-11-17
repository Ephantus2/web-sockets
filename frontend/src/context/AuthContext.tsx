import {
    createContext,
    useContext,
    useState,
    type ReactNode,
} from "react";

import { authService } from "../features/auth/authService";
import { tokenStorage } from "../utils/tokenStorage";
import type { LoginCredentials } from "../features/auth/types";

interface AuthContextType {
    isAuthenticated: boolean;
    loading: boolean;
    login: (credentials: LoginCredentials) => Promise<void>;
    logout: () => void
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

interface AuthProviderProps {
    children: ReactNode
}

export function AuthProvider({ children } : AuthProviderProps) {
    const [isAuthenticated, setIsAuthenticated] = useState(() => Boolean(tokenStorage.getAccessToken()));

    const [loading] = useState(false)
    const login = async (credentials: LoginCredentials) => {
        const tokens = await authService.login(credentials);
        tokenStorage.saveTokens(tokens.access, tokens.refresh);
        setIsAuthenticated(true)
    };

    const logout = () => {
        tokenStorage.clearTokens();
        setIsAuthenticated(false)
    };

    return (
        <AuthContext.Provider
        value={{
            isAuthenticated,
            loading,
            login,
            logout
        }}
        >{children}</AuthContext.Provider>
    )

}


export function useAuth() {
    const context = useContext(AuthContext);
    if (!context) {
        throw new Error("useAuth must be used inside an AuthProvider")
    }

    return context
}