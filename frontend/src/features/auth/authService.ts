import api from "../../api/client"
import type { LoginCredentials, AuthTokens } from "./types"

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
    }
}