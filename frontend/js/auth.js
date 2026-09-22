async function logout() {
    try {
        await api("/auth/logout", "POST");
        location.replace("/login");
    } catch (error) {
        if (error.status === 401) location.replace("/login");
        else alert(error.message);
    }
}

async function protectPage() {
    try {
        await api("/auth/me");
    } catch (error) {
        if (error.status !== 401) alert(error.message);
    }
}
