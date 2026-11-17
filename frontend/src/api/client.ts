import axios from "axios"
import { tokenStorage } from "../utils/tokenStorage";

const api = axios.create({
    baseURL:
    import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000",
    headers: {
        "Content-Type": "application/json",
    },
    timeout: 15000,
});

// Attach the access token to outgoing requests

api.interceptors.request.use((config) => {
    const accessToken = tokenStorage.getAccessToken()

    if (accessToken){
        config.headers.Authorization = `Bearer ${accessToken}`
    }

    return config
});

export default api;