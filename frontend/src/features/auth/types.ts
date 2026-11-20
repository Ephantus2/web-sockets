export interface LoginCredentials {
    username: string;
    password: string;
}

export interface AuthTokens {
    access: string;
    refresh: string;
}

export interface CurrentUser {
    id: number;
    username: string;
    email: string;
}

