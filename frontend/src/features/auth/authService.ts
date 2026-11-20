import api from "../../api/client"
import type { LoginCredentials, AuthTokens, CurrentUser } from "./types"

export const authService = {
    async login(credentials: LoginCredentials): Promise<AuthTokens> {
        const response = await api.post<AuthTokens>("/api/token/", credentials);
        return response.data
    },

    async refreshToken(refresh: string): Promise<{access: string}> {
        const response = await api.post<{access: string}>(
            "/api/token/refresh/",
            {refresh}
        );
        return response.data
    },

    async getCurrentUser(): Promise<CurrentUser>{
        const response = await api.get<CurrentUser>("/api/accounts/me/");
        return response.data;
    }
}